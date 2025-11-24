"""BbongGuard Backend API"""

import logging
import os
import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .shared.schemas import (
    VideoMeta, 
    Claim, 
    HealthResponse, 
    ErrorResponse
)
from .shared.rag_models import (
    TextAnalysisRequest,
    TextModuleResult,
    MultiModalAnalysisResult,
    FinalVerdict
)
from .text_module.text_analyzer import TextAnalyzer
from .image_module.image_analyzer import ImageAnalyzer
from .audio_module.audio_analyzer import AudioAnalyzer
from .text_module.verdict_agent import VerdictAgent
from .image_module.schemas import ImageAnalysisRequest
from .audio_module.schemas import AudioAnalysisRequest

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
    allow_origins=["*"],  # 실제 배포 시에는 구체적인 도메인으로 제한 권장
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 모듈 인스턴스 (싱글톤처럼 사용)
text_analyzer = TextAnalyzer()
image_analyzer = ImageAnalyzer()
audio_analyzer = AudioAnalyzer()
verdict_agent = VerdictAgent()


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """서버 상태 확인"""
    return HealthResponse(status="ok", version="0.2.0")


@app.post("/api/analyze-rag", response_model=TextModuleResult)
async def analyze_video_text(request: TextAnalysisRequest):
    """
    (Legacy) 텍스트 기반 RAG 분석 엔드포인트
    """
    try:
        logger.info(f"텍스트 분석 요청 수신: {request.video_id}")
        result = await text_analyzer.analyze(request)
        return result
    except Exception as e:
        logger.error(f"텍스트 분석 중 오류 발생: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze-multimodal", response_model=MultiModalAnalysisResult)
async def analyze_video_multimodal(request: TextAnalysisRequest):
    """
    멀티모달(텍스트+이미지+오디오) 분석 엔드포인트
    """
    try:
        logger.info(f"멀티모달 분석 요청 수신: {request.video_id}")
        
        # 1. 텍스트 모듈 실행 (Claim 추출 및 1차 팩트체크)
        # 이미지/오디오 모듈은 Claim이 필요하므로 텍스트 모듈이 먼저 실행되어야 함
        # (최적화를 위해 Claim 추출만 먼저 하고 병렬 처리할 수도 있으나, 여기서는 순차 진행 후 병렬)
        
        text_result = await text_analyzer.analyze(request)
        
        # VideoMeta 및 Claims 변환
        video_meta = VideoMeta(
            video_id=request.video_id,
            url=f"https://www.youtube.com/watch?v={request.video_id}",
            duration_sec=request.duration_sec,  # 영상 길이 설정
            transcript=[{'text': request.transcript, 'start': 0, 'end': 0, 'duration': 0}] if request.transcript else []
            # 주의: request.transcript가 단순 문자열이라 상세 타임스탬프 정보가 없을 수 있음.
            # 실제로는 YouTube API에서 상세 자막을 받아와야 함.
        )
        
        # TextAnalyzer 결과에서 Claims 복원 (ClaimVerdict -> Claim)
        claims = []
        for cv in text_result.claims:
            claims.append(Claim(
                claim_id=cv.claim_id,
                claim_text=cv.claim_text,
                category=cv.category,
                importance="High" # 기본값
            ))
            
        if not claims:
            logger.info("추출된 주장이 없어 멀티모달 분석을 중단합니다.")
            return MultiModalAnalysisResult(
                video_id=request.video_id,
                text_result=text_result,
                final_verdict=FinalVerdict(
                    is_fake_news=False,
                    confidence_level="low",
                    overall_reasoning="분석할 주장이 발견되지 않았습니다.",
                    recommendation="영상 내용이 불충분하거나 분석할 수 없습니다."
                )
            )

        # 2. 이미지/오디오 모듈 병렬 실행
        # 오디오 파일 경로가 없으므로 오디오 모듈은 자막 분석 위주로 동작하거나, 내부에서 다운로드 시도
        
        image_request = ImageAnalysisRequest(video_id=request.video_id, claims=claims)
        audio_request = AudioAnalysisRequest(video_id=request.video_id, claims=claims)
        
        # 비동기 병렬 실행
        image_task = asyncio.create_task(image_analyzer.analyze(image_request))
        audio_task = asyncio.create_task(audio_analyzer.analyze(audio_request))
        
        image_result, audio_result = await asyncio.gather(image_task, audio_task)
        
        # 3. 최종 통합 판단
        final_verdict = await verdict_agent.aggregate_multimodal_verdicts(
            video_meta=video_meta,
            claims=claims,
            text_verdicts=text_result.claims,
            image_results=image_result.model_dump(),
            audio_results=audio_result.model_dump()
        )
        
        return MultiModalAnalysisResult(
            video_id=request.video_id,
            text_result=text_result,
            image_result=image_result,
            audio_result=audio_result,
            final_verdict=final_verdict
        )

    except Exception as e:
        logger.error(f"멀티모달 분석 중 오류 발생: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
