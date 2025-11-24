"""검색 쿼리 생성"""

import logging
from ..shared.rag_models import Claim

logger = logging.getLogger(__name__)


class QueryBuilder:
    """Claim을 웹 검색 쿼리로 변환하는 클래스"""

    def __init__(self):
        """QueryBuilder를 초기화합니다."""
        logger.info("QueryBuilder 초기화")

    def build_search_query(self, claim: Claim) -> str:
        """
        주장을 팩트체크용 검색 쿼리로 변환합니다.

        신뢰할 수 있는 공식 출처의 뉴스나 발표를 우선적으로 검색하도록
        관련 키워드를 추가합니다.

        Args:
            claim: 검색할 주장 객체

        Returns:
            검색 엔진에 최적화된 쿼리 문자열
        """
        # 팩트체크 관련 키워드 추가
        query = f"{claim.claim_text} 뉴스 OR 보도 OR 발표 OR 공식"

        logger.debug(f"검색 쿼리 생성: {claim.claim_text[:50]}... -> {query}")
        return query
