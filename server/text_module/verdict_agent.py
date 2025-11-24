"""주장 판정 및 멀티모달 통합"""

import logging
from typing import List, Dict, Any
import time
import json

from ..shared.schemas import Claim, VideoMeta
from ..shared.rag_models import Evidence, ClaimVerdict, FinalVerdict
from ..shared.llm_client import get_llm_client
from ..shared.logger_utils import log_execution

logger = logging.getLogger(__name__)


class VerdictAgent:
    """LLM을 사용하여 증거 기반으로 주장의 진위를 판정하고 멀티모달 결과를 통합하는 클래스"""

    def __init__(self):
        """VerdictAgent를 초기화합니다."""
        logger.info("VerdictAgent 초기화")

    async def judge_claim(
        self,
        claim: Claim,
        evidence_list: List[Evidence]
    ) -> ClaimVerdict:
        """
        증거를 기반으로 주장이 가짜인지 사실인지 이진 판정합니다.
        (기존 텍스트 모듈 로직 유지)
        """
        start_time = time.time()

        try:
            llm_client = await get_llm_client()
            evidence_dicts = [ev.model_dump() for ev in evidence_list]

            # LLM 이진 판정
            judgment = await llm_client.judge_claim(
                claim=claim.claim_text,
                evidence_list=evidence_dicts
            )

            is_fake = judgment.get('is_fake', True)
            verdict_reason = judgment.get('reason', '판정 근거 없음')

            verdict = ClaimVerdict(
                claim_id=claim.claim_id,
                claim_text=claim.claim_text,
                category=claim.category,
                is_fake=is_fake,
                verdict_reason=verdict_reason,
                evidence=evidence_list,
                processing_time_ms=(time.time() - start_time) * 1000
            )

            logger.info(f"주장 판정 완료: {claim.claim_text[:50]}... -> {'가짜' if is_fake else '사실'}")
            return verdict

        except Exception as e:
            logger.error(f"주장 판정 실패: {e}", exc_info=True)
            return ClaimVerdict(
                claim_id=claim.claim_id,
                claim_text=claim.claim_text,
                category=claim.category,
                is_fake=True,
                verdict_reason=f"판정 중 오류 발생: {str(e)}",
                evidence=evidence_list,
                processing_time_ms=(time.time() - start_time) * 1000
            )

    @log_execution(module_name="integration", step_name="final_verdict")
    async def aggregate_multimodal_verdicts(
        self,
        video_meta: VideoMeta,
        claims: List[Claim],
        text_verdicts: List[ClaimVerdict],
        image_results: Dict[str, Any],
        audio_results: Dict[str, Any]
    ) -> FinalVerdict:
        """
        텍스트, 이미지, 오디오 분석 결과를 종합하여 최종 판단을 내립니다.
        (자극성 및 감정적 선동 여부 반영)
        """
        try:
            llm_client = await get_llm_client()

            # 1. Claim별 데이터 취합
            claims_summary = ""
            for i, claim in enumerate(claims, 1):
                # 텍스트 판정
                t_verdict = next((v for v in text_verdicts if v.claim_id == claim.claim_id), None)
                t_result = "판정 불가"
                t_reason = "근거 없음"
                if t_verdict:
                    t_result = "가짜" if t_verdict.is_fake else "사실"
                    t_reason = t_verdict.verdict_reason
                
                # 이미지 결과 (자극성)
                img_res = next((r for r in image_results.get("claims", []) if r["claim_id"] == claim.claim_id), {})
                # notes에 자극성 요약이 들어있음
                img_summary = img_res.get("notes", ["분석 없음"])[0]

                # 오디오 결과 (선동)
                aud_res = next((r for r in audio_results.get("claims", []) if r["claim_id"] == claim.claim_id), {})
                # notes에 선동 요약이 들어있음
                aud_summary = aud_res.get("notes", ["분석 없음"])[0]

                claims_summary += f"""
Claim {i}: "{claim.claim_text}"
- 텍스트 팩트체크: {t_result} (근거: {t_reason})
- 이미지 분석 (자극성): {img_summary}
- 오디오 분석 (선동성): {aud_summary}
"""

            # 2. LLM 종합 판단 요청
            prompt = f"""당신은 멀티모달 가짜뉴스 판별 전문가입니다. 다음 영상의 분석 결과를 종합하여 최종 판단을 내리세요.

영상 제목: {video_meta.url} (ID: {video_meta.video_id})

각 주장에 대한 모듈별 분석 결과:
{claims_summary}

판단 가이드:
1. **텍스트 팩트체크**가 가장 중요합니다. 팩트체크 결과가 '가짜'라면 가짜뉴스일 확률이 매우 높습니다.
2. **이미지/오디오**는 '자극성'과 '선동성'을 분석했습니다.
   - 팩트체크가 '사실'이어도 이미지/오디오가 매우 자극적이라면 "낚시성/과장된 콘텐츠(Clickbait)"로 판단하세요.
   - 팩트체크가 '가짜'이고 이미지/오디오도 자극적/선동적이라면 "악의적인 가짜뉴스(Malicious Fake News)"로 강력히 경고하세요.
   - 팩트체크가 '가짜'인데 이미지/오디오가 차분하다면 "단순 오정보(Misinformation)"일 수 있습니다.

3. **종합 결론**: 영상 전체가 시청자에게 해로운지, 단순 흥미 위주인지, 아니면 유익한지 판단하세요.

출력 형식 (JSON):
{{
  "is_fake_news": true/false,
  "confidence_level": "high/medium/low",
  "overall_reasoning": "종합적인 판단 이유 (3문장 내외)",
  "text_analysis_summary": "텍스트 모듈 요약",
  "image_analysis_summary": "이미지 모듈 요약 (자극성 위주)",
  "audio_analysis_summary": "오디오 모듈 요약 (선동성 위주)",
  "key_evidence": ["핵심 근거 1", "핵심 근거 2"],
  "recommendation": "사용자에게 주는 권장 사항"
}}"""

            messages = [{"role": "user", "content": prompt}]
            
            result = await llm_client.chat_completion_json(messages)

            return FinalVerdict(
                is_fake_news=result.get("is_fake_news", False),
                confidence_level=result.get("confidence_level", "medium"),
                overall_reasoning=result.get("overall_reasoning", "분석 결과 없음"),
                text_analysis_summary=result.get("text_analysis_summary", ""),
                image_analysis_summary=result.get("image_analysis_summary", ""),
                audio_analysis_summary=result.get("audio_analysis_summary", ""),
                key_evidence=result.get("key_evidence", []),
                recommendation=result.get("recommendation", "정보 확인 필요")
            )

        except Exception as e:
            logger.error(f"멀티모달 통합 판단 실패: {e}", exc_info=True)
            # 실패 시 기본값 반환
            return FinalVerdict(
                is_fake_news=False,
                confidence_level="low",
                overall_reasoning="통합 분석 중 오류가 발생했습니다.",
                recommendation="분석 시스템 오류로 인해 결과를 확인할 수 없습니다."
            )

    def aggregate_verdicts(self, verdicts: List[ClaimVerdict]) -> dict:
        """
        (Legacy) 텍스트 모듈 전용 집계 함수 - 하위 호환성 유지
        """
        if not verdicts:
            return {
                'is_fake_news': False,
                'summary': '분석할 주장이 없습니다.',
                'total_claims': 0,
                'fake_claims_count': 0
            }

        total_claims = len(verdicts)
        fake_claims_count = sum(1 for v in verdicts if v.is_fake)
        is_fake_news = (fake_claims_count >= total_claims * 0.5)
        
        summary = f"총 {total_claims}개 주장 중 {fake_claims_count}개가 거짓으로 판명되었습니다."
        
        return {
            'is_fake_news': is_fake_news,
            'summary': summary,
            'total_claims': total_claims,
            'fake_claims_count': fake_claims_count
        }
