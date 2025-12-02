"""
Google Cloud Vision API 기반 이미지 분석 모듈
- 썸네일 재사용 탐지 (Web Detection)
- 프레임 맥락 분석 (Label/Text Detection)
"""

import logging
import time
import requests
import asyncio
import os
from typing import List, Dict, Any, Optional
from google.cloud import vision
import cv2

from ..shared.schemas import Claim, VideoMeta
from .frame_sampler import FrameSampler
from ..shared.logger_utils import log_execution
from .schemas import ImageAnalysisRequest, ImageModuleResult, ClaimVerdict
from ..config import Config

logger = logging.getLogger(__name__)

class ImageAnalyzer:
    """
    Google Cloud Vision API를 사용하여 이미지의 조작 여부 및 맥락을 분석하는 클래스
    """

    def __init__(self):
        """ImageAnalyzer 초기화"""
        logger.info("ImageAnalyzer(Vision API) 초기화 시작...")
        
        # [중요 수정] Sampler는 API 키 여부와 상관없이 무조건 먼저 초기화
        # 이렇게 해야 Vision Client 초기화 실패 시에도 analyze 메서드에서 AttributeError가 안 남
        self.sampler = FrameSampler(max_frames=5) 

        # .env 설정 적용: 인증 파일 경로 환경변수 설정
        if Config.GOOGLE_APPLICATION_CREDENTIALS_PATH:
            key_path = Config.GOOGLE_APPLICATION_CREDENTIALS_PATH
            if not os.path.isabs(key_path):
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                key_path = os.path.join(base_dir, key_path)
            
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
            logger.info(f"Google Cloud 인증 경로 설정: {key_path}")

        try:
            self.vision_client = vision.ImageAnnotatorClient()
            logger.info("Google Cloud Vision API 클라이언트 로드 완료")
        except Exception as e:
            logger.error(f"Google Cloud Vision 클라이언트 초기화 실패: {e}")
            logger.warning("Google Cloud 자격 증명을 확인해주세요.")
            self.vision_client = None

    @log_execution(module_name="image", step_name="full_analysis")
    async def analyze(self, request: ImageAnalysisRequest) -> ImageModuleResult:
        """
        이미지 분석 수행 (썸네일 웹 탐지 + 프레임 라벨링)
        """
        start_time = time.time()
        logger.info(f"이미지 분석 시작: {request.video_id}")
        
        # [안전 장치] 클라이언트가 초기화되지 않았으면 빠른 실패 처리
        if not self.vision_client:
             return ImageModuleResult(
                modality="image",
                video_id=request.video_id,
                analysis_summary="Google Vision API 설정 오류로 분석을 수행할 수 없습니다.",
                claims=[],
                processing_time_ms=(time.time() - start_time) * 1000,
                status="error",
                error_message="Google Vision Client not initialized"
            )
        
        web_detection_result = {}
        frame_analysis_results = []
        summary = "분석 실패"

        try:
            # 1. 썸네일 URL 구성 및 분석 (Web Detection)
            thumbnail_url = f"https://img.youtube.com/vi/{request.video_id}/maxresdefault.jpg"
            web_detection_task = self._analyze_thumbnail_reuse(thumbnail_url)
            
            # 2. 프레임 샘플링 및 분석 (Context Analysis)
            video_meta = VideoMeta(
                video_id=request.video_id,
                url=f"https://www.youtube.com/watch?v={request.video_id}",
                title="" 
            )
            
            # 프레임 추출 (IO/CPU 작업이므로 별도 스레드 실행)
            loop = asyncio.get_running_loop()
            frames = await loop.run_in_executor(None, self.sampler.sample_frames, video_meta)
            frame_analysis_task = self._analyze_frames_context(frames)

            # 병렬 실행 및 결과 대기
            web_detection_result, frame_analysis_results = await asyncio.gather(
                web_detection_task, 
                frame_analysis_task
            )

            # 3. 결과 요약 생성
            summary = self._generate_module_summary(web_detection_result, frame_analysis_results)
            
            # 4. 결과 매핑 (모든 Claim에 동일한 이미지 증거 첨부)
            image_claims = []
            for claim in request.claims:
                image_claims.append(ClaimVerdict(
                    claim_id=claim.claim_id,
                    image_support_score=0.0, 
                    image_contradiction_score=0.0,
                    notes=[summary],
                    frames=frame_analysis_results
                ))

            processing_time = (time.time() - start_time) * 1000
            logger.info(f"이미지 분석 완료: {processing_time:.2f}ms")

            return ImageModuleResult(
                modality="image",
                video_id=request.video_id,
                analysis_summary=summary,
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

    async def _analyze_thumbnail_reuse(self, image_url: str) -> Dict[str, Any]:
        """썸네일이 웹 상의 다른 곳에서 사용되었는지 탐지"""
        try:
            content = await asyncio.to_thread(self._download_image, image_url)
            if not content:
                return {"error": "Thumbnail download failed"}

            image = vision.Image(content=content)
            response = await asyncio.to_thread(self.vision_client.web_detection, image=image)
            
            annotations = response.web_detection
            
            matching_pages = []
            if annotations.pages_with_matching_images:
                for page in annotations.pages_with_matching_images[:5]:
                    matching_pages.append({
                        "url": page.url,
                        "page_title": page.page_title
                    })
            
            return {
                "matching_pages_count": len(annotations.pages_with_matching_images),
                "matching_pages": matching_pages,
                "best_guess_labels": [label.label for label in annotations.best_guess_labels]
            }

        except Exception as e:
            logger.error(f"썸네일 분석 실패: {e}")
            return {"error": str(e)}

    async def _analyze_frames_context(self, frames: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """프레임 라벨 및 텍스트 탐지"""
        if not frames:
            return []

        results = []
        for frame in frames:
            try:
                success, encoded_image = cv2.imencode('.jpg', frame['image'])
                if not success: continue
                
                content = encoded_image.tobytes()
                image = vision.Image(content=content)
                
                features = [
                    vision.Feature(type_=vision.Feature.Type.LABEL_DETECTION),
                    vision.Feature(type_=vision.Feature.Type.TEXT_DETECTION),
                ]
                
                request = vision.AnnotateImageRequest(image=image, features=features)
                response = await asyncio.to_thread(self.vision_client.annotate_image, request=request)
                
                labels = [label.description for label in response.label_annotations[:5]]
                ocr_text = response.text_annotations[0].description if response.text_annotations else ""
                
                results.append({
                    "frame_id": frame['frame_id'],
                    "timestamp": frame['timestamp'],
                    "detected_labels": labels,
                    "detected_text": ocr_text.replace('\n', ' ')[:100]
                })

            except Exception as e:
                logger.warning(f"프레임 분석 실패: {e}")

        return results

    def _download_image(self, url: str) -> Optional[bytes]:
        try:
            resp = requests.get(url, timeout=10)
            return resp.content if resp.status_code == 200 else None
        except:
            return None

    def _generate_module_summary(self, web_data: Dict, frame_data: List[Dict]) -> str:
        summary_parts = []
        
        # 재사용 탐지 요약
        if "error" in web_data:
             summary_parts.append(f"웹 탐지 오류: {web_data['error']}")
        elif web_data.get("matching_pages_count", 0) > 0:
            urls = [p['url'] for p in web_data.get('matching_pages', [])]
            summary_parts.append(f"⚠️ [이미지 재사용 감지] 썸네일이 {web_data['matching_pages_count']}개의 외부 웹사이트에서 발견되었습니다.")
            summary_parts.append(f"  - 관련 URL: {', '.join(urls[:2])}...")
        else:
            summary_parts.append("✅ [이미지 재사용 미감지] 썸네일과 동일한 이미지가 웹에서 발견되지 않았습니다.")

        # 프레임 맥락 요약
        if frame_data:
            summary_parts.append(f"\n[프레임 시각/텍스트 분석]")
            for f in frame_data:
                ts = f"{f['timestamp']:.1f}초"
                labels = ", ".join(f['detected_labels'][:3])
                text = f"\"{f['detected_text'][:30]}...\"" if f['detected_text'] else "(텍스트 없음)"
                summary_parts.append(f"  - {ts}: [화면] {labels} vs [자막] {text}")

        return "\n".join(summary_parts)