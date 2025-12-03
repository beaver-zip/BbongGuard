"""텍스트 분석 모듈 (RAG)"""

import logging
import asyncio
import time
from typing import List, Dict, Any

from ..shared.rag_models import (
    TextAnalysisRequest,
    TextModuleResult,
    ClaimVerdict,
    Finding
)
from .claim_extractor import extract_claims_from_video
from .web_searcher import WebSearcher
from .evidence_ranker import EvidenceRanker
from .verdict_agent import VerdictAgent
from ..shared.logger_utils import log_execution

logger = logging.getLogger(__name__)

class TextAnalyzer:
    """영상 텍스트 가짜뉴스 분석 파이프라인을 조율하는 클래스"""

    def __init__(self):
        """TextAnalyzer를 초기화하고 하위 컴포넌트들을 생성합니다."""
        self.web_searcher = WebSearcher()
        self.evidence_ranker = EvidenceRanker()
        self.verdict_agent = VerdictAgent()

        logger.info("TextAnalyzer 초기화 완료")

    @log_execution(module_name="text", step_name="full_analysis")
    async def analyze(self, request: TextAnalysisRequest) -> TextModuleResult:
        """
        영상 텍스트 전체 분석을 수행합니다.
        """
        start_time = time.time()

        try:
            logger.info(f"텍스트 분석 시작: {request.video_id}")

            # [삭제됨] 불필요한 자막 추출 시도 로직 제거
            # if not request.transcript: ... (이 부분 전체 삭제)

            # 1단계: 주장 추출
            # 자막(transcript)은 없으면 없는 대로 제목/설명/댓글만 사용
            logger.info("Step 1/4: Claim 추출")
            claims = await extract_claims_from_video(
                title=request.title,
                description=request.description,
                comments=request.comments,
                transcript=request.transcript, # 있으면 쓰고 없으면 None
                max_claims=request.max_claims
            )

            if not claims:
                logger.warning("추출된 주장이 없습니다")
                return self._create_no_claims_result(request.video_id, start_time)

            logger.info(f"추출된 주장: {len(claims)}개")

            # 2단계: 각 주장 병렬 검증
            logger.info("Step 2/4: Claim 병렬 검증")
            claim_tasks = [
                self._process_single_claim(claim)
                for claim in claims
            ]

            claim_verdicts = await asyncio.gather(*claim_tasks, return_exceptions=True)

            # 예외 처리
            valid_verdicts = []
            for i, result in enumerate(claim_verdicts):
                if isinstance(result, Exception):
                    logger.error(f"Claim {i} 처리 실패: {result}")
                else:
                    valid_verdicts.append(result)

            if not valid_verdicts:
                logger.error("모든 주장 검증 실패")
                return self._create_error_result(request.video_id, "모든 주장 검증 실패", start_time)

            # 3단계: 판정 통합
            logger.info("Step 3/4: 판정 통합")            
            aggregated = self.verdict_agent.aggregate_verdicts(valid_verdicts)

            # 4단계: Finding 변환 및 최종 결과 생성
            logger.info("Step 4/4: Finding 변환 및 최종 결과 생성")
            findings = self._convert_verdicts_to_findings(valid_verdicts)

            module_assessment = self._determine_assessment(
                aggregated['fake_claims_count'],
                aggregated['total_claims']
            )

            key_concerns = [
                verdict.verdict_reason
                for verdict in valid_verdicts
                if verdict.is_fake
            ][:3]

            result = TextModuleResult(
                modality="text",
                video_id=request.video_id,
                analysis_summary=aggregated['summary'],
                findings=findings,
                total_findings=aggregated['total_claims'],
                problematic_findings_count=aggregated['fake_claims_count'],
                module_assessment=module_assessment,
                key_concerns=key_concerns,
                processing_time_ms=(time.time() - start_time) * 1000,
                status="success",
                claims=valid_verdicts
            )

            logger.info(
                f"텍스트 분석 완료: {request.video_id} -> {module_assessment} "
                f"(문제 발견: {result.problematic_findings_count}/{result.total_findings})"
            )
            return result

        except Exception as e:
            logger.error(f"텍스트 분석 중 오류: {e}", exc_info=True)
            return self._create_error_result(request.video_id, str(e), start_time)

    # ... (나머지 메서드들은 기존 코드 그대로 유지) ...
    # _convert_verdicts_to_findings, _determine_assessment, _process_single_claim 등
    
    def _convert_verdicts_to_findings(self, verdicts: List[ClaimVerdict]) -> List[Finding]:
        findings = []
        for verdict in verdicts:
            finding = Finding(
                finding_id=verdict.claim_id,
                finding_type="claim",
                description=verdict.claim_text,
                is_problematic=verdict.is_fake,
                severity="high" if verdict.is_fake else "low",
                evidence_summary=verdict.verdict_reason,
                details={
                    "category": verdict.category,
                    "evidence_count": len(verdict.evidence)
                }
            )
            findings.append(finding)
        return findings

    def _determine_assessment(self, fake_count: int, total_count: int) -> str:
        if total_count == 0: return "inconclusive"
        fake_ratio = fake_count / total_count
        if fake_ratio >= 0.5: return "suspicious"
        else: return "normal"

    async def _process_single_claim(self, claim) -> ClaimVerdict:
        """단일 주장 검색 및 검증"""
        try:
            logger.info(f"Claim 처리 시작: {claim.claim_text[:50]}...")

            # 웹 검색 (Async)
            evidence_list = await self.web_searcher.search_claim(claim)
            evidence_list = self.web_searcher.filter_and_format_results(evidence_list, claim)

            if not evidence_list:
                return ClaimVerdict(
                    claim_id=claim.claim_id,
                    claim_text=claim.claim_text,
                    category=claim.category,
                    is_fake=False, 
                    verdict_reason="검색 결과가 없어 검증할 수 없습니다.",
                    evidence=[],
                    processing_time_ms=0
                )

            # 랭킹 및 LLM 검증 (Async)
            top_evidence = await self.evidence_ranker.rank_and_select(claim, evidence_list)

            # 판정
            verdict = await self.verdict_agent.judge_claim(claim, top_evidence)
            return verdict

        except Exception as e:
            logger.error(f"Claim 처리 실패: {e}", exc_info=True)
            raise

    def _create_no_claims_result(self, video_id: str, start_time: float) -> TextModuleResult:
        return TextModuleResult(
            modality="text",
            video_id=video_id,
            analysis_summary="분석할 주장이 없습니다.",
            findings=[],
            total_findings=0,
            problematic_findings_count=0,
            module_assessment="inconclusive",
            key_concerns=[],
            processing_time_ms=(time.time() - start_time) * 1000,
            status="success",
            claims=[]
        )

    def _create_error_result(self, video_id: str, error_msg: str, start_time: float) -> TextModuleResult:
        return TextModuleResult(
            modality="text",
            video_id=video_id,
            analysis_summary="분석 중 오류 발생",
            findings=[],
            total_findings=0,
            problematic_findings_count=0,
            module_assessment="inconclusive",
            key_concerns=[],
            processing_time_ms=(time.time() - start_time) * 1000,
            status="error",
            error_message=error_msg,
            claims=[]
        )