"""BbongGuard Backend API"""

import logging
import asyncio
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .shared.schemas import (
    VideoMeta, 
    Claim 
)
from .shared.text_module import (
    TextAnalysisRequest,
)
from .shared.multimodal_result import (
    MultiModalAnalysisResult,
    FinalVerdict
)
from .text_module.text_analyzer import TextAnalyzer
from .image_module.image_analyzer import ImageAnalyzer
from .audio_module.audio_analyzer import AudioAnalyzer
from .text_module.verdict_agent import VerdictAgent
from .image_module.schemas import ImageAnalysisRequest, ImageModuleResult, ClaimVerdict as ImageClaimVerdict
from .audio_module.schemas import AudioAnalysisRequest, AudioModuleResult, ClaimVerdict as AudioClaimVerdict
from fastapi.responses import StreamingResponse
import json

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="BbongGuard Inference Server",
    description="YouTube Fake News Detection API (Multimodal)",
    version="0.2.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 모듈 인스턴스 (싱글톤)
text_analyzer = TextAnalyzer()
image_analyzer = ImageAnalyzer()
audio_analyzer = AudioAnalyzer()
verdict_agent = VerdictAgent()


@app.post("/api/analyze-multimodal")
async def analyze_video_multimodal(request: TextAnalysisRequest):
    """
    멀티모달(텍스트+이미지+오디오) 분석 엔드포인트. (Streaming)
    
    진행 상황을 실시간으로 스트리밍(NDJSON)하며, 텍스트/이미지/오디오 모듈을 병렬로 실행합니다.

    Args:
        request (TextAnalysisRequest): 분석할 영상의 메타데이터 (ID, 제목, 설명 등).

    Returns:
        StreamingResponse: NDJSON 형식의 진행 상황 및 최종 분석 결과 스트림.

    Raises:
        HTTPException: 분석 중 예기치 못한 오류 발생 시 500 에러 포맷의 스트림 메시지 전송.
    """
    async def analyze_generator():
        start_time = time.time()
        try:
            # 초기 상태 전송
            yield json.dumps({"type": "progress", "message": "분석 요청 수신 및 작업 준비 중..."}) + "\n"
            logger.info(f"멀티모달 분석 요청 수신: {request.video_id}")
            
            # Helper: 진행 상황 추적을 위한 래퍼 함수
            async def run_with_id(task_id: str, coro):
                """
                비동기 작업에 ID를 부여하여 실행합니다.

                Args:
                    task_id (str): 작업 식별 ID (예: 'text', 'image').
                    coro (Coroutine): 실행할 비동기 코루틴.

                Returns:
                    tuple: (task_id, result) 튜플.
                """
                try:
                    return task_id, await coro
                except Exception as e:
                    return task_id, e

            # ========================================
            # Phase 1: Audio 먼저 실행 (STT transcript 획득)
            # ========================================
            yield json.dumps({"type": "progress", "message": "오디오 분석 중 (STT 변환)..."}) + "\n"
            
            audio_request = AudioAnalysisRequest(
                video_id=request.video_id, 
                title=request.title,
                description=request.description,
                claims=[], 
                transcript=request.transcript  # 이미 있으면 재활용
            )
            
            try:
                audio_result = await audio_analyzer.analyze(audio_request)
                transcript_from_audio = audio_result.transcript if audio_result and hasattr(audio_result, 'transcript') else None
                logger.info(f"Audio 분석 완료, transcript 길이: {len(transcript_from_audio) if transcript_from_audio else 0}")
            except Exception as e:
                logger.error(f"Audio 분석 실패: {e}")
                audio_result = None
                transcript_from_audio = None

            yield json.dumps({"type": "progress", "message": "오디오(스크립트) 분석 완료"}) + "\n"

            # ========================================
            # Phase 2: Text/Image 병렬 실행 (Audio의 transcript 활용)
            # ========================================
            yield json.dumps({"type": "progress", "message": "텍스트/이미지 분석 중..."}) + "\n"
            
            # Audio의 transcript를 Text 모듈에 전달 (중복 STT 방지)
            if transcript_from_audio and not request.transcript:
                request.transcript = transcript_from_audio
                logger.info("Audio의 STT 결과를 Text 모듈에 전달")
            
            text_coro = text_analyzer.analyze(request)
            
            image_request = ImageAnalysisRequest(
                video_id=request.video_id,
                claims=[], 
                title=request.title
            )
            image_coro = image_analyzer.analyze(image_request)

            # Text/Image 병렬 실행
            tasks = [
                run_with_id("text", text_coro),
                run_with_id("image", image_coro),
            ]
            
            results = {"audio": audio_result}  # Audio 결과 미리 저장
            for future in asyncio.as_completed(tasks):
                task_id, result = await future
                
                module_names = {"text": "텍스트(팩트체크)", "image": "이미지(썸네일)"}
                yield json.dumps({
                    "type": "progress", 
                    "message": f"{module_names.get(task_id, task_id)} 분석 완료"
                }) + "\n"
                
                results[task_id] = result

            # 결과 추출
            text_result = results.get("text")
            image_result = results.get("image")
            audio_result = results.get("audio")

            # 3. 결과 통합 및 최종 판정
            yield json.dumps({"type": "progress", "message": "최종 결과 통합 및 판정 중..."}) + "\n"

            # 텍스트 모듈 실패 시 중단
            if isinstance(text_result, Exception) or not text_result:
                error_msg = str(text_result) if text_result else "Text Analysis Failed"
                logger.error(f"Text Module Error: {error_msg}")
                yield json.dumps({"type": "error", "message": f"핵심 분석(텍스트) 실패: {error_msg}"}) + "\n"
                return

            # VideoMeta 생성
            video_meta = VideoMeta(
                video_id=request.video_id,
                url=f"https://www.youtube.com/watch?v={request.video_id}",
                duration_sec=request.duration_sec,
                transcript=[],
                published_at=request.published_at
            )

            # Claims 변환
            claims = []
            for cv in text_result.claims:
                claims.append(Claim(
                    claim_id=cv.claim_id,
                    claim_text=cv.claim_text,
                    category=cv.category,
                    importance="High"
                ))
            
            # 비정보성 영상 예외 처리 (Claims 없음)
            if not claims:
                logger.info("추출된 주장이 없음 - 비정보성 영상으로 간주")
                final_result = MultiModalAnalysisResult(
                    video_id=request.video_id,
                    text_result=text_result,
                    final_verdict=FinalVerdict(
                        is_fake_news=False,
                        confidence_level="low",
                        overall_reasoning="정보성 영상이 아니거나, 검증할 만한 핵심 주장이 발견되지 않았습니다.",
                        recommendation="이 영상은 팩트체크 대상이 아닐 수 있습니다."
                    )
                )
                logger.info("비정보성 영상 결과 객체 생성 완료, yield 시작")
                result_json = json.dumps({"type": "result", "data": final_result.model_dump()})
                logger.info(f"비정보성 영상 결과 JSON 길이: {len(result_json)}")
                yield result_json + "\n"
                logger.info("비정보성 영상 결과 yield 완료")
                return

            # 이미지/오디오 결과 핸들링 (에러 시 기본값)
            if isinstance(image_result, Exception):
                logger.error(f"Image Module Error: {image_result}")
                image_result = ImageModuleResult(
                    video_id=request.video_id, 
                    analysis_summary="이미지 분석 실패", 
                    claims=[], 
                    status="error"
                )
            
            if isinstance(audio_result, Exception):
                logger.error(f"Audio Module Error: {audio_result}")
                audio_result = AudioModuleResult(
                    video_id=request.video_id, 
                    analysis_summary="오디오 분석 실패", 
                    claims=[], 
                    status="error"
                )

            # Claims 주입 (Cross-modal Mapping)
            # 이미지
            image_result.claims = [
                ImageClaimVerdict(
                    claim_id=c.claim_id,
                    image_support_score=0.0,
                    image_contradiction_score=image_result.overall_contradiction_score,
                    notes=[image_result.analysis_summary],
                    frames=image_result.frames
                ) for c in claims
            ]
            
            # 오디오
            audio_result.claims = [
                AudioClaimVerdict(
                    claim_id=c.claim_id,
                    audio_support_score=0.0,
                    notes=[audio_result.analysis_summary],
                    segments=[]
                ) for c in claims
            ]

            # 4. 최종 Verdict Agent 호출
            final_verdict = await verdict_agent.aggregate_multimodal_verdicts(
                video_meta=video_meta,
                claims=claims,
                text_verdicts=text_result.claims,
                image_results=image_result.model_dump(),
                audio_results=audio_result.model_dump()
            )

            result_obj = MultiModalAnalysisResult(
                video_id=request.video_id,
                text_result=text_result,
                image_result=image_result,
                audio_result=audio_result,
                final_verdict=final_verdict,
                total_processing_time_ms=(time.time() - start_time) * 1000
            )

            # 최종 결과 전송
            yield json.dumps({"type": "result", "data": result_obj.model_dump()}) + "\n"

        except Exception as e:
            logger.error(f"분석 중 오류 발생: {e}", exc_info=True)
            yield json.dumps({"type": "error", "message": f"분석 중 오류 발생: {str(e)}"}) + "\n"

    return StreamingResponse(analyze_generator(), media_type="application/x-ndjson")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)