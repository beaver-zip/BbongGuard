"""증거 순위 매김"""

import logging
from typing import List, Dict, Any
from datetime import datetime
import math
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from ..shared.text_module import Claim, Evidence
from ..config import Config

logger = logging.getLogger(__name__)


class EvidenceRanker:
    """코사인 유사도를 사용하여 증거의 관련성 순위를 매기는 클래스"""

    def __init__(self):
        """EvidenceRanker를 초기화하고 임베딩 모델을 로드합니다."""
        self.top_k = Config.RAG_TOP_EVIDENCE

        try:
            self.embedding_model = SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')
            logger.info(f"EvidenceRanker 초기화 - 상위 {self.top_k}개 선택, 모델 로드 완료")
        except Exception as e:
            logger.error(f"임베딩 모델 로드 실패: {e}")
            raise

    def calculate_recency_score(self, published_date: str) -> float:
        """
        발행일로부터 경과 시간을 기반으로 최신성 점수를 계산합니다.

        지수 감쇠를 사용하여 최근 콘텐츠일수록 높은 점수를 부여합니다.

        Args:
            published_date (str): ISO 형식의 발행일 문자열.

        Returns:
            float: 0~1 범위의 최신성 점수. 날짜가 없으면 0.7 반환.
        """
        if not published_date:
            return 0.7

        try:
            pub_date = datetime.fromisoformat(published_date.replace('Z', '+00:00'))
            now = datetime.now(pub_date.tzinfo)
            days_ago = (now - pub_date).days

            # 지수 감쇠 (365일 반감기)
            score = math.exp(-days_ago / 365)
            return max(0.0, min(1.0, score))

        except Exception as e:
            logger.warning(f"날짜 파싱 실패: {published_date}, {e}")
            return 0.7

    def calculate_combined_score(
        self,
        relevance_score: float,
        domain_score: float,
        recency_score: float,
        weights: Dict[str, float] = None
    ) -> float:
        """
        관련성, 신뢰도, 최신성 점수를 가중 평균하여 최종 점수를 계산합니다.

        기본 가중치: 관련성 40%, 신뢰도 40%, 최신성 20%.

        Args:
            relevance_score (float): 주장과의 관련성 점수 (0~1).
            domain_score (float): 출처 도메인 신뢰도 (0~1).
            recency_score (float): 최신성 점수 (0~1).
            weights (Optional[Dict[str, float]]): 커스텀 가중치 딕셔너리.

        Returns:
            float: 0~1 범위의 종합 점수.
        """
        if weights is None:
            weights = {
                'relevance': 0.4,
                'domain': 0.2,
                'recency': 0.4  # 영상 게시일 기준 날짜 근접성
            }

        score = (
            relevance_score * weights['relevance'] +
            domain_score * weights['domain'] +
            recency_score * weights['recency']
        )

        return score

    async def rank_evidence(
        self,
        claim: Claim,
        evidence_list: List[Dict[str, Any]]
    ) -> List[Evidence]:
        """
        증거를 주장과의 관련성, 신뢰도, 최신성을 종합하여 순위를 매깁니다.

        임베딩 모델을 사용하여 주장과 증거 간의 의미적 유사도를 계산합니다.

        Args:
            claim (Claim): 순위를 매길 대상 주장.
            evidence_list (List[Dict[str, Any]]): 순위를 매길 증거 딕셔너리 리스트.

        Returns:
            List[Evidence]: 종합 점수 기준으로 정렬된 Evidence 객체 리스트.
        """
        if not evidence_list:
            logger.warning("Evidence가 없습니다")
            return []

        try:
            # 텍스트 준비
            claim_text = claim.claim_text
            evidence_texts = [
                f"{ev.get('source_title', '')} {ev.get('snippet', '')}"
                for ev in evidence_list
            ]

            # 임베딩 생성
            claim_embedding = self.embedding_model.encode([claim_text])
            evidence_embeddings = self.embedding_model.encode(evidence_texts)

            # 코사인 유사도 계산
            similarities = cosine_similarity(claim_embedding, evidence_embeddings)[0]

            # 각 증거에 종합 점수 계산
            scored_evidence = []

            for i, ev in enumerate(evidence_list):
                relevance_score = float(np.clip(similarities[i], 0.0, 1.0))
                domain_score = ev.get('domain_score', 0.5)
                
                # date_diff_days가 있으면 영상 게시일 기준 점수 사용 (rerank_by_date에서 계산됨)
                date_diff_days = ev.get('date_diff_days')
                
                if date_diff_days is not None:
                    # 날짜 차이 절댓값 기반 점수 (지수 감쇠, 30일 반감기)
                    recency_score = math.exp(-date_diff_days / 30)
                else:
                    recency_score = self.calculate_recency_score(ev.get('published_date'))

                combined_score = self.calculate_combined_score(
                    relevance_score, domain_score, recency_score
                )

                evidence = Evidence(
                    source_title=ev.get('source_title', 'Unknown'),
                    source_url=ev.get('source_url', ''),
                    domain=ev.get('domain', ''),
                    snippet=ev.get('snippet', ''),
                    published_date=ev.get('published_date')
                )

                scored_evidence.append({
                    'evidence': evidence,
                    'combined_score': combined_score,
                    'date_diff_days': date_diff_days if date_diff_days is not None else 3650,
                    'recency_score': recency_score,
                    'relevance_score': relevance_score,
                    'domain_score': domain_score
                })

            # 정렬: (1) date_diff_days 낮은 순 (2) combined_score 높은 순
            scored_evidence.sort(
                key=lambda x: (x['date_diff_days'], -x['combined_score'])
            )
            
            ranked_evidence = [item['evidence'] for item in scored_evidence]
            
            # 정렬 결과 로깅
            logger.info(f"Evidence 순위 매김 완료: {len(ranked_evidence)}개")
            for idx, item in enumerate(scored_evidence[:5]):  # 상위 5개만 로그
                logger.info(
                    f"  #{idx+1}: {item['evidence'].source_title[:40]} | "
                    f"diff={item['date_diff_days']}일 | "
                    f"combined={item['combined_score']:.3f}"
                )
            return ranked_evidence

        except Exception as e:
            logger.error(f"Evidence 순위 매김 실패: {e}", exc_info=True)
            return []

    def select_top_evidence(
        self,
        ranked_evidence: List[Evidence],
        top_k: int = None
    ) -> List[Evidence]:
        """
        순위가 매겨진 증거 중 상위 K개를 선택합니다.

        Args:
            ranked_evidence (List[Evidence]): 순위가 매겨진 증거 리스트.
            top_k (Optional[int]): 선택할 개수 (None이면 Config 기본값).

        Returns:
            List[Evidence]: 상위 K개 증거 리스트.
        """
        k = top_k if top_k is not None else self.top_k
        selected = ranked_evidence[:k]

        logger.info(f"상위 {len(selected)}개 Evidence 선택")
        return selected

    async def rank_and_select(
        self,
        claim: Claim,
        evidence_list: List[Dict[str, Any]],
        top_k: int = None
    ) -> List[Evidence]:
        """
        증거 순위 매김과 상위 K개 선택을 한 번에 수행합니다.

        Args:
            claim (Claim): 대상 주장.
            evidence_list (List[Dict[str, Any]]): 증거 딕셔너리 리스트.
            top_k (Optional[int]): 선택할 개수.

        Returns:
            List[Evidence]: 상위 K개 증거 객체 리스트.
        """
        ranked = await self.rank_evidence(claim, evidence_list)
        selected = self.select_top_evidence(ranked, top_k)
        return selected
