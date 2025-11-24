"""이미지 증거 분석 (LLM)"""

import logging
from typing import List, Dict, Any

from ..shared.schemas import Claim, FrameFeature
from ..shared.llm_client import get_llm_client

logger = logging.getLogger(__name__)

class ImageLLMSummarizer:
    """선택된 프레임의 텍스트 정보를 바탕으로 Claim과의 관계를 분석하는 클래스"""

    def __init__(self):
        """ImageLLMSummarizer 초기화"""
        logger.info("ImageLLMSummarizer 초기화")

    async def summarize_for_claim(
        self, 
        claim: Claim, 
        selected_frames: List[FrameFeature]
    ) -> Dict[str, Any]:
        """
        프레임 정보를 바탕으로 Claim을 분석합니다.

        Args:
            claim: 분석할 주장
            selected_frames: 선택된 프레임 리스트

        Returns:
            분석 결과 딕셔너리
            {
                "image_support_score": float,
                "image_contradiction_score": float,
                "notes": List[str]
            }
        """
        if not selected_frames:
            return {
                "image_support_score": 0.0,
                "image_contradiction_score": 0.0,
                "notes": ["관련된 이미지 프레임을 찾을 수 없습니다."]
            }

        try:
            llm_client = await get_llm_client()

            # 프레임 정보 텍스트 변환
            frames_text = ""
            for i, frame in enumerate(selected_frames, 1):
                frames_text += f"\nFrame {i} (시간: {frame.timestamp:.1f}초):\n"
                frames_text += f"  - 화면 텍스트(OCR): {frame.ocr_text}\n"
                if frame.caption:
                    frames_text += f"  - 화면 설명: {frame.caption}\n"

            prompt = f"""당신은 영상 분석 전문가입니다. 다음 영상 프레임 정보들이 주장을 시각적으로 지지하는지, 아니면 모순되는지 분석하세요.

주장: "{claim.claim_text}"

선택된 프레임 정보 (OCR 및 설명):
{frames_text}

분석 가이드:
1. **지지 여부**: 화면의 텍스트나 장면이 주장의 내용을 직접적으로 보여주거나 뒷받침합니까? (예: 주장의 수치가 자막으로 등장)
2. **모순 여부**: 화면의 내용이 주장과 정반대되거나, 주장이 거짓임을 시사합니까?
3. **객관성**: 단순한 자막(제작자의 주장 반복)인지, 아니면 객관적인 증거 자료(공문서, 뉴스 화면 등)인지 구분하세요. 단순 자막은 지지 점수를 낮게 책정하세요.

출력 형식 (JSON):
{{
  "image_support_score": 0.0 ~ 1.0,       // 이미지가 주장을 지지하는 정도 (단순 자막 반복은 0.3 이하)
  "image_contradiction_score": 0.0 ~ 1.0, // 이미지가 주장과 모순되는 정도
  "notes": ["분석 의견 1", "분석 의견 2"] // 구체적인 근거 (어떤 프레임이 어떤 내용을 담고 있는지)
}}"""

            messages = [{"role": "user", "content": prompt}]

            result = await llm_client.chat_completion_json(messages)
            
            return {
                "image_support_score": result.get("image_support_score", 0.0),
                "image_contradiction_score": result.get("image_contradiction_score", 0.0),
                "notes": result.get("notes", [])
            }

        except Exception as e:
            logger.error(f"이미지 분석 요약 실패: {e}", exc_info=True)
            return {
                "image_support_score": 0.0,
                "image_contradiction_score": 0.0,
                "notes": [f"분석 중 오류 발생: {str(e)}"]
            }
