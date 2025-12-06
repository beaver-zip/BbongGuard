"""검색 쿼리 생성 (LLM 기반 최적화)"""

import logging
from ..shared.text_module import Claim
from ..shared.llm_client import get_llm_client
from ..resources.prompts import get_query_builder_prompt

logger = logging.getLogger(__name__)

class QueryBuilder:
    """Claim을 최적화된 웹 검색 쿼리로 변환하는 클래스"""

    def __init__(self):
        logger.info("QueryBuilder(LLM) 초기화")

    async def build_search_query(self, claim: Claim) -> str:
        """
        LLM을 사용하여 주장에서 핵심 키워드를 추출, 검색 쿼리를 생성합니다.

        Args:
            claim (Claim): 검색 쿼리를 생성할 주장 객체.

        Returns:
            str: 생성된 검색 쿼리 문자열.
        """
        try:
            # 쿼리 생성은 단순 변환 작업이므로 mini 모델 사용
            from ..shared.llm_client import LLMClient
            llm = LLMClient(model="gpt-4o-mini")
            
            prompt = get_query_builder_prompt(claim.claim_text)
            
            messages = [{"role": "user", "content": prompt}]
            query = await llm.chat_completion(messages)
            
            # 불필요한 따옴표 제거 및 다듬기
            query = query.strip().replace('"', '').replace("'", "")
            
            logger.info(f"검색 쿼리 생성: '{claim.claim_text[:20]}...' -> '{query}'")
            return query

        except Exception as e:
            logger.error(f"쿼리 생성 실패: {e}. 기본 쿼리로 대체합니다.")
            # 실패 시 기본 키워드 조합 사용
            return f"{claim.claim_text} 뉴스 팩트체크"