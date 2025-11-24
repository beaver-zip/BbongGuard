"""오디오 분석 파이프라인 Orchestrator"""

import logging
import time
import os
from typing import List, Dict, Any

from ..shared.schemas import VideoMeta, Claim, AudioSegment
from .aligner import TranscriptAligner
from .feature_extractor import AudioFeatureExtractor
from .summarizer import AudioLLMSummarizer
from ..shared.logger_utils import log_execution
from .schemas import AudioAnalysisRequest, AudioModuleResult, ClaimVerdict

logger = logging.getLogger(__name__)

class AudioAnalyzer:
    """오디오 모듈 전체 파이프라인을 실행하는 클래스"""

    def __init__(self):
        """AudioAnalyzer 초기화"""
        logger.info("AudioAnalyzer 초기화 시작...")
        try:
            self.aligner = TranscriptAligner()
            self.extractor = AudioFeatureExtractor()
            self.summarizer = AudioLLMSummarizer()
            logger.info("AudioAnalyzer 초기화 완료")
        except Exception as e:
            logger.error(f"AudioAnalyzer 초기화 실패: {e}")
            raise

    def _download_audio(self, video_url: str) -> str:
        """오디오 다운로드 (임시 파일)"""
        import yt_dlp
        import tempfile
        
        try:
            # 임시 파일 생성 (확장자는 yt-dlp가 결정하도록 둠, 하지만 편의상 mp3/wav 등 지정)
            # 여기서는 tempfile로 디렉토리만 받고 yt-dlp 템플릿으로 파일명 지정
            temp_dir = tempfile.mkdtemp()
            output_path = os.path.join(temp_dir, "audio.%(ext)s")
            
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'wav',
                    'preferredquality': '192',
                }],
                'outtmpl': output_path,
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
                
            # 다운로드된 파일 찾기 (.wav)
            for f in os.listdir(temp_dir):
                if f.endswith(".wav"):
                    return os.path.join(temp_dir, f)
            
            return None
        except Exception as e:
            logger.error(f"오디오 다운로드 실패: {e}")
            return None

    @log_execution(module_name="audio", step_name="full_analysis")
    async def analyze(self, request: AudioAnalysisRequest) -> AudioModuleResult:
        """
        오디오 분석을 수행합니다. (감정적 선동 탐지)
        """
        start_time = time.time()
        logger.info(f"오디오 분석 시작: {request.video_id}")

        temp_audio_path = None

        try:
            # 1. 오디오 다운로드
            # 오디오는 용량이 작으므로 전체 다운로드 후 구간 추출이 효율적일 수 있음
            # 또는 스트리밍을 지원한다면 좋겠지만, librosa/wav2vec2 처리를 위해 파일이 필요함
            video_url = f"https://www.youtube.com/watch?v={request.video_id}"
            temp_audio_path = self._download_audio(video_url)
            
            if not temp_audio_path:
                return AudioModuleResult(
                    modality="audio",
                    video_id=request.video_id,
                    analysis_summary="오디오 다운로드 실패",
                    claims=[],
                    processing_time_ms=(time.time() - start_time) * 1000,
                    status="error"
                )

            # 2. 0-9 지점 구간 추출 (±5초)
            import librosa
            duration = librosa.get_duration(path=temp_audio_path)
            
            segments = []
            target_positions = [i * 0.1 for i in range(10)]
            
            for i, pos in enumerate(target_positions):
                center_time = duration * pos
                start_time_seg = max(0, center_time - 5)
                end_time_seg = min(duration, center_time + 5)
                
                segments.append(AudioSegment(
                    segment_id=f"sample_{i}",
                    start=start_time_seg,
                    end=end_time_seg,
                    transcript_text="", # 텍스트 매칭은 생략하거나 별도 로직 필요
                    tone="",
                    emotion="",
                    spoof_score=0.0
                ))

            # 3. 특징 추출 (감정/톤)
            processed_segments = self.extractor.extract(temp_audio_path, segments)
            
            # 4. 감정적 선동 분석 (LLM)
            manipulation_analysis = await self._analyze_manipulation(processed_segments, request.claims)
            
            # 결과 매핑
            audio_claims = []
            for claim in request.claims:
                audio_claims.append(ClaimVerdict(
                    claim_id=claim.claim_id,
                    audio_support_score=0.0, # 더 이상 사용 안 함
                    notes=[manipulation_analysis['summary']],
                    segments=[] # 상세 구간 정보는 생략하거나 필요시 추가
                ))

            processing_time = (time.time() - start_time) * 1000
            logger.info(f"오디오 분석 완료: {processing_time:.2f}ms")

            return AudioModuleResult(
                modality="audio",
                video_id=request.video_id,
                analysis_summary=manipulation_analysis['summary'],
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
            # 임시 파일 삭제
            if temp_audio_path and os.path.exists(temp_audio_path):
                try:
                    os.remove(temp_audio_path)
                    os.rmdir(os.path.dirname(temp_audio_path))
                except:
                    pass

    async def _analyze_manipulation(self, segments: List[AudioSegment], claims: List[Claim]) -> Dict[str, Any]:
        """
        오디오 구간의 감정/톤을 분석하여 선동 여부를 판단합니다.
        """
        from ..shared.llm_client import get_llm_client
        llm = get_llm_client()
        
        emotions = [f"{s.start:.1f}s: {s.emotion} ({s.tone})" for s in segments]
        emotions_text = "\n".join(emotions)
        
        claim_texts = "\n".join([f"- {c.claim_text}" for c in claims])
        
        prompt = f"""
        다음은 유튜브 영상의 10개 지점에서 추출한 화자의 감정 및 어조 분석 결과입니다.
        화자가 시청자를 감정적으로 선동하거나, 내용(주장)에 비해 지나치게 격앙된 어조를 사용하는지 분석해주세요.

        [감정/어조 분석 결과]
        {emotions_text}

        [핵심 주장]
        {claim_texts}

        분석 기준:
        1. 감정적 선동 (Emotional Manipulation): 0~10점. (10: 분노/공포 등 부정적 감정을 과도하게 표출)
        2. 부자연스러움 (Unnaturalness): 0~10점. (10: 기계음 같거나 매우 부자연스러운 억양)
        
        결과를 JSON 형식으로 반환해주세요:
        {{
            "manipulation_score": int,
            "unnaturalness_score": int,
            "summary": "한 줄 요약 (예: 전반적으로 차분하나 특정 구간에서 급격히 분노를 표출하여 선동 의심)"
        }}
        """
        
        try:
            response = await llm.generate_json(prompt)
            return response
        except Exception as e:
            logger.error(f"선동 분석 실패: {e}")
            return {"manipulation_score": 0, "unnaturalness_score": 0, "summary": "분석 실패"}
