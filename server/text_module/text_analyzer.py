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
from ..shared.youtube_client import get_youtube_client
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

        주장 추출 → 각 주장 병렬 검증 → 판정 통합 단계로 진행됩니다.

        Args:
            request: 분석할 영상 정보를 담은 요청 객체

        Returns:
            텍스트 모듈 분석 결과 (ModalityResult)
        """
        start_time = time.time()

        try:
            logger.info(f"텍스트 분석 시작: {request.video_id}")

            # 자막 확보
            if not request.transcript:
                logger.info("자막이 없어 추출을 시도합니다...")
                youtube_client = get_youtube_client()
                request.transcript = youtube_client.get_transcript(request.video_id)
                if request.transcript:
                    logger.info(f"자막 추출 성공: {len(request.transcript)}자")
                else:
                    logger.warning("자막 추출 실패")

            # 1단계: 주장 추출
            logger.info("Step 1/4: Claim 추출")
            claims = await extract_claims_from_video(
                title=request.title,
                description=request.description,
                comments=request.comments,
                transcript=request.transcript,
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

            # 4단계: ClaimVerdict를 Finding으로 변환
            logger.info("Step 4/4: Finding 변환 및 최종 결과 생성")
            findings = self._convert_verdicts_to_findings(valid_verdicts)

            # module_assessment 결정
            module_assessment = self._determine_assessment(
                aggregated['fake_claims_count'],
                aggregated['total_claims']
            )

            # key_concerns 생성
            key_concerns = [
                verdict.verdict_reason
                for verdict in valid_verdicts
                if verdict.is_fake
            ][:3]  # 상위 3개만

            # 최종 결과 생성
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

    def _convert_verdicts_to_findings(self, verdicts: List[ClaimVerdict]) -> List[Finding]:
        """
        ClaimVerdict 리스트를 Finding 리스트로 변환합니다.

        Args:
            verdicts: ClaimVerdict 리스트

        Returns:
            Finding 리스트
        """
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
        """
        가짜 주장 비율로 모듈 평가를 결정합니다.

        Args:
            fake_count: 가짜 주장 수
            total_count: 전체 주장 수

        Returns:
            "suspicious" / "normal" / "inconclusive"
        """
        if total_count == 0:
            return "inconclusive"

        fake_ratio = fake_count / total_count

        if fake_ratio >= 0.5:
            return "suspicious"
        elif fake_ratio > 0:
            return "normal"
        else:
            return "normal"

    async def _process_single_claim(self, claim) -> ClaimVerdict:
        """
        단일 주장을 검색 → 랭킹 → 판정 단계로 처리합니다.

        Args:
            claim: 처리할 주장 객체

        Returns:
            주장 판정 결과 (ClaimVerdict)
        """
        try:
            logger.info(f"Claim 처리 시작: {claim.claim_text[:50]}...")

            # 웹 검색
            evidence_list = await self.web_searcher.search_and_filter(claim)

            if not evidence_list:
                logger.warning(f"Claim에 대한 Evidence 없음: {claim.claim_text[:50]}...")
                # 증거 없으면 검증 불가능으로 가짜 판정
                return ClaimVerdict(
                    claim_id=claim.claim_id,
                    claim_text=claim.claim_text,
                    category=claim.category,
                    is_fake=True,
                    verdict_reason="신뢰할 수 있는 출처에서 관련 정보를 찾을 수 없어 검증 불가능합니다.",
                    evidence=[],
                    processing_time_ms=0
                )

            # 증거 랭킹 및 상위 선택
            top_evidence = await self.evidence_ranker.rank_and_select(claim, evidence_list)

            # 판정
            verdict = await self.verdict_agent.judge_claim(claim, top_evidence)

            return verdict

        except Exception as e:
            logger.error(f"Claim 처리 실패: {e}", exc_info=True)
            raise

    def _create_no_claims_result(self, video_id: str, start_time: float) -> TextModuleResult:
        """
        주장이 추출되지 않았을 때의 결과를 생성합니다.

        Args:
            video_id: 영상 ID
            start_time: 분석 시작 시각

        Returns:
            주장 없음을 나타내는 TextModuleResult
        """
        return TextModuleResult(
            modality="text",
            video_id=video_id,
            analysis_summary="영상에서 팩트체킹이 필요한 구체적인 주장을 찾을 수 없습니다. 의견이나 예측 위주의 콘텐츠일 수 있습니다.",
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
        """
        분석 중 오류 발생 시 에러 결과를 생성합니다.

        Args:
            video_id: 영상 ID
            error_msg: 에러 메시지
            start_time: 분석 시작 시각

        Returns:
            에러 상태를 나타내는 TextModuleResult
        """
        return TextModuleResult(
            modality="text",
            video_id=video_id,
            analysis_summary="분석 중 오류가 발생했습니다.",
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


async def analyze_video_text(
    video_id: str,
    title: str,
    description: str = "",
    comments: List[str] = None,
    transcript: str = None,
    max_claims: int = None
) -> TextModuleResult:
    """
    YouTube 영상 텍스트를 분석하여 가짜뉴스 여부를 판정합니다.

    TextAnalyzer를 생성하여 전체 분석 파이프라인을 실행하는 편의 함수입니다.

    Args:
        video_id: YouTube 영상 ID
        title: 영상 제목
        description: 영상 설명 (선택)
        comments: 댓글 목록 (선택)
        transcript: 자막 (선택)
        max_claims: 최대 추출할 주장 수 (선택)

    Returns:
        텍스트 모듈 분석 결과 (TextModuleResult)
    """
    request = TextAnalysisRequest(
        video_id=video_id,
        title=title,
        description=description,
        comments=comments or [],
        transcript=transcript,
        max_claims=max_claims
    )

    analyzer = TextAnalyzer()
    result = await analyzer.analyze(request)

    return result
