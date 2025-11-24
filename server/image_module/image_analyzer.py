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

            # 2. 특징 추출 (병렬 처리)
            # asyncio.to_thread를 사용하여 CPU 바운드 작업(OCR, 임베딩)을 비동기적으로 실행
            loop = asyncio.get_running_loop()
            
            embedding_task = loop.run_in_executor(None, self.extractor.extract_embeddings, frames)
            ocr_task = loop.run_in_executor(None, self.extractor.extract_ocr, frames)
            
            embeddings, ocr_texts = await asyncio.gather(embedding_task, ocr_task)
            
            # 3. 자극성 및 불일치 분석 (LLM)
            combined_ocr = "\n".join([t for t in ocr_texts if t.strip()])
            
            if combined_ocr.strip():
                # [Branch A] 화면 내 텍스트 검출됨 -> 텍스트 기반 불일치/과장 분석
                logger.info("화면 텍스트 검출됨: 텍스트 기반 분석 수행")
                provocation_analysis = await self._analyze_provocation(combined_ocr, request.claims)
            else:
                # [Branch B] 텍스트 없음 -> 시각적 자극성만 분석 (Vision API)
                logger.info("화면 텍스트 없음: 시각적 자극성 분석 수행 (Vision API)")
                
                # CLIP 임베딩을 사용하여 Claim과 가장 관련성 높은 프레임 3장 선택
                # (단순히 앞 3장이 아니라, 의미적으로 중요한 프레임을 선별하여 비용/성능 최적화)
                selected_indices = self._select_top_frames(embeddings, request.claims)
                
                # Base64 이미지 변환 (선택된 프레임만)
                import base64
                import cv2
                base64_images = []
                
                for idx in selected_indices:
                    frame = frames[idx]
                    # 이미지를 JPG로 인코딩
                    _, buffer = cv2.imencode('.jpg', frame['image'])
                    b64 = base64.b64encode(buffer).decode('utf-8')
                    base64_images.append(b64)
                
                provocation_analysis = await self._analyze_visual_provocation(base64_images, request.claims)
            
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

    def _select_top_frames(self, frame_embeddings: List[Any], claims: List[Claim], top_k: int = 3) -> List[int]:
        """
        Claim과 가장 유사도가 높은 프레임의 인덱스를 반환합니다.
        """
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity
        
        if not frame_embeddings or not claims:
            return list(range(min(len(frame_embeddings), top_k)))
            
        try:
            # Claim 텍스트 임베딩
            claim_texts = [c.claim_text for c in claims]
            claim_embeddings = self.extractor.encode_text(claim_texts)
            
            if len(claim_embeddings) == 0:
                return list(range(min(len(frame_embeddings), top_k)))
                
            # 코사인 유사도 계산 (Frames x Claims)
            # frame_embeddings가 리스트라면 numpy array로 변환
            frame_embs_np = np.array(frame_embeddings)
            
            # 유사도 매트릭스: [num_frames, num_claims]
            similarities = cosine_similarity(frame_embs_np, claim_embeddings)
            
            # 각 프레임별로 가장 높은 유사도(Max Similarity)를 구함 (어떤 Claim이든 가장 관련성 높은 것)
            # [num_frames]
            max_similarities = np.max(similarities, axis=1)
            
            # 유사도 순으로 정렬하여 상위 K개 인덱스 추출
            # argsort는 오름차순이므로 뒤집어서 상위권 선택
            top_indices = np.argsort(max_similarities)[::-1][:top_k]
            
            # 시간 순서대로 정렬 (영상의 흐름 유지를 위해)
            top_indices.sort()
            
            logger.info(f"프레임 선별 완료: {top_indices} (유사도 기반)")
            return top_indices.tolist()
            
        except Exception as e:
            logger.error(f"프레임 선별 중 오류: {e}")
            # 오류 시 앞부분 반환
            return list(range(min(len(frame_embeddings), top_k)))

    async def _analyze_provocation(self, ocr_text: str, claims: List[Claim]) -> Dict[str, Any]:
        """
        OCR 텍스트와 주장을 비교하여 자극성 및 불일치를 분석합니다.
        """
        llm = await get_llm_client()
        
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
            response = await llm.chat_completion_json([{"role": "user", "content": prompt}])
            return response
        except Exception as e:
            logger.error(f"자극성 분석 실패: {e}")
            return {"provocation_score": 0, "inconsistency_score": 0, "summary": "분석 실패"}

    async def _analyze_visual_provocation(self, base64_images: List[str], claims: List[Claim]) -> Dict[str, Any]:
        """
        이미지만으로 시각적 자극성을 분석합니다.
        """
        llm = await get_llm_client()
        claim_texts = [c.claim_text for c in claims]
        
        return await llm.analyze_visual_provocation(base64_images, claim_texts)
