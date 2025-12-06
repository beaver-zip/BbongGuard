"""주장 판정 및 멀티모달 통합"""

import logging
from typing import List, Dict, Any
import time

from ..shared.schemas import Claim, VideoMeta
from ..shared.text_module import Evidence, ClaimVerdict
from ..shared.multimodal_result import FinalVerdict
from ..shared.llm_client import get_llm_client
from ..shared.logger_utils import log_execution
from ..resources.prompts import get_verdict_agent_prompt, get_claim_judgment_prompt

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
        단일 주장에 대해 증거를 바탕으로 진위를 판정합니다.

        LLM을 사용하여 증거와 주장 간의 일치 여부를 분석하고 판정 결과를 생성합니다.

        Args:
            claim (Claim): 판정할 주장.
            evidence_list (List[Evidence]): 관련 증거 목록.

        Returns:
            ClaimVerdict: 판정 결과 (진실/거짓/판정불가 및 이유).
        """
        try:
            llm_client = await get_llm_client()
            
            # 증거가 없으면 바로 insufficient_evidence 반환
            if not evidence_list:
                return ClaimVerdict(
                    claim_id=claim.claim_id,
                    claim_text=claim.claim_text,
                    category=claim.category,
                    is_fake=False,
                    verdict_reason="관련 증거를 찾지 못했습니다.",
                    evidence=[],
                    processing_time_ms=0
                )

            # Evidence 포맷팅 (출처 강조)
            evidence_text = ""
            for i, ev in enumerate(evidence_list, 1):
                domain = ev.domain
                source_title = ev.source_title
                snippet = ev.snippet

                evidence_text += f"\n{i}. [{domain}] {source_title}\n"
                evidence_text += f"   내용: {snippet}\n"

            prompt = get_claim_judgment_prompt(claim.claim_text, evidence_text)
            messages = [{"role": "user", "content": prompt}]
            
            result = await llm_client.chat_completion_json(messages)
            
            verdict_status = result.get('verdict_status', 'insufficient_evidence')
            # 유효성 검사
            if verdict_status not in ["verified_true", "verified_false", "insufficient_evidence"]:
                verdict_status = "insufficient_evidence"
            
            reason = result.get('reason', '판정 이유 없음')

            is_fake = (verdict_status == "verified_false")
            
            return ClaimVerdict(
                claim_id=claim.claim_id,
                claim_text=claim.claim_text,
                category=claim.category,
                is_fake=is_fake,
                verdict_reason=reason,
                evidence=evidence_list,
                processing_time_ms=0 # 상위에서 계산
            )

        except Exception as e:
            logger.error(f"주장 판정 실패: {e}", exc_info=True)
            return ClaimVerdict(
                claim_id=claim.claim_id,
                claim_text=claim.claim_text,
                category=claim.category,
                verdict_status="insufficient_evidence",
                is_fake=False,
                verdict_reason=f"판정 중 오류 발생: {str(e)}",
                evidence=evidence_list,
                processing_time_ms=0
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

        Args:
            video_meta (VideoMeta): 영상 메타데이터.
            claims (List[Claim]): 추출된 주장 목록.
            text_verdicts (List[ClaimVerdict]): 텍스트 팩트체크 결과.
            image_results (Dict[str, Any]): 이미지 분석 결과.
            audio_results (Dict[str, Any]): 오디오 분석 결과.

        Returns:
            FinalVerdict: 종합 판정 결과.
        """
        try:
            llm_client = await get_llm_client()

            # 1. Claim별 데이터 취합 및 텍스트 출처 정보 수집
            claims_summary = ""
            text_sources_info = []  # 텍스트 모듈에서 사용한 출처 정보
            
            for i, claim in enumerate(claims, 1):
                # 텍스트 판정
                t_verdict = next((v for v in text_verdicts if v.claim_id == claim.claim_id), None)
                t_result = "판정 불가"
                t_reason = "근거 없음"
                evidence_sources = []
                
                if t_verdict:
                    t_result = "가짜" if t_verdict.is_fake else "사실"
                    t_reason = t_verdict.verdict_reason
                    
                    # Evidence에서 출처 URL 추출
                    evidence_sources = [
                        f"[{ev.source_title}]({ev.source_url})" 
                        for ev in t_verdict.evidence
                    ]
                    
                    # 텍스트 출처 정보 저장 (판단 근거와 출처)
                    if t_verdict.evidence:
                        for ev in t_verdict.evidence:
                            # 중복 제거 (URL 기준)
                            if not any(s['url'] == ev.source_url for s in text_sources_info):
                                text_sources_info.append({
                                    "reason": t_reason,
                                    "title": ev.source_title,
                                    "url": ev.source_url
                                })
                
                # 이미지 결과 (자극성)
                img_res = next((r for r in image_results.get("claims", []) if r["claim_id"] == claim.claim_id), {})
                # notes에 자극성 요약이 들어있음
                img_summary = img_res.get("notes", ["분석 없음"])[0]

                # 오디오 결과 (선동)
                aud_res = next((r for r in audio_results.get("claims", []) if r["claim_id"] == claim.claim_id), {})
                # notes에 선동 요약이 들어있음
                aud_summary = aud_res.get("notes", ["분석 없음"])[0]

                # 출처 정보 포함
                evidence_str = ", ".join(evidence_sources) if evidence_sources else "출처 없음"
                
                claims_summary += f"""
Claim {i}: "{claim.claim_text}"

[핵심 검증: 텍스트]
- 판정: {t_result}
- 근거: {t_reason}
- 출처: {evidence_str}

[보조 분석: 이미지/오디오]
- 이미지(썸네일): {img_summary}
- 오디오(선동성): {aud_summary}
--------------------------------------------------
"""

            # 2. LLM 종합 판단 요청
            prompt = get_verdict_agent_prompt(video_meta, claims_summary)

            messages = [{"role": "user", "content": prompt}]
            
            result = await llm_client.chat_completion_json(messages)

            return FinalVerdict(
                is_fake_news=result.get("is_fake_news", False),
                confidence_level=result.get("confidence_level", "medium"),
                overall_reasoning=result.get("overall_reasoning", "분석 결과 없음"),
                text_analysis_summary=result.get("text_analysis_summary", ""),
                image_analysis_summary=result.get("image_analysis_summary", ""),
                audio_analysis_summary=result.get("audio_analysis_summary", ""),
                image_analysis_details=result.get("image_analysis_details", ""),
                audio_analysis_details=result.get("audio_analysis_details", ""),
                key_evidence=result.get("key_evidence", []),
                text_sources=text_sources_info,
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
        텍스트 모듈 전용 집계 함수.
        개별 주장 판정 결과를 종합하여 텍스트 모듈의 전체 결과를 생성합니다.

        Args:
            verdicts (List[ClaimVerdict]): 개별 주장 판정 결과 리스트.

        Returns:
            dict: 집계 결과 (is_fake_news, summary, total_claims, fake_claims_count).
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
