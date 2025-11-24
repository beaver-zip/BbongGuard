"""오디오 분석 요약 (LLM)"""

import logging
from typing import List, Dict, Any

from ..shared.schemas import Claim, AudioSegment
from ..shared.llm_client import get_llm_client

logger = logging.getLogger(__name__)

class AudioLLMSummarizer:
    """오디오 구간의 텍스트와 톤 정보를 바탕으로 Claim과의 관계를 분석하는 클래스"""

    def __init__(self):
        """AudioLLMSummarizer 초기화"""
        logger.info("AudioLLMSummarizer 초기화")

    async def summarize_for_claim(
        self, 
        claim: Claim, 
        segments: List[AudioSegment]
    ) -> Dict[str, Any]:
        """
        오디오 구간 정보를 바탕으로 Claim을 분석합니다.

        Args:
            claim: 분석할 주장
            segments: 관련 오디오 구간 리스트

        Returns:
            분석 결과 딕셔너리
            {
                "audio_support_score": float,
                "notes": List[str]
            }
        """
        if not segments:
            return {
                "audio_support_score": 0.0,
                "notes": ["관련된 오디오 구간을 찾을 수 없습니다."]
            }

        try:
            llm_client = await get_llm_client()

            # 오디오 정보 텍스트 변환
            segments_text = ""
            for i, seg in enumerate(segments, 1):
                segments_text += f"\nSegment {i} (시간: {seg.start:.1f}~{seg.end:.1f}초):\n"
                segments_text += f"  - 발화 내용: {seg.transcript_text}\n"
                if seg.tone:
                    segments_text += f"  - 어조/톤: {seg.tone}\n"
                if seg.emotion:
                    segments_text += f"  - 감정: {seg.emotion}\n"

            prompt = f"""당신은 음성 분석 전문가입니다. 다음 오디오 구간 정보들이 주장을 청각적으로 지지하는지 분석하세요.

주장: "{claim.claim_text}"

선택된 오디오 구간 정보 (발화 및 톤):
{segments_text}

분석 가이드:
1. **지지 여부**: 화자가 주장의 내용을 직접 말하고 있습니까?
2. **신뢰도**: 화자의 어조가 확신에 차 있는지, 아니면 불확실하거나 감정적인지(선동적) 분석하세요.
3. **근거 제시**: 화자가 주장의 근거를 함께 언급하는지 확인하세요. 근거 없이 주장만 반복한다면 점수를 조정하세요.

출력 형식 (JSON):
{{
  "audio_support_score": 0.0 ~ 1.0, // 오디오 내용이 주장을 지지하는 정도
  "notes": ["분석 의견 1", "분석 의견 2"] // 화자의 태도, 근거 유무 등에 대한 의견
}}"""

            messages = [{"role": "user", "content": prompt}]

            result = await llm_client.chat_completion_json(messages)
            
            return {
                "audio_support_score": result.get("audio_support_score", 0.0),
                "notes": result.get("notes", [])
            }

        except Exception as e:
            logger.error(f"오디오 분석 요약 실패: {e}", exc_info=True)
            return {
                "audio_support_score": 0.0,
                "notes": [f"분석 중 오류 발생: {str(e)}"]
            }
