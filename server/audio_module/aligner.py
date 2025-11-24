"""자막-주장 정렬 및 구간 추출"""

import logging
import numpy as np
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from ..shared.schemas import Claim, AudioSegment, VideoMeta
from ..config import Config

logger = logging.getLogger(__name__)

class TranscriptAligner:
    """주장(Claim)과 자막(Transcript)을 매칭하여 관련 오디오 구간을 찾는 클래스"""

    def __init__(self, model_name: str = 'paraphrase-multilingual-mpnet-base-v2'):
        """
        Aligner 초기화
        
        Args:
            model_name: 텍스트 임베딩 모델 이름 (TextModule과 동일한 모델 권장)
        """
        self.device = "cpu" 
        try:
            self.model = SentenceTransformer(model_name, device=self.device)
            logger.info(f"TranscriptAligner 초기화 완료 (Model: {model_name})")
        except Exception as e:
            logger.error(f"임베딩 모델 로드 실패: {e}")
            raise

    def find_segments_for_claim(
        self, 
        claim: Claim, 
        transcript: List[Dict[str, Any]], 
        window_sec: float = 5.0,
        threshold: float = 0.3
    ) -> List[AudioSegment]:
        """
        주장과 관련된 자막 구간을 찾고 전후 시간을 확장하여 반환합니다.

        Args:
            claim: 대상 주장
            transcript: 자막 리스트 [{'text':..., 'start':..., 'end':...}]
            window_sec: 앞뒤 확장 시간 (초)
            threshold: 유사도 임계값

        Returns:
            관련 AudioSegment 리스트
        """
        if not transcript:
            return []

        try:
            # 1. 주장 임베딩
            claim_embedding = self.model.encode([claim.claim_text])

            # 2. 자막 임베딩 (배치 처리)
            transcript_texts = [t['text'] for t in transcript]
            transcript_embeddings = self.model.encode(transcript_texts)

            # 3. 유사도 계산
            similarities = cosine_similarity(claim_embedding, transcript_embeddings)[0]

            # 4. 관련 구간 선택
            segments = []
            for i, score in enumerate(similarities):
                if score >= threshold:
                    t = transcript[i]
                    
                    # 구간 확장
                    start_time = max(0.0, float(t['start']) - window_sec)
                    end_time = float(t['start']) + float(t['duration']) + window_sec
                    
                    segment = AudioSegment(
                        segment_id=f"S{i:03d}",
                        start=start_time,
                        end=end_time,
                        transcript_text=t['text'],
                        relevance_score=float(score)
                    )
                    segments.append(segment)

            # 5. 중복/인접 구간 병합 (선택 사항, 여기서는 단순 상위 K개 선택으로 대체 가능)
            # 점수순 정렬 후 상위 3개만 반환
            segments.sort(key=lambda x: x.relevance_score, reverse=True)
            selected = segments[:3]
            
            logger.debug(f"Claim '{claim.claim_text[:20]}...' 관련 오디오 구간 {len(selected)}개 선택")
            return selected

        except Exception as e:
            logger.error(f"자막 정렬 실패: {e}", exc_info=True)
            return []
