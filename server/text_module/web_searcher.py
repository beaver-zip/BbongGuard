"""웹 검색 및 필터링"""

import logging
from typing import List, Dict, Any
from tavily import TavilyClient

from ..shared.rag_models import Claim
from ..shared.source_manager import get_source_manager
from ..config import Config
from .query_builder import QueryBuilder

logger = logging.getLogger(__name__)


class WebSearcher:
    """Tavily API를 사용하여 주장을 검증할 웹 증거를 검색하는 클래스"""

    def __init__(self):
        """WebSearcher를 초기화합니다."""
        if not Config.TAVILY_API_KEY:
            raise ValueError("TAVILY_API_KEY가 설정되지 않았습니다")

        self.client = TavilyClient(api_key=Config.TAVILY_API_KEY)
        self.query_builder = QueryBuilder()
        self.source_manager = get_source_manager()
        self.max_results = Config.RAG_MAX_SEARCH_RESULTS

        logger.info("WebSearcher 초기화 완료")

    async def search_claim(self, claim: Claim) -> List[Dict[str, Any]]:
        """
        주장에 대해 Tavily 웹 검색을 수행합니다.

        Args:
            claim: 검색할 주장 객체

        Returns:
            Tavily API 원시 검색 결과 리스트
        """
        try:
            # 검색 쿼리 생성
            query = self.query_builder.build_search_query(claim)

            logger.info(f"웹 검색 시작: {query}")

            # Tavily 검색
            response = self.client.search(
                query=query,
                search_depth="advanced",
                max_results=self.max_results,
                include_answer=False,
                include_raw_content=False,
                include_domains=self._get_include_domains()
            )

            results = response.get('results', [])
            logger.info(f"웹 검색 완료: {len(results)}개 결과")

            return results

        except Exception as e:
            logger.error(f"웹 검색 실패: {e}", exc_info=True)
            return []

    def _get_include_domains(self) -> List[str]:
        """
        화이트리스트에서 신뢰할 수 있는 도메인 목록을 가져옵니다.

        와일드카드를 제거하고 Tavily API에서 사용 가능한 형식으로 변환합니다.

        Returns:
            검색에 포함할 도메인 리스트
        """
        include_domains = []

        for tier_name in ['tier1', 'tier2', 'tier3']:
            if tier_name in self.source_manager.whitelist:
                tier_info = self.source_manager.whitelist[tier_name]
                if 'domains' in tier_info:
                    # 와일드카드 제거
                    domains = [d for d in tier_info['domains'] if '*' not in d]
                    include_domains.extend(domains)

        return include_domains

    def filter_and_format_results(
        self,
        raw_results: List[Dict[str, Any]],
        claim: Claim
    ) -> List[Dict[str, Any]]:
        """
        검색 결과를 블랙리스트와 신뢰도 기준으로 필터링하고 Evidence 형식으로 변환합니다.

        신뢰도 0.5 미만의 출처는 제외됩니다.

        Args:
            raw_results: Tavily 원시 검색 결과
            claim: 연관된 주장 객체

        Returns:
            필터링되고 포맷팅된 Evidence 딕셔너리 리스트
        """
        filtered_evidence = []

        for result in raw_results:
            url = result.get('url', '')

            # 블랙리스트 필터링
            if self.source_manager.is_blacklisted(url):
                logger.debug(f"블랙리스트 필터링: {url}")
                continue

            # 도메인 신뢰도 계산
            credibility_info = self.source_manager.get_credibility_info(url, claim.category)
            domain_score = credibility_info['final_score']

            # 신뢰도 기준 미달 필터링
            if domain_score < 0.5:
                logger.debug(f"신뢰도 미달 ({domain_score:.2f}): {url}")
                continue

            # Evidence 형식으로 변환
            evidence = {
                'source_title': result.get('title', 'Unknown'),
                'source_url': url,
                'domain': self.source_manager.extract_domain(url),
                'snippet': result.get('content', '')[:500],
                'published_date': result.get('published_date') or '',
                'domain_score': domain_score,
                'relevance_score': result.get('score', 0.5),
                'recency_score': 1.0
            }

            filtered_evidence.append(evidence)

        # 도메인 신뢰도 순 정렬
        filtered_evidence.sort(key=lambda x: x['domain_score'], reverse=True)

        logger.info(f"필터링 완료: {len(raw_results)} -> {len(filtered_evidence)}개")
        return filtered_evidence

    async def search_and_filter(self, claim: Claim) -> List[Dict[str, Any]]:
        """
        웹 검색과 필터링을 한 번에 수행합니다.

        Args:
            claim: 검색할 주장 객체

        Returns:
            필터링된 Evidence 딕셔너리 리스트
        """
        raw_results = await self.search_claim(claim)
        evidence_list = self.filter_and_format_results(raw_results, claim)
        return evidence_list
