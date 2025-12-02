"""검색 쿼리 생성 (LLM 기반 최적화)"""

import logging
from ..shared.rag_models import Claim
from ..shared.llm_client import get_llm_client

logger = logging.getLogger(__name__)

class QueryBuilder:
    """Claim을 최적화된 웹 검색 쿼리로 변환하는 클래스"""

    def __init__(self):
        logger.info("QueryBuilder(LLM) 초기화")

    async def build_search_query(self, claim: Claim) -> str:
        """
        LLM을 사용하여 주장에서 핵심 키워드를 추출, 검색 쿼리를 생성합니다.
        """
        try:
            llm = await get_llm_client()
            
            prompt = f"""
            당신은 검색 엔진 최적화(SEO) 전문가입니다. 
            다음 주장(Claim)을 검증하기 위해, 구글/네이버 등에서 가장 정확한 검색 결과를 얻을 수 있는 '검색 쿼리'를 작성하세요.

            [주장]
            "{claim.claim_text}"

            [규칙]
            1. 불필요한 조사나 서술어는 제거하고, **핵심 키워드(Entity)** 위주로 구성하세요.
            2. 주장의 시점이나 고유명사가 있다면 반드시 포함하세요.
            3. 쿼리는 한 줄의 문자열로만 반환하세요. (따옴표 없이)
            
            예시:
            주장: "어제 손흥민이 해트트릭을 기록했다."
            쿼리: 손흥민 해트트릭 경기 결과 골 모음
            """
            
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