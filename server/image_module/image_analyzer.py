"""
Google Cloud Vision API + Video Intelligence API 기반 이미지 분석 모듈
- 썸네일 TEXT_DETECTION (OCR 기반 낚시성 탐지)
- 영상 전체 Label Detection (내용 불일치 탐지)
"""

import logging
import time
import requests
import asyncio
import os
import tempfile
import yt_dlp
import re
from typing import List, Dict, Any, Optional
from google.cloud import vision


from ..shared.schemas import Claim
from ..shared.logger_utils import log_execution
from .schemas import ImageAnalysisRequest, ImageModuleResult, ClaimVerdict
from ..shared.llm_client import get_llm_client
from ..resources.prompts import get_thumbnail_analysis_prompt
from ..resources.keywords import CLICKBAIT_KEYWORDS

logger = logging.getLogger(__name__)


class ImageAnalyzer:
    """
    Google Cloud Vision API + Video Intelligence API를 사용하여
    썸네일 낚시성 및 영상 내용 불일치를 분석하는 클래스
    """

    def __init__(self):
        """ImageAnalyzer 초기화"""
        logger.info("ImageAnalyzer(Google Vision + GPT-4o-mini) 초기화 시작...")
        
        # Google Cloud Vision 클라이언트 초기화
        try:
            from ..config import Config
            if Config.GOOGLE_APPLICATION_CREDENTIALS_PATH:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = Config.GOOGLE_APPLICATION_CREDENTIALS_PATH
                logger.info(f"Google Cloud Credentials 설정: {Config.GOOGLE_APPLICATION_CREDENTIALS_PATH}")

            self.vision_client = vision.ImageAnnotatorClient()
            logger.info("Google Cloud Vision API 연결 성공")
        except Exception as e:
            logger.error(f"Google Cloud Vision API 연결 실패: {e}")
            self.vision_client = None



    @log_execution(module_name="image", step_name="full_analysis")
    async def analyze(self, request: ImageAnalysisRequest) -> ImageModuleResult:
        """
        이미지 분석 수행 (썸네일 TEXT_DETECTION + 영상 전체 분석)
        """
        start_time = time.time()
        logger.info(f"이미지 분석 시작: {request.video_id}")

        # [안전 장치] 클라이언트가 초기화되지 않았으면 빠른 실패 처리
        if not self.vision_client:
             return ImageModuleResult(
                modality="image",
                video_id=request.video_id,
                analysis_summary="Google Cloud API 설정 오류로 분석을 수행할 수 없습니다.",
                claims=[],
                processing_time_ms=(time.time() - start_time) * 1000,
                status="error",
                error_message="Google Cloud Client not initialized"
            )

        thumbnail_text_result = {}
        video_analysis_result = {}
        summary = "분석 실패"
        temp_video_path = None

        try:
            # 1. 썸네일 TEXT_DETECTION (Vision API OCR)
            thumbnail_url = f"https://img.youtube.com/vi/{request.video_id}/maxresdefault.jpg"
            logger.info("Step 1/3: 썸네일 TEXT_DETECTION 분석 중...")
            
            try:
                thumbnail_text_result = await self._analyze_thumbnail_text(thumbnail_url)
            except Exception as e:
                logger.warning(f"썸네일 텍스트 추출 실패: {e}")
                thumbnail_text_result = {"error": str(e)}

            # 2. 썸네일 2단계 분석
            text_size_ratio = thumbnail_text_result.get("text_size_ratio", 0.0)

            if thumbnail_text_result.get("error"):
                # TEXT_DETECTION 실패 시
                thumbnail_analysis = {
                    "stage": "error",
                    "is_fake": False,
                    "reason": f"썸네일 분석 실패: {thumbnail_text_result['error']}"
                }
            else:
                # Stage 1: OCR 기반 1차 필터링
                keyword_check = self._check_clickbait_keywords(
                    thumbnail_text_result.get("extracted_text", "")
                )

                # 규칙: 텍스트 20% 미만이고 키워드 없으면 통과
                if text_size_ratio < 0.2 and not keyword_check["has_clickbait"]:
                    logger.info("✅ Stage 1 통과: 썸네일 정상 (텍스트 적음 + 키워드 없음)")
                    thumbnail_analysis = {
                        "stage": "stage1_pass",
                        "is_fake": False,
                        "text_size_ratio": text_size_ratio,
                        "matched_keywords": [],
                        "reason": "텍스트 면적 20% 미만, 자극적 키워드 없음"
                    }
                # 텍스트 20% 이상이고 키워드 있으면 Stage 2 진행
                elif text_size_ratio >= 0.2 and keyword_check["has_clickbait"]:
                    logger.info("⚠️  Stage 1 의심 → Stage 2 GPT Vision 분석 수행")
                    vision_result = await self._analyze_thumbnail_with_vision(
                        thumbnail_url,
                        thumbnail_text_result.get("extracted_text", ""),
                        keyword_check["matched_keywords"]
                    )
                    thumbnail_analysis = {
                        "stage": "stage2_vision",
                        "is_fake": vision_result.get("fake_news_rating", "Safe") in ["Danger", "Warning"],
                        "text_size_ratio": text_size_ratio,
                        "matched_keywords": keyword_check["matched_keywords"],
                        "vision_analysis": vision_result,
                        "reason": vision_result.get("reason", "GPT Vision 분석 완료")
                    }
                else:
                    # 중간 케이스: 텍스트는 많지만 키워드 없음, 또는 그 반대
                    logger.info("ℹ️  Stage 1: 경계 케이스 (추가 분석 없이 정상 처리)")
                    thumbnail_analysis = {
                        "stage": "stage1_borderline",
                        "is_fake": False,
                        "text_size_ratio": text_size_ratio,
                        "matched_keywords": keyword_check["matched_keywords"],
                        "reason": "기준 미달로 정상 처리"
                    }
            # 3. 최종 평가 (썸네일 분석 결과 기반)
            is_fake = thumbnail_analysis.get("is_fake", False)
            
            # 썸네일 분석 결과에 따라 점수 할당 (0.0 ~ 1.0)
            # Safe: 0.0, Warning: 0.5, Danger: 1.0
            image_contradiction_score = 0.0
            
            if is_fake:
                # Stage 2에서 가짜뉴스(Danger/Warning)로 판정
                vision_result = thumbnail_analysis.get("vision_analysis", {})
                rating = vision_result.get("fake_news_rating", "Safe")
                
                if rating == "Danger":
                    image_contradiction_score = 1.0
                    logger.info(f"🚨 가짜뉴스 썸네일 탐지: 등급=Danger")
                elif rating == "Warning":
                    image_contradiction_score = 0.5
                    logger.info(f"⚠️ 가짜뉴스 썸네일 의심: 등급=Warning")
            else:
                # Stage 1 통과 또는 Safe
                image_contradiction_score = 0.0
                logger.info(f"✅ 썸네일 정상: Stage={thumbnail_analysis.get('stage', 'unknown')}")

            # 4. frames 배열 생성
            frames = self._create_evidence_frames(
                thumbnail_text_result,
                thumbnail_analysis
            )

            # 5. 결과 요약 생성
            summary = self._generate_module_summary(
                thumbnail_text_result,
                thumbnail_analysis,
                request.claims
            )

            # 6. 결과 매핑
            image_claims = []
            for claim in request.claims:
                image_claims.append(ClaimVerdict(
                    claim_id=claim.claim_id,
                    image_support_score=0.0, # 이미지 모듈은 팩트체크보다는 자극성 위주
                    image_contradiction_score=image_contradiction_score,
                    notes=[summary],
                    frames=frames
                ))

            processing_time = (time.time() - start_time) * 1000
            logger.info(f"이미지 분석 완료: {processing_time:.2f}ms")

            return ImageModuleResult(
                modality="image",
                video_id=request.video_id,
                analysis_summary=summary,
                claims=image_claims,
                frames=frames,
                processing_time_ms=processing_time,
                status="success",
                overall_contradiction_score=image_contradiction_score
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

    async def _analyze_thumbnail_text(self, image_url: str) -> Dict[str, Any]:
        """썸네일의 TEXT_DETECTION (OCR + 텍스트 크기 분석)"""
        try:
            content = await asyncio.to_thread(self._download_image, image_url)
            if not content:
                raise Exception("Thumbnail download failed")

            image = vision.Image(content=content)

            # TEXT_DETECTION 요청
            features = [vision.Feature(type_=vision.Feature.Type.TEXT_DETECTION)]
            request_obj = vision.AnnotateImageRequest(image=image, features=features)
            response = await asyncio.to_thread(self.vision_client.annotate_image, request=request_obj)

            if not response.text_annotations:
                return {
                    "extracted_text": "",
                    "text_size_ratio": 0.0,
                    "bounding_boxes": []
                }

            # 첫 번째 annotation이 전체 텍스트
            full_text = response.text_annotations[0].description

            # 각 단어의 bounding box 수집
            bounding_boxes = []
            total_text_area = 0
            for annotation in response.text_annotations[1:]:  # 첫 번째는 전체 텍스트라서 스킵
                vertices = annotation.bounding_poly.vertices
                if len(vertices) == 4:
                    width = abs(vertices[1].x - vertices[0].x)
                    height = abs(vertices[2].y - vertices[0].y)
                    area = width * height
                    total_text_area += area
                    bounding_boxes.append({
                        "text": annotation.description,
                        "area": area
                    })

            # 이미지 크기 추정 (첫 번째 annotation의 전체 영역)
            if response.text_annotations:
                img_vertices = response.text_annotations[0].bounding_poly.vertices
                if len(img_vertices) == 4:
                    img_width = max(v.x for v in img_vertices)
                    img_height = max(v.y for v in img_vertices)
                    image_area = img_width * img_height if img_width > 0 and img_height > 0 else 1
                else:
                    image_area = 1280 * 720  # 기본값
            else:
                image_area = 1280 * 720

            # 텍스트 크기 비율 계산
            text_size_ratio = min(total_text_area / image_area, 1.0) if image_area > 0 else 0.0

            logger.info(f"OCR 완료: 텍스트 길이={len(full_text)}, 크기비율={text_size_ratio:.2%}")

            return {
                "extracted_text": full_text,
                "text_size_ratio": text_size_ratio,
                "bounding_boxes": bounding_boxes
            }

        except Exception as e:
            logger.error(f"썸네일 TEXT_DETECTION 실패: {e}")
            raise

    def _check_clickbait_keywords(self, text: str) -> Dict[str, Any]:
        """간단한 키워드 매칭으로 낚시성 체크"""
        if not text:
            return {
                "has_clickbait": False,
                "matched_keywords": [],
                "reason": "텍스트 없음"
            }

        # 키워드 매칭
        matched = [kw for kw in CLICKBAIT_KEYWORDS if kw in text]

        return {
            "has_clickbait": len(matched) > 0,
            "matched_keywords": matched,
            "reason": f"낚시성 키워드 {len(matched)}개 발견: {', '.join(matched)}" if matched else "낚시성 키워드 없음"
        }

    async def _analyze_thumbnail_with_vision(
        self,
        image_url: str,
        extracted_text: str,
        matched_keywords: List[str]
    ) -> Dict[str, Any]:
        """GPT-4o-mini Vision으로 썸네일 심층 분석 (Stage 2)"""
        try:
            from ..shared.llm_client import LLMClient
            import json

            # GPT-4o-mini 사용 (비용 절감)
            llm = LLMClient(model="gpt-4o-mini")

            prompt = get_thumbnail_analysis_prompt(extracted_text, matched_keywords)

            # GPT-4o-mini Vision API 호출
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }]

            response_text = await llm.chat_completion_image(
                messages=messages,
                temperature=0.3,
                max_tokens=500
            )

            # JSON 파싱
            try:
                # LLM 응답에서 JSON 블록만 추출
                json_match = re.search(r'```json\n({.*?})\n```', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = response_text

                result = json.loads(json_str.strip())
                logger.info(f"✅ GPT Vision 분석 완료: rating={result.get('fake_news_rating', 'unknown')}, style={result.get('design_style', 'unknown')}")
                return result
            except json.JSONDecodeError as e:
                logger.error(f"GPT Vision JSON 파싱 실패: {e}. 응답: {response_text}")
                return {
                    "text_density": "unknown",
                    "design_style": "unknown",
                    "emotion": "unknown",
                    "fake_news_rating": "Warning", # 파싱 실패 시 기본값
                    "reason": f"분석 오류: LLM 응답이 유효한 JSON이 아님"
                }

        except Exception as e:
            logger.error(f"GPT Vision 분석 중 심각한 오류: {e}", exc_info=True)
            return {
                "text_density": "unknown",
                "design_style": "unknown",
                "emotion": "unknown",
                "fake_news_rating": "Warning",
                "reason": f"분석 오류: {str(e)}"
            }



    def _download_image(self, url: str) -> Optional[bytes]:
        try:
            resp = requests.get(url, timeout=10)
            return resp.content if resp.status_code == 200 else None
        except:
            return None

    def _create_evidence_frames(
        self,
        thumbnail_data: Dict,
        thumbnail_analysis: Dict
    ) -> List[Dict]:
        """증거 프레임 배열 생성"""
        frames = []

        # 썸네일 프레임 추가
        if thumbnail_data.get("extracted_text"):
            is_fake = thumbnail_analysis.get("is_fake", False)
            stage = thumbnail_analysis.get("stage", "unknown")

            details = {
                "stage": stage,
                "text_size_ratio": thumbnail_data.get("text_size_ratio", 0.0),
                "matched_keywords": thumbnail_analysis.get("matched_keywords", [])
            }

            # Stage 2 Vision 분석 결과 포함
            if stage == "stage2_vision":
                vision = thumbnail_analysis.get("vision_analysis", {})
                details.update({
                    "text_density": vision.get("text_density", "unknown"),
                    "design_style": vision.get("design_style", "unknown"),
                    "emotion": vision.get("emotion", "no"),
                    "fake_news_rating": vision.get("fake_news_rating", "Safe")
                })

            frames.append({
                "frame_id": "thumbnail",
                "timestamp": 0.0,
                "description": "썸네일 2단계 분석",
                "evidence": thumbnail_data["extracted_text"][:200],
                "is_problematic": is_fake,
                "details": details
            })

        return frames

    def _generate_module_summary(
        self,
        thumbnail_data: Dict,
        thumbnail_analysis: Dict,
        claims: List[Claim]
    ) -> str:
        """상세 분석 결과 요약 생성"""
        summary_parts = []

        # 1. 썸네일 OCR 결과
        if "error" in thumbnail_data:
            summary_parts.append(f"⚠️ 썸네일 분석 오류: {thumbnail_data['error']}")
        else:
            extracted_text = thumbnail_data.get("extracted_text", "")
            text_size_ratio = thumbnail_data.get("text_size_ratio", 0.0)

            if extracted_text:
                summary_parts.append(f"[썸네일 OCR 결과]")
                summary_parts.append(f"추출된 텍스트: {extracted_text[:100]}...")
                summary_parts.append(f"텍스트 점유율: {text_size_ratio:.1%}")
            else:
                summary_parts.append("⚠️ 썸네일에서 텍스트를 추출할 수 없습니다.")

        # 2. 2단계 분석 결과
        stage = thumbnail_analysis.get("stage", "unknown")
        is_fake = thumbnail_analysis.get("is_fake", False)
        reason = thumbnail_analysis.get("reason", "")

        if stage == "stage1_pass":
            summary_parts.append(f"\n✅ [Stage 1 통과]")
            summary_parts.append(f"판정: 정상 (텍스트 20% 미만, 자극적 키워드 없음)")

        elif stage == "stage2_vision":
            vision = thumbnail_analysis.get("vision_analysis", {})
            rating = vision.get("fake_news_rating", "Safe")

            if rating in ["Danger", "Warning"]:
                icon = "🚨" if rating == "Danger" else "⚠️"
                summary_parts.append(f"\n{icon} [Stage 2: 가짜뉴스 탐지]")
                summary_parts.append(f"위험 등급: {rating}")
                summary_parts.append(f"디자인 스타일: {vision.get('design_style', 'unknown')}")
                summary_parts.append(f"텍스트 밀도: {vision.get('text_density', 'unknown')}")
                summary_parts.append(f"표정 과장: {vision.get('emotion', 'no')}")
                summary_parts.append(f"판정 이유: {reason}")
            else:
                summary_parts.append(f"\n✅ [Stage 2: 정상]")
                summary_parts.append(f"위험 등급: Safe")

        elif stage == "stage1_borderline":
            summary_parts.append(f"\n✅ [Stage 1 경계 케이스]")
            summary_parts.append(f"판정: 정상 (기준 미달)")

        else:
            summary_parts.append(f"\n⚠️ [알 수 없음] stage={stage}")

        return "\n".join(summary_parts)