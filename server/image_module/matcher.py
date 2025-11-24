"""이미지-주장 매칭"""

import logging
import numpy as np
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from ..shared.schemas import Claim, FrameFeature
from ..config import Config

logger = logging.getLogger(__name__)

class ImageClaimMatcher:
    """주장(Text)과 프레임(Image) 간의 유사도를 계산하여 매칭하는 클래스"""

    def __init__(self, model_name: str = 'clip-ViT-B-32-multilingual-v1'):
        """
        Matcher 초기화
        
        Args:
            model_name: 사용할 CLIP 모델 이름 (FeatureExtractor와 동일해야 함)
        """
        self.device = "cpu" # 매칭은 연산량이 적으므로 CPU로 충분할 수 있음, 필요시 변경
        try:
            self.model = SentenceTransformer(model_name, device=self.device)
            logger.info(f"ImageClaimMatcher 초기화 완료 (Model: {model_name})")
        except Exception as e:
            logger.error(f"매칭 모델 로드 실패: {e}")
            raise

    def select_top_frames(
        self, 
        claim: Claim, 
        frame_features: List[Dict[str, Any]], 
        top_k: int = 3
    ) -> List[FrameFeature]:
        """
        주장과 가장 관련성 높은 상위 K개 프레임을 선택합니다.

        Args:
            claim: 대상 주장
            frame_features: 특징이 추출된 프레임 리스트
            top_k: 선택할 프레임 수

        Returns:
            선택된 FrameFeature 리스트
        """
        if not frame_features:
            return []

        try:
            # 1. 주장 텍스트 임베딩
            text_embedding = self.model.encode([claim.claim_text])

            # 2. 프레임 이미지 임베딩 가져오기
            image_embeddings = np.array([f['embedding'] for f in frame_features])

            # 3. 코사인 유사도 계산
            similarities = cosine_similarity(text_embedding, image_embeddings)[0]

            # 4. 점수 매핑 및 정렬
            scored_frames = []
            for i, frame in enumerate(frame_features):
                score = float(similarities[i])
                
                # FrameFeature 객체 생성
                frame_obj = FrameFeature(
                    frame_id=frame['frame_id'],
                    timestamp=frame['timestamp'],
                    ocr_text=frame.get('ocr_text', ''),
                    caption=frame.get('caption', ''), # 현재는 caption이 없으므로 빈 문자열
                    relevance_score=score
                )
                scored_frames.append(frame_obj)

            # 점수 내림차순 정렬
            scored_frames.sort(key=lambda x: x.relevance_score, reverse=True)

            # 상위 K개 선택
            selected = scored_frames[:top_k]
            
            logger.debug(f"Claim '{claim.claim_text[:20]}...' 관련 프레임 {len(selected)}개 선택 (Max Score: {selected[0].relevance_score:.4f})")
            
            return selected

        except Exception as e:
            logger.error(f"프레임 매칭 실패: {e}", exc_info=True)
            return []
