"""이미지 분석 파이프라인 Orchestrator"""

import logging
import time
from typing import List, Dict, Any

from ..shared.schemas import VideoMeta, Claim
from .frame_sampler import FrameSampler
from .feature_extractor import ImageFeatureExtractor
from ..shared.logger_utils import log_execution
from .schemas import ImageAnalysisRequest, ImageModuleResult, ClaimVerdict
from ..shared.llm_client import get_llm_client

logger = logging.getLogger(__name__)

class ImageAnalyzer:
    """이미지 모듈 전체 파이프라인을 실행하는 클래스"""

    def __init__(self):
        """ImageAnalyzer 초기화 및 하위 컴포넌트 로드"""
        logger.info("ImageAnalyzer 초기화 시작...")
        try:
            self.sampler = FrameSampler()
            self.extractor = ImageFeatureExtractor()
            # self.matcher = ImageClaimMatcher() # 더 이상 사용 안 함
            # self.summarizer = ImageLLMSummarizer() # 더 이상 사용 안 함
            logger.info("ImageAnalyzer 초기화 완료")
        except Exception as e:
            logger.error(f"ImageAnalyzer 초기화 실패: {e}")
            raise

    @log_execution(module_name="image", step_name="full_analysis")
    async def analyze(self, request: ImageAnalysisRequest) -> ImageModuleResult:
        """
        이미지 분석을 수행합니다. (자극성 및 불일치 탐지)
        """
        start_time = time.time()
        logger.info(f"이미지 분석 시작: {request.video_id}")

        try:
            # 1. 프레임 샘플링 (0-9 지점 스트리밍)
            # FrameSampler는 매 요청마다 생성하지 않고 self.sampler 사용 가능하지만,
            # 상태가 없다면 매번 생성해도 무방. 여기선 self.sampler 사용.
            
            video_meta = VideoMeta(
                video_id=request.video_id,
                url=f"https://www.youtube.com/watch?v={request.video_id}",
                transcript=[], 
                description=""
            )
            
            frames = self.sampler.sample_frames(video_meta)

            if not frames:
                logger.error("프레임 추출 실패")
                return ImageModuleResult(
                    modality="image",
                    video_id=request.video_id,
                    analysis_summary="이미지 분석을 수행할 수 없습니다 (프레임 추출 실패).",
                    claims=[],
                    processing_time_ms=(time.time() - start_time) * 1000,
                    status="error",
                )

            # 2. 특징 추출 (OCR)
            processed_frames = self.extractor.extract(frames)
            
            # 3. 자극성 및 불일치 분석 (LLM)
            ocr_texts = [f.get('ocr_text', '') for f in processed_frames if f.get('ocr_text')]
            combined_ocr = "\n".join(ocr_texts)
            
            provocation_analysis = await self._analyze_provocation(combined_ocr, request.claims)
            
            # 결과 매핑
            image_claims = []
            for claim in request.claims:
                image_claims.append(ClaimVerdict(
                    claim_id=claim.claim_id,
                    image_support_score=0.0,
                    image_contradiction_score=0.0,
                    notes=[provocation_analysis['summary']],
                    frames=[] 
                ))

            processing_time = (time.time() - start_time) * 1000
            logger.info(f"이미지 분석 완료: {processing_time:.2f}ms")

            return ImageModuleResult(
                modality="image",
                video_id=request.video_id,
                analysis_summary=provocation_analysis['summary'],
                claims=image_claims,
                processing_time_ms=processing_time,
                status="success",
            )

        except Exception as e:
            logger.error(f"이미지 분석 중 오류: {e}", exc_info=True)
            return ImageModuleResult(
                modality="image",
                video_id=request.video_id,
                analysis_summary=f"오류 발생: {str(e)}",
                claims=[],
                processing_time_ms=(time.time() - start_time) * 1000,
                status="error",
                error_message=str(e)
            )

    async def _analyze_provocation(self, ocr_text: str, claims: List[Claim]) -> Dict[str, Any]:
        """
        OCR 텍스트와 주장을 비교하여 자극성 및 불일치를 분석합니다.
        """
        llm = get_llm_client()
        
        claim_texts = "\n".join([f"- {c.claim_text}" for c in claims])
        
        prompt = f"""
        다음은 유튜브 영상의 화면에서 추출한 텍스트(OCR)와 영상의 핵심 주장입니다.
        화면 텍스트가 시청자를 유인하기 위해 지나치게 자극적이거나, 실제 주장과 다르게 과장되었는지(낚시성) 분석해주세요.

        [화면 텍스트 (OCR)]
        {ocr_text}

        [핵심 주장]
        {claim_texts}

        분석 기준:
        1. 자극성 (Provocation): 0~10점. (10: 매우 자극적/충격적 단어 사용)
        2. 불일치 (Inconsistency): 0~10점. (10: 내용과 전혀 다른 낚시성 텍스트)
        
        결과를 JSON 형식으로 반환해주세요:
        {{
            "provocation_score": int,
            "inconsistency_score": int,
            "summary": "한 줄 요약 (예: 화면 텍스트는 '충격', '경악' 등의 단어를 사용하여 자극적이나 내용은 평이함)"
        }}
        """
        
        try:
            response = await llm.generate_json(prompt)
            return response
        except Exception as e:
            logger.error(f"자극성 분석 실패: {e}")
            return {"provocation_score": 0, "inconsistency_score": 0, "summary": "분석 실패"}
