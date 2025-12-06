"""웹 검색 및 필터링"""

import logging
import asyncio
from typing import List, Dict, Any
from tavily import TavilyClient
import dateparser
from datetime import datetime

from ..shared.text_module import Claim
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
            claim (Claim): 검색할 주장.

        Returns:
            List[Dict[str, Any]]: 검색 결과 리스트.
        """
        try:
            query = await self.query_builder.build_search_query(claim)

            logger.info(f"웹 검색 시작: {query}")

            # Tavily 검색 (Blocking I/O)을 비동기 스레드로 실행
            response = await asyncio.to_thread(
                self.client.search,
                query=query,
                search_depth="advanced",
                max_results=self.max_results,
                include_answer=False,
                include_raw_content=False
            )

            results = response.get('results', [])
            logger.info(f"웹 검색 완료: {len(results)}개 결과")

            return results

        except Exception as e:
            logger.error(f"웹 검색 실패: {e}", exc_info=True)
            return []

    def filter_and_format_results(
        self,
        raw_results: List[Dict[str, Any]],
        claim: Claim
    ) -> List[Dict[str, Any]]:
        """
        검색 결과를 블랙리스트와 신뢰도 기준으로 필터링하고 Evidence 형식으로 변환합니다.

        Args:
            raw_results (List[Dict[str, Any]]): Tavily 검색 결과 원본.
            claim (Claim): 관련 주장 (카테고리 확인용).

        Returns:
            List[Dict[str, Any]]: 필터링 및 포맷팅된 증거 리스트.
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

            # 신뢰도 기준 완화 (0.1)
            if domain_score < 0.1:
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

    def rerank_by_date(
        self,
        evidence_list: List[Dict[str, Any]],
        video_published_at_str: str
    ) -> List[Dict[str, Any]]:
        """
        영상 게시일과 증거 게시일의 차이를 기준으로 증거를 재정렬합니다.

        영상 게시일과 가까운 증거일수록 높은 우선순위를 가집니다.

        Args:
            evidence_list (List[Dict[str, Any]]): 증거 리스트.
            video_published_at_str (str): 영상 게시일 문자열.

        Returns:
            List[Dict[str, Any]]: 날짜순으로 재정렬된 증거 리스트.
        """
        if not video_published_at_str:
            logger.warning("영상 게시일 정보가 없어 날짜 재정렬을 건너뜁니다.")
            return evidence_list

        try:
            video_published_at = dateparser.parse(video_published_at_str)
            if not video_published_at:
                logger.warning(f"영상 게시일 파싱 실패: {video_published_at_str}")
                return evidence_list
        except Exception as e:
            logger.error(f"영상 게시일 파싱 중 오류 발생: {e}")
            return evidence_list
            
        for evidence in evidence_list:
            evidence_date_str = evidence.get('published_date')
            if not evidence_date_str:
                evidence['date_diff_days'] = 3650  # 10년, 날짜 없는 경우 최하 순위
                continue

            try:
                evidence_date = dateparser.parse(evidence_date_str)
                if evidence_date:
                    time_difference = abs((video_published_at - evidence_date).days)
                    evidence['date_diff_days'] = time_difference
                else:
                    evidence['date_diff_days'] = 3650
            except Exception:
                evidence['date_diff_days'] = 3650
        
        # 날짜 차이가 적은 순으로 정렬
        evidence_list.sort(key=lambda x: x.get('date_diff_days', 3650))
        
        logger.info("증거 목록 날짜순 재정렬 완료")
        return evidence_list


    async def search_and_filter(self, claim: Claim) -> List[Dict[str, Any]]:
        """
        웹 검색과 필터링을 한 번에 수행합니다.

        Args:
            claim (Claim): 검색할 주장.

        Returns:
            List[Dict[str, Any]]: 필터링된 증거 리스트.
        """
        raw_results = await self.search_claim(claim)
        evidence_list = self.filter_and_format_results(raw_results, claim)
        return evidence_list