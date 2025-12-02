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


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """서버 상태 확인"""
    return HealthResponse(status="ok", version="0.2.0")


@app.post("/api/analyze-rag", response_model=TextModuleResult)
async def analyze_video_text(request: TextAnalysisRequest):
    """(Legacy) 텍스트 기반 RAG 분석 엔드포인트"""
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
        # RAG 시스템이 핵심 주장을 먼저 추출해야 다른 모듈이 검증할 수 있습니다.
        text_result = await text_analyzer.analyze(request)
        
        # VideoMeta 생성 (메타데이터용)
        video_meta = VideoMeta(
            video_id=request.video_id,
            url=f"https://www.youtube.com/watch?v={request.video_id}",
            duration_sec=request.duration_sec,
            transcript=[] # 자막은 TextAnalyzer 내부에서 처리하므로 여기선 생략 가능
        )
        
        # TextAnalyzer 결과에서 Claims 추출 및 변환
        claims = []
        for cv in text_result.claims:
            claims.append(Claim(
                claim_id=cv.claim_id,
                claim_text=cv.claim_text,
                category=cv.category,
                importance="High"
            ))
            
        if not claims:
            logger.info("추출된 주장이 없어 멀티모달 분석을 중단합니다.")
            return MultiModalAnalysisResult(
                video_id=request.video_id,
                text_result=text_result,
                final_verdict=FinalVerdict(
                    is_fake_news=False,
                    confidence_level="low",
                    overall_reasoning="분석할 주장이 발견되지 않았습니다. (영상 설명이나 자막이 부족할 수 있습니다)",
                    recommendation="정보가 부족하여 판단을 유보합니다."
                )
            )

        # 2. 이미지/오디오 모듈 병렬 실행
        # 각 모듈에 필요한 요청 객체 생성
        image_request = ImageAnalysisRequest(
            video_id=request.video_id, 
            claims=claims
        )
        
        audio_request = AudioAnalysisRequest(
            video_id=request.video_id, 
            title=request.title,  # [New] 제목 낚시 탐지용
            claims=claims
        )
        
        # 비동기 병렬 실행 (Image: Google Vision, Audio: Naver Cloud)
        image_task = asyncio.create_task(image_analyzer.analyze(image_request))
        audio_task = asyncio.create_task(audio_analyzer.analyze(audio_request))
        
        image_result, audio_result = await asyncio.gather(image_task, audio_task)
        
        # 3. 최종 통합 판단 (Verdict Agent)
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