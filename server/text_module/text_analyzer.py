"""텍스트 분석 모듈 (RAG)"""

import logging
import asyncio
import time
from typing import List

from ..shared.text_module import (
    TextAnalysisRequest,
    TextModuleResult,
    ClaimVerdict,
    Finding
)
from ..shared.schemas import Claim
from .claim_extractor import extract_claims_from_video
from .web_searcher import WebSearcher
from .evidence_ranker import EvidenceRanker
from .verdict_agent import VerdictAgent
from ..shared.logger_utils import log_execution
from ..shared.youtube_client import get_youtube_client

logger = logging.getLogger(__name__)

class TextAnalyzer:
    """영상 텍스트 가짜뉴스 분석 파이프라인을 조율하는 클래스"""

    def __init__(self):
        """TextAnalyzer를 초기화하고 하위 컴포넌트들을 생성합니다."""
        self.web_searcher = WebSearcher()
        self.evidence_ranker = EvidenceRanker()
        self.verdict_agent = VerdictAgent()
        self.youtube_client = get_youtube_client()
        # self.audio_analyzer = AudioAnalyzer() # 순환 참조 방지를 위해 analyze 메서드로 이동

        logger.info("TextAnalyzer 초기화 완료")

    @log_execution(module_name="text", step_name="full_analysis")
    async def analyze(self, request: TextAnalysisRequest) -> TextModuleResult:
        """
        영상 텍스트 전체 분석 파이프라인을 실행합니다.

        1. 주장 추출 (1차: 자막/메타데이터, 2차: STT)
        2. 웹 검색 및 증거 수집
        3. 증거 순위 매김
        4. LLM 기반 팩트체크 및 판정
        5. 결과 통합 및 요약

        Args:
            request (TextAnalysisRequest): 텍스트 분석 요청 객체.

        Returns:
            TextModuleResult: 텍스트 모듈 분석 결과.
        """
        start_time = time.time()

        try:
            logger.info(f"텍스트 분석 시작: {request.video_id}")

            # 영상 정보 가져오기 (게시일)
            video_info = await asyncio.to_thread(self.youtube_client.get_video_info, request.video_id)
            request.published_at = video_info.get("published_at")

            # 1단계: 주장 추출 (1차 시도 - 기본 정보 활용)
            logger.info("Step 1/5: Claim 추출 (1차 시도)")
            claims = await extract_claims_from_video(
                title=request.title,
                description=request.description,
                transcript=request.transcript,
                max_claims=request.max_claims
            )

            # 1-2단계: 1차 추출 실패 시 STT를 이용한 2차 시도
            if not claims:
                # ================== STT 디버깅 로그 시작 ==================
                import os
                debug_log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", "stt_debug.log")
                # 기본 로거를 재설정하지 않도록 핸들러를 직접 추가
                debug_logger = logging.getLogger('stt_debugger')
                if not debug_logger.handlers: # 핸들러 중복 추가 방지
                    debug_logger.setLevel(logging.INFO)
                    handler = logging.FileHandler(debug_log_path, mode='w', encoding='utf-8')
                    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
                    handler.setFormatter(formatter)
                    debug_logger.addHandler(handler)
                # ========================================================

                from ..audio_module.audio_analyzer import AudioAnalyzer # 순환 참조 방지를 위한 지연 임포트
                
                debug_logger.info("1차 주장 추출 실패. STT를 이용한 2차 추출을 시도합니다.")
                logger.warning("1차 주장 추출 실패. STT를 이용한 2차 추출을 시도합니다.")
                
                audio_analyzer = AudioAnalyzer()
                stt_transcript = await audio_analyzer.transcribe_video(request.video_id)

                if stt_transcript:
                    debug_logger.info(f"STT 성공. Transcript 길이: {len(stt_transcript)}. 2차 주장 추출 실행.")
                    logger.info("STT 성공. 2차 주장 추출 실행.")
                    request.transcript = stt_transcript
                    claims = await extract_claims_from_video(
                        title=request.title,
                        description=request.description,
                        transcript=stt_transcript,
                        max_claims=request.max_claims
                    )
                else:
                    debug_logger.error("STT 변환에 실패하여 2차 주장 추출을 건너뜁니다.")
                    logger.error("STT 변환에 실패하여 2차 주장 추출을 건너뜁니다.")

            if not claims:
                logger.warning("최종적으로 추출된 주장이 없습니다")
                return self._create_no_claims_result(request.video_id, start_time)

            logger.info(f"추출된 주장: {len(claims)}개")

            # 2단계: 각 주장 병렬 검증
            logger.info("Step 2/5: Claim 병렬 검증")
            claim_tasks = [
                self._process_single_claim(claim, request)
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
            logger.info("Step 3/5: 판정 통합")
            aggregated = self.verdict_agent.aggregate_verdicts(valid_verdicts)

            # 4단계: Finding 변환 및 최종 결과 생성
            logger.info("Step 4/5: Finding 변환 및 최종 결과 생성")
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
                claims=valid_verdicts,
                transcript=request.transcript
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
        """ClaimVerdict 리스트를 Finding 리스트로 변환"""
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
        """가짜뉴스 비율에 따른 모듈 평가 결정"""
        if total_count == 0: return "inconclusive"
        fake_ratio = fake_count / total_count
        if fake_ratio >= 0.5: return "suspicious"
        else: return "normal"

    async def _process_single_claim(self, claim: Claim, request: TextAnalysisRequest) -> ClaimVerdict:
        """
        단일 주장에 대한 검색, 증거 수집, 팩트체크를 수행합니다.

        Args:
            claim (Claim): 검증할 주장.
            request (TextAnalysisRequest): 분석 요청 정보.

        Returns:
            ClaimVerdict: 주장에 대한 판정 결과.
        """
        try:
            logger.info(f"Claim 처리 시작: {claim.claim_text[:50]}...")

            # 웹 검색 (Async)
            evidence_list = await self.web_searcher.search_claim(claim)
            evidence_list = self.web_searcher.filter_and_format_results(evidence_list, claim)

            # 날짜 기반 재정렬
            if request.published_at:
                evidence_list = self.web_searcher.rerank_by_date(evidence_list, request.published_at)

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