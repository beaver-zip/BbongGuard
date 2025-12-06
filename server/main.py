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


@app.post("/api/analyze-multimodal", response_model=MultiModalAnalysisResult)
async def analyze_video_multimodal(request: TextAnalysisRequest):
    """
    멀티모달(텍스트+이미지+오디오) 분석 엔드포인트.

    텍스트, 이미지, 오디오 모듈을 병렬로 실행하여 유튜브 영상의 가짜뉴스 여부를 판단합니다.
    
    Args:
        request (TextAnalysisRequest): 분석할 영상의 메타데이터 (ID, 제목, 설명 등).

    Returns:
        MultiModalAnalysisResult: 각 모듈의 분석 결과 및 최종 판결.

    Raises:
        HTTPException: 분석 중 오류 발생 시 500 에러 반환.
    """
    start_time = time.time()
    try:
        logger.info(f"멀티모달 분석 요청 수신: {request.video_id}")
        
        # 1. 병렬 실행을 위한 Task 생성
        # 텍스트 분석 (가장 오래 걸림)
        text_task = asyncio.create_task(text_analyzer.analyze(request))

        # 이미지 분석 (Claims 없이 1차 분석: 다운로드, OCR, Vision)
        image_request = ImageAnalysisRequest(
            video_id=request.video_id,
            claims=[], # 초기에는 Claim 없음
            title=request.title
        )
        image_task = asyncio.create_task(image_analyzer.analyze(image_request))

        # 오디오 분석 (Claims 없이 1차 분석: 다운로드, STT, 낚시 탐지)
        audio_request = AudioAnalysisRequest(
            video_id=request.video_id, 
            title=request.title,
            description=request.description,
            claims=[], # 초기에는 Claim 없음
            transcript=request.transcript # 있으면 재활용
        )
        audio_task = asyncio.create_task(audio_analyzer.analyze(audio_request))

        # 2. 모든 모듈 병렬 대기
        logger.info("모듈 병렬 실행 시작 (Text, Image, Audio)")
        results = await asyncio.gather(text_task, image_task, audio_task, return_exceptions=True)
        
        text_result = results[0]
        image_result = results[1]
        audio_result = results[2]

        # 3. 결과 처리 및 통합
        
        # 텍스트 결과 확인
        if isinstance(text_result, Exception):
            logger.error(f"텍스트 모듈 실패: {text_result}")
            raise HTTPException(status_code=500, detail=f"Text Module Failed: {text_result}")
            
        # VideoMeta 생성
        video_meta = VideoMeta(
            video_id=request.video_id,
            url=f"https://www.youtube.com/watch?v={request.video_id}",
            duration_sec=request.duration_sec,
            transcript=[] 
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

        if not claims:
            logger.info("추출된 주장이 없어 멀티모달 분석을 중단합니다.")
            return MultiModalAnalysisResult(
                video_id=request.video_id,
                text_result=text_result,
                final_verdict=FinalVerdict(
                    is_fake_news=False,
                    confidence_level="low",
                    overall_reasoning="분석할 주장이 발견되지 않았습니다.",
                    recommendation="정보가 부족하여 판단을 유보합니다."
                )
            )

        # 이미지 결과 통합 (Claims 주입)
        if isinstance(image_result, Exception):
            logger.error(f"이미지 모듈 실패: {image_result}")
            image_result = ImageModuleResult(
                video_id=request.video_id,
                analysis_summary="이미지 분석 중 오류가 발생했습니다.",
                claims=[],
                processing_time_ms=0,
                status="error",
                error_message=str(image_result)
            )
        else:
            # 텍스트에서 추출된 Claims를 이미지 결과에 매핑
            image_claims = []
            for claim in claims:
                image_claims.append(ImageClaimVerdict(
                    claim_id=claim.claim_id,
                    image_support_score=0.0,
                    image_contradiction_score=image_result.overall_contradiction_score,
                    notes=[image_result.analysis_summary],
                    frames=image_result.frames
                ))
            image_result.claims = image_claims

        # 오디오 결과 통합 (Claims 주입)
        if isinstance(audio_result, Exception):
             logger.error(f"오디오 모듈 실패: {audio_result}")
             audio_result = AudioModuleResult(
                video_id=request.video_id,
                analysis_summary="오디오 분석 중 오류가 발생했습니다.",
                claims=[],
                processing_time_ms=0,
                status="error",
                error_message=str(audio_result)
            )
        else:
            # 텍스트에서 추출된 Claims를 오디오 결과에 매핑
            audio_claims = []
            for claim in claims:
                audio_claims.append(AudioClaimVerdict(
                    claim_id=claim.claim_id,
                    audio_support_score=0.0,
                    notes=[audio_result.analysis_summary],
                    segments=[]
                ))
            audio_result.claims = audio_claims

        # 4. 최종 통합 판단 (Verdict Agent)
        final_verdict = await verdict_agent.aggregate_multimodal_verdicts(
            video_meta=video_meta,
            claims=claims,
            text_verdicts=text_result.claims,
            image_results=image_result.model_dump(),
            audio_results=audio_result.model_dump()
        )
        
        result = MultiModalAnalysisResult(
            video_id=request.video_id,
            text_result=text_result,
            image_result=image_result,
            audio_result=audio_result,
            final_verdict=final_verdict
        )
        
        end_time = time.time()
        result.total_processing_time_ms = (end_time - start_time) * 1000
        return result

    except Exception as e:
        logger.error(f"멀티모달 분석 중 오류 발생: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)