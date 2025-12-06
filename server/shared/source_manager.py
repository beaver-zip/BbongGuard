"""
출처 신뢰도 관리 시스템
화이트리스트/블랙리스트 기반 도메인 신뢰도 평가
"""

import json
import logging
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
import re

from ..config import Config

logger = logging.getLogger(__name__)


class SourceManager:
    """출처 신뢰도 관리자"""

    def __init__(self):
        """화이트리스트 및 블랙리스트 로드"""
        self.whitelist = self._load_whitelist()
        self.blacklist = self._load_blacklist()
        logger.info(f"SourceManager 초기화 완료 - 화이트리스트 {len(self._get_all_white_domains())}개, 블랙리스트 {len(self.blacklist)}개")

    def _load_whitelist(self) -> Dict:
        """화이트리스트 JSON 로드"""
        try:
            with open(Config.WHITELIST_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"화이트리스트 파일을 찾을 수 없습니다: {Config.WHITELIST_PATH}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"화이트리스트 JSON 파싱 오류: {e}")
            return {}

    def _load_blacklist(self) -> List[str]:
        """블랙리스트 JSON 로드"""
        try:
            with open(Config.BLACKLIST_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('domains', [])
        except FileNotFoundError:
            logger.error(f"블랙리스트 파일을 찾을 수 없습니다: {Config.BLACKLIST_PATH}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"블랙리스트 JSON 파싱 오류: {e}")
            return []

    def _get_all_white_domains(self) -> List[str]:
        """모든 화이트리스트 도메인 목록"""
        domains = []
"""
출처 신뢰도 관리 시스템
화이트리스트/블랙리스트 기반 도메인 신뢰도 평가
"""

import json
import logging
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
import re

from ..config import Config

logger = logging.getLogger(__name__)


class SourceManager:
    """출처 신뢰도 관리자"""

    def __init__(self):
        """화이트리스트 및 블랙리스트 로드"""
        self.whitelist = self._load_whitelist()
        self.blacklist = self._load_blacklist()
        logger.info(f"SourceManager 초기화 완료 - 화이트리스트 {len(self._get_all_white_domains())}개, 블랙리스트 {len(self.blacklist)}개")

    def _load_whitelist(self) -> Dict:
        """화이트리스트 JSON 로드"""
        try:
            with open(Config.WHITELIST_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"화이트리스트 파일을 찾을 수 없습니다: {Config.WHITELIST_PATH}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"화이트리스트 JSON 파싱 오류: {e}")
            return {}

    def _load_blacklist(self) -> List[str]:
        """블랙리스트 JSON 로드"""
        try:
            with open(Config.BLACKLIST_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('domains', [])
        except FileNotFoundError:
            logger.error(f"블랙리스트 파일을 찾을 수 없습니다: {Config.BLACKLIST_PATH}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"블랙리스트 JSON 파싱 오류: {e}")
            return []

    def _get_all_white_domains(self) -> List[str]:
        """모든 화이트리스트 도메인 목록"""
        domains = []
        for tier_info in self.whitelist.values():
            if isinstance(tier_info, dict) and 'domains' in tier_info:
                domains.extend(tier_info['domains'])
        return domains

    def extract_domain(self, url: str) -> str:
        """
        URL에서 도메인을 추출합니다.

        Args:
            url (str): 분석할 URL.

        Returns:
            str: 추출된 도메인 (예: naver.com). 추출 실패 시 빈 문자열.
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # www. 제거
            if domain.startswith('www.'):
                domain = domain[4:]

            return domain
        except Exception as e:
            logger.warning(f"도메인 추출 실패: {url}, {e}")
            return ""

    def is_blacklisted(self, url: str) -> bool:
        """
        URL이 블랙리스트에 포함되어 있는지 확인합니다.

        Args:
            url (str): 확인할 URL.

        Returns:
            bool: 블랙리스트 포함 여부.
        """
        domain = self.extract_domain(url)

        for blacklisted in self.blacklist:
            # 완전 일치 또는 하위 도메인 체크
            if domain == blacklisted or domain.endswith('.' + blacklisted):
                logger.debug(f"블랙리스트 도메인 감지: {domain}")
                return True

        return False

    def get_domain_tier(self, url: str) -> Optional[str]:
        """
        URL의 신뢰도 등급(Tier)을 반환합니다.

        Args:
            url (str): 확인할 URL.

        Returns:
            Optional[str]: 등급 이름 (예: tier1). 화이트리스트에 없으면 None.
        """
        domain = self.extract_domain(url)

        for tier_name, tier_info in self.whitelist.items():
            if not isinstance(tier_info, dict) or 'domains' not in tier_info:
                continue

            for trusted_domain in tier_info['domains']:
                # 완전 일치
                if domain == trusted_domain:
                    return tier_name

                # 와일드카드 매칭 (예: *.ac.kr)
                if '*' in trusted_domain:
                    pattern = trusted_domain.replace('.', r'\.').replace('*', '.*')
                    if re.match(f'^{pattern}$', domain):
                        return tier_name

                # 하위 도메인 체크 (예: news.kbs.co.kr → kbs.co.kr)
                if domain.endswith('.' + trusted_domain):
                    return tier_name

        return None

    def get_domain_score(self, url: str) -> float:
        """
        URL의 신뢰도 점수를 반환합니다 (0.0 ~ 1.0).

        Args:
            url (str): 확인할 URL.

        Returns:
            float: 신뢰도 점수.
        """
        # 블랙리스트 체크
        if self.is_blacklisted(url):
            return 0.0

        # 화이트리스트 등급별 점수
        tier = self.get_domain_tier(url)
        if tier and tier in self.whitelist:
            return self.whitelist[tier].get('score', 0.5)

        # 화이트리스트에 없으면 낮은 기본 점수
        return 0.3

    def get_credibility_info(self, url: str, category: Optional[str] = None) -> Dict:
        """
        URL의 종합 신뢰도 정보를 반환합니다.

        Args:
            url (str): 확인할 URL.
            category (Optional[str]): 콘텐츠 카테고리 (일치 여부 확인용).

        Returns:
            Dict: 신뢰도 정보 (domain, tier, score, is_blacklisted 등).
        """
        domain = self.extract_domain(url)
        tier = self.get_domain_tier(url)
        base_score = self.get_domain_score(url)

        # 카테고리 일치 여부 확인
        category_match = True
        if tier and category and tier in self.whitelist:
            tier_info = self.whitelist[tier]
            if 'categories' in tier_info:
                category_match = category in tier_info['categories']

        # 카테고리 불일치 시 점수 감점
        final_score = base_score if category_match else base_score * 0.7

        return {
            'domain': domain,
            'tier': tier,
            'base_score': base_score,
            'final_score': final_score,
            'category_match': category_match,
            'is_blacklisted': self.is_blacklisted(url),
            'is_whitelisted': tier is not None
        }

    def filter_trusted_sources(
        self,
        urls: List[str],
        min_score: float = 0.5,
        category: Optional[str] = None
    ) -> List[Tuple[str, float]]:
        """
        신뢰할 수 있는 출처만 필터링합니다.

        Args:
            urls (List[str]): URL 목록.
            min_score (float): 최소 신뢰도 점수.
            category (Optional[str]): 콘텐츠 카테고리.

        Returns:
            List[Tuple[str, float]]: (URL, 신뢰도 점수) 튜플 리스트. 점수 내림차순 정렬.
        """
        filtered = []

        for url in urls:
            info = self.get_credibility_info(url, category)

            if info['is_blacklisted']:
                continue

            if info['final_score'] >= min_score:
                filtered.append((url, info['final_score']))

        # 신뢰도 점수 내림차순 정렬
        filtered.sort(key=lambda x: x[1], reverse=True)

        return filtered

    def get_tier_description(self, tier: str) -> str:
        """
        등급에 대한 설명을 반환합니다.

        Args:
            tier (str): 등급 이름.

        Returns:
            str: 등급 설명.
        """
        if tier in self.whitelist:
            return self.whitelist[tier].get('description', '알 수 없음')
        return '알 수 없음'


# 싱글톤 인스턴스
_source_manager_instance: Optional[SourceManager] = None


def get_source_manager() -> SourceManager:
    """
    SourceManager의 싱글톤 인스턴스를 반환합니다.

    Returns:
        SourceManager: 초기화된 SourceManager 인스턴스.
    """
    global _source_manager_instance

    if _source_manager_instance is None:
        _source_manager_instance = SourceManager()

    return _source_manager_instance
