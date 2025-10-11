"""
BbongGuard 추론 서버 - FastAPI 애플리케이션
Chrome Extension과 통신하여 YouTube 영상 가짜뉴스 분석
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import logging
import sys

from .config import Config
from .models import (
    AnalyzeRequest,
    AnalyzeResponse,
    ErrorResponse,
    HealthResponse,
    PredictionDetails
)
from .inference import get_inference_engine, InferenceEngine

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(
    title="BbongGuard Inference Server",
    description="YouTube 가짜뉴스 탐지 API",
    version="1.0.0"
)

# CORS 설정 (Chrome Extension 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 origin만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """서버 시작 시 실행"""
    logger.info("="*70)
    logger.info("BbongGuard 추론 서버 시작")
    logger.info("="*70)

    # 설정 출력
    Config.print_config()

    # 설정 검증
    errors = Config.validate()
    if errors:
        logger.error("설정 오류:")
        for error in errors:
            logger.error(f"  - {error}")
        logger.error("\n모델 파일을 server/models/ 디렉토리에 배치해주세요.")
        sys.exit(1)

    # 추론 엔진 초기화 (모델 로딩)
    try:
        engine = get_inference_engine()
        if not engine.is_ready():
            raise RuntimeError("추론 엔진 초기화 실패")
        logger.info("✓ 추론 엔진 준비 완료")
    except Exception as e:
        logger.error(f"추론 엔진 초기화 실패: {e}")
        sys.exit(1)

    logger.info("="*70)
    logger.info(f"서버 준비 완료: http://{Config.HOST}:{Config.PORT}")
    logger.info("="*70)


@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 실행"""
    logger.info("서버 종료 중...")


@app.get("/", tags=["Root"])
async def root():
    """루트 엔드포인트"""
    return {
        "message": "BbongGuard Inference Server",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check(engine: InferenceEngine = Depends(get_inference_engine)):
    """
    서버 상태 확인

    Chrome Extension의 inference-api.js에서 checkServerHealth()로 호출됨
    """
    try:
        is_ready = engine.is_ready()

        if is_ready:
            return HealthResponse(
                status="healthy",
                message="서버가 정상 작동 중입니다",
                models_loaded=True,
                doc2vec_loaded=engine.doc2vec_loaded,
                cnn_loaded=engine.cnn_loaded,
                errors=[]
            )
        else:
            return HealthResponse(
                status="unhealthy",
                message="모델 로딩에 문제가 있습니다",
                models_loaded=False,
                doc2vec_loaded=engine.doc2vec_loaded,
                cnn_loaded=engine.cnn_loaded,
                errors=["일부 모델이 로딩되지 않았습니다"]
            )

    except Exception as e:
        logger.error(f"Health check 실패: {e}")
        return HealthResponse(
            status="unhealthy",
            message="서버 상태 확인 실패",
            models_loaded=False,
            doc2vec_loaded=False,
            cnn_loaded=False,
            errors=[str(e)]
        )


@app.post("/api/analyze", response_model=AnalyzeResponse, tags=["Analysis"])
async def analyze_video(
    request: AnalyzeRequest,
    engine: InferenceEngine = Depends(get_inference_engine)
):
    """
    YouTube 영상 가짜뉴스 분석

    Chrome Extension의 inference-api.js에서 analyzeWithInferenceServer()로 호출됨

    Args:
        request: 영상 정보 (videoId, title, description, comments, relatedVideos)

    Returns:
        분석 결과 (prediction, fakeProbability, confidence, details)
    """
    try:
        logger.info(f"분석 요청 수신: {request.videoId}")

        # 추론 엔진 상태 확인
        if not engine.is_ready():
            raise HTTPException(
                status_code=503,
                detail="추론 엔진이 준비되지 않았습니다"
            )

        # 요청 데이터를 dict로 변환
        video_data = request.model_dump()

        # 추론 수행
        result = engine.predict(video_data)

        # 응답 생성
        response = AnalyzeResponse(
            success=True,
            videoId=request.videoId,
            prediction=result['prediction'],
            fakeProbability=result['fakeProbability'],
            confidence=result['confidence'],
            evidence=None,  # 필요시 구현
            details=PredictionDetails(**result['details'])
        )

        logger.info(
            f"분석 완료: {request.videoId} -> {result['prediction']} "
            f"(신뢰도: {result['confidence']*100:.2f}%)"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"분석 중 오류 발생: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"분석 중 오류가 발생했습니다: {str(e)}"
        )


# 개발 환경에서 직접 실행
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server.main:app",
        host=Config.HOST,
        port=Config.PORT,
        reload=True,
        log_level="info"
    )