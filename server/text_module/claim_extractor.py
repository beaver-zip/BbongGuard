"""주장 추출"""

import logging
from typing import List, Dict, Any
import uuid

from ..shared.llm_client import get_llm_client
from ..shared.text_module import Claim
from ..config import Config
from ..resources.prompts import get_claim_extraction_prompt

logger = logging.getLogger(__name__)


class ClaimExtractor:
    """YouTube 영상 텍스트에서 팩트체킹이 필요한 주장을 추출하는 클래스"""

    def __init__(self):
        """ClaimExtractor를 초기화합니다."""
        self.max_claims = Config.RAG_MAX_CLAIMS
        logger.info(f"ClaimExtractor 초기화 - 최대 {self.max_claims}개 주장 추출")

    async def extract_claims(
        self,
        title: str,
        description: str,
        transcript: str = None,
        max_claims: int = None
    ) -> List[Claim]:
        """
        영상의 제목, 설명, 자막에서 팩트체킹이 필요한 주장을 추출합니다.

        LLM을 사용하여 검증 가능한 사실 주장을 식별하고 구조화합니다.

        Args:
            title (str): 영상 제목.
            description (str): 영상 설명.
            transcript (Optional[str]): 자막 텍스트.
            max_claims (Optional[int]): 최대 추출 개수 (None이면 Config 기본값 사용).

        Returns:
            List[Claim]: 추출된 Claim 객체 리스트.
        """
        try:
            # Claim 추출은 복잡한 추론보다는 정보 추출이므로 mini 모델 사용 (속도/비용 최적화)
            from ..shared.llm_client import LLMClient
            llm_client = LLMClient(model="gpt-4o-mini")
            max_count = max_claims if max_claims is not None else self.max_claims

            # 스크립트가 너무 길면 앞부분만 사용 (토큰 제한)
            script_text = ""
            if transcript:
                max_script_length = 50000  # 약 12.5k 토큰 (GPT-4o는 충분히 처리 가능)
                if len(transcript) > max_script_length:
                    script_text = transcript[:max_script_length] + "...(중략)"
                else:
                    script_text = transcript
            else:
                script_text = "자막 없음"

            prompt = get_claim_extraction_prompt(
                title=title,
                description=description,
                script_text=script_text,
                max_claims=max_count
            )

            messages = [{"role": "user", "content": prompt}]
            result = await llm_client.chat_completion_json(messages)
            raw_claims = result.get('claims', [])
            video_category = result.get('video_category', 'info')

            logger.info(f"영상 카테고리 분석 결과: {video_category}")
            
            # 비정보성 카테고리 필터링
            non_info_categories = ["entertainment", "humor", "daily", "other"]
            if video_category in non_info_categories:
                logger.info("비정보성 영상으로 판단되어 주장을 추출하지 않습니다.")
                return []

            # Claim 객체로 변환
            claims = []
            for raw in raw_claims:
                claim = self._structure_claim(raw)
                if claim:
                    claims.append(claim)

            logger.info(f"주장 추출 완료: {len(claims)}개")
            return claims

        except Exception as e:
            logger.error(f"주장 추출 중 오류: {e}", exc_info=True)
            return []

    def _structure_claim(self, raw_claim: Dict[str, Any]) -> Claim:
        """
        LLM 응답을 Claim 객체로 변환합니다.

        Args:
            raw_claim (Dict[str, Any]): LLM이 추출한 주장 딕셔너리.

        Returns:
            Optional[Claim]: 구조화된 Claim 객체. 실패 시 None.
        """
        try:
            return Claim(
                claim_id=str(uuid.uuid4()),
                claim_text=raw_claim.get('claim', ''),
                category=raw_claim.get('category', '일반'),
                importance=raw_claim.get('importance', 'medium')
            )
        except Exception as e:
            logger.error(f"Claim 구조화 실패: {e}, raw_claim={raw_claim}")
            return None

    def filter_by_importance(self, claims: List[Claim], min_importance: str = "medium") -> List[Claim]:
        """
        주장을 중요도 기준으로 필터링합니다.

        Args:
            claims (List[Claim]): 주장 목록.
            min_importance (str): 최소 중요도 ("high", "medium", "low").

        Returns:
            List[Claim]: 필터링된 주장 목록.
        """
        importance_order = {"high": 3, "medium": 2, "low": 1}
        min_level = importance_order.get(min_importance, 2)

        filtered = [
            claim for claim in claims
            if importance_order.get(claim.importance, 2) >= min_level
        ]

        logger.info(f"중요도 필터링: {len(claims)} -> {len(filtered)}개")
        return filtered

    def deduplicate_claims(self, claims: List[Claim]) -> List[Claim]:
        """
        중복된 주장을 제거합니다.

        단어 집합의 70% 이상이 겹치면 중복으로 간주합니다.

        Args:
            claims (List[Claim]): 주장 목록.

        Returns:
            List[Claim]: 중복 제거된 주장 목록.
        """
        if not claims:
            return []

        unique_claims = [claims[0]]

        for claim in claims[1:]:
            is_duplicate = False

            for unique_claim in unique_claims:
                # 단어 집합 비교
                text1 = set(claim.claim_text.lower().split())
                text2 = set(unique_claim.claim_text.lower().split())
                if len(text1 & text2) >= len(text1) * 0.7:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_claims.append(claim)

        logger.info(f"중복 제거: {len(claims)} -> {len(unique_claims)}개")
        return unique_claims


async def extract_claims_from_video(
    title: str,
    description: str,
    transcript: str = None,
    max_claims: int = None
) -> List[Claim]:
    """
    영상에서 주장을 추출하고 필터링하여 반환합니다.

    중요도 필터링(medium 이상)과 중복 제거를 자동으로 수행합니다.

    Args:
        title (str): 영상 제목.
        description (str): 영상 설명.
        transcript (Optional[str]): 자막.
        max_claims (Optional[int]): 최대 주장 수.

    Returns:
        List[Claim]: 필터링되고 중복 제거된 Claim 객체 리스트.
    """
    extractor = ClaimExtractor()
    claims = await extractor.extract_claims(title, description, transcript, max_claims)

    # 중요도 필터링 및 중복 제거
    claims = extractor.filter_by_importance(claims, min_importance="medium")
    claims = extractor.deduplicate_claims(claims)

    return claims
