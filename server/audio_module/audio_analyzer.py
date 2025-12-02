"""
Naver Cloud Clova Speech 기반 오디오 분석 모듈
- 오디오 다운로드 및 STT (Speech-to-Text)
- 제목 낚시 및 주제 이탈 탐지
"""

import logging
import time
import os
import json
import requests
import asyncio
import yt_dlp
import tempfile
from typing import List, Dict, Any, Optional

from ..shared.schemas import Claim, VideoMeta
from ..shared.logger_utils import log_execution
from .schemas import AudioAnalysisRequest, AudioModuleResult, ClaimVerdict
from ..shared.llm_client import get_llm_client
from ..config import Config

logger = logging.getLogger(__name__)

class AudioAnalyzer:
    """
    Naver Clova Speech API를 사용하여 오디오 내용을 분석하고
    제목/주장과의 일치 여부(낚시성)를 판별하는 클래스
    """

    def __init__(self):
        """AudioAnalyzer 초기화"""
        logger.info("AudioAnalyzer(Naver Cloud) 초기화 시작...")
        
        self.invoke_url = Config.NAVER_CLOVA_SPEECH_INVOKE_URL
        self.secret_key = Config.NAVER_CLOVA_SPEECH_SECRET_KEY
        
        if not self.invoke_url or not self.secret_key:
            logger.warning("Naver Clova Speech 설정이 누락되었습니다.")

    @log_execution(module_name="audio", step_name="full_analysis")
    async def analyze(self, request: AudioAnalysisRequest) -> AudioModuleResult:
        """
        오디오 분석 수행 (다운로드 -> STT -> 낚시 탐지)
        """
        start_time = time.time()
        logger.info(f"오디오 분석 시작: {request.video_id}")
        
        temp_audio_path = None
        summary = "분석 실패"
        transcript = ""
        
        try:
            # 1. 오디오 다운로드 (yt-dlp)
            video_url = f"https://www.youtube.com/watch?v={request.video_id}"
            temp_audio_path = await asyncio.to_thread(self._download_audio, video_url)
            
            if not temp_audio_path:
                summary = "오디오 파일을 다운로드할 수 없습니다."
            else:
                # 2. Naver Clova Speech로 텍스트 변환 (STT)
                transcript = await asyncio.to_thread(self._transcribe_audio, temp_audio_path)
                
                if not transcript:
                    summary = "오디오에서 목소리를 감지하지 못했거나 API 호출에 실패했습니다."
                else:
                    # 3. 제목 낚시 및 주제 이탈 분석 (LLM)
                    video_title = getattr(request, 'title', '제목 미상') 
                    analysis_result = await self._detect_fishing(video_title, transcript)
                    summary = analysis_result

            # 4. 결과 매핑
            audio_claims = []
            for claim in request.claims:
                audio_claims.append(ClaimVerdict(
                    claim_id=claim.claim_id,
                    audio_support_score=0.0,
                    notes=[summary],
                    segments=[] 
                ))

            processing_time = (time.time() - start_time) * 1000
            logger.info(f"오디오 분석 완료: {processing_time:.2f}ms")

            return AudioModuleResult(
                modality="audio",
                video_id=request.video_id,
                analysis_summary=summary,
                claims=audio_claims,
                processing_time_ms=processing_time,
                status="success",
            )

        except Exception as e:
            logger.error(f"오디오 분석 중 오류: {e}", exc_info=True)
            return AudioModuleResult(
                modality="audio",
                video_id=request.video_id,
                analysis_summary=f"오류 발생: {str(e)}",
                claims=[],
                processing_time_ms=(time.time() - start_time) * 1000,
                status="error",
                error_message=str(e)
            )
        finally:
            if temp_audio_path and os.path.exists(temp_audio_path):
                try:
                    os.remove(temp_audio_path)
                except:
                    pass

    def _download_audio(self, video_url: str) -> Optional[str]:
        """yt-dlp를 사용하여 오디오 다운로드 (m4a/mp3)"""
        try:
            fd, temp_path = tempfile.mkstemp(suffix=".m4a")
            os.close(fd)
            if os.path.exists(temp_path):
                os.remove(temp_path) 

            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': temp_path,
                'quiet': True,
                'no_warnings': True,
                'overwrites': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'm4a',
                }],
            }
            
            logger.info(f"오디오 다운로드 시작: {video_url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
            
            if os.path.exists(temp_path):
                return temp_path
            elif os.path.exists(temp_path + ".m4a"):
                return temp_path + ".m4a"
            
            return None
        except Exception as e:
            logger.error(f"Audio Download Failed: {e}")
            return None

    def _transcribe_audio(self, file_path: str) -> str:
        """Naver Clova Speech API 호출 (파일 업로드 방식)"""
        if not self.invoke_url or not self.secret_key:
            return ""

        try:
            base_url = self.invoke_url.rstrip('/')
            if base_url.endswith('/recognizer/upload'):
                api_url = base_url
            else:
                api_url = f"{base_url}/recognizer/upload"
            
            headers = {
                'X-CLOVASPEECH-API-KEY': self.secret_key
            }
            
            files = {'media': open(file_path, 'rb')}
            
            # [중요 수정] diarization(화자 인식) 기능을 끔
            data = {
                'params': json.dumps({
                    'language': 'ko-KR',
                    'completion': 'sync',
                    'wordAlignment': False,
                    'fullText': True,
                    'diarization': { "enable": False } 
                })
            }
            
            logger.info(f"Clova Speech API 요청: {api_url}")
            response = requests.post(api_url, headers=headers, files=files, data=data, timeout=120)
            
            files['media'].close()

            if response.status_code == 200:
                res_json = response.json()
                text = res_json.get('text', '')
                logger.info(f"STT 변환 성공: {len(text)}자")
                return text
            else:
                logger.error(f"Clova Speech API Error: {response.status_code} - {response.text}")
                return ""
                
        except Exception as e:
            logger.error(f"Transcribe Failed: {e}")
            return ""

    async def _detect_fishing(self, title: str, transcript: str) -> str:
        """LLM을 사용하여 제목과 스크립트 내용의 일치 여부 분석"""
        try:
            llm = await get_llm_client()
            transcript_preview = transcript[:3000] + "..." if len(transcript) > 3000 else transcript
            
            prompt = f"""
            당신은 뉴스 기사 및 영상 분석 전문가입니다.
            다음 유튜브 영상의 '제목'과 실제 '오디오 내용(스크립트)'을 비교하여, 제목이 내용을 왜곡하거나 과장하는 '낚시성(Clickbait)'인지 판별해주세요.

            [영상 제목]
            {title}

            [오디오 내용]
            {transcript_preview}

            분석 가이드:
            1. **사실 일치 여부**: 제목에서 주장하는 핵심 사건이 실제 내용에 포함되어 있습니까?
            2. **주제 이탈 여부**: 제목은 심각한데 내용은 가벼운 잡담이거나 전혀 다른 주제입니까?
            3. **결론 도출**: 위 분석을 바탕으로 이 영상이 '정상적인 정보 전달'인지, '낚시성/허위 콘텐츠'인지 명확히 결론을 내려주세요.

            한 문장으로 요약해서 답변하세요.
            """
            
            messages = [{"role": "user", "content": prompt}]
            response = await llm.chat_completion(messages)
            
            return response
            
        except Exception as e:
            logger.error(f"Fishing Detection Failed: {e}")
            return "내용 분석 중 오류가 발생했습니다."