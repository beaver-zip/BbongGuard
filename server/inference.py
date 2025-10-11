"""
추론 엔진 - 가짜뉴스 판정 로직
싱글톤 패턴으로 모델을 한 번만 로드하여 성능 최적화
"""

import numpy as np
from gensim.models.doc2vec import Doc2Vec
import tensorflow as tf
from typing import Dict, List, Optional
import logging

from .config import Config
from .preprocessor import DataPreprocessor

logger = logging.getLogger(__name__)


class InferenceEngine:
    """
    가짜뉴스 추론 엔진 (싱글톤)
    서버 시작 시 모델을 한 번 로드하고 재사용
    """

    _instance: Optional['InferenceEngine'] = None
    _initialized: bool = False

    def __new__(cls):
        """싱글톤 패턴: 인스턴스가 없으면 생성, 있으면 재사용"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """초기화는 한 번만 수행"""
        if not InferenceEngine._initialized:
            logger.info("추론 엔진 초기화 중...")
            self._initialize_models()
            InferenceEngine._initialized = True
            logger.info("추론 엔진 초기화 완료")

    def _initialize_models(self):
        """모델 로딩"""
        try:
            # Doc2Vec 모델 로드
            logger.info(f"Doc2Vec 모델 로딩: {Config.DOC2VEC_MODEL_PATH}")
            self.doc2vec_model = Doc2Vec.load(str(Config.DOC2VEC_MODEL_PATH))
            self.doc2vec_loaded = True
            logger.info(f"  ✓ Doc2Vec 벡터 크기: {self.doc2vec_model.vector_size}")

        except Exception as e:
            logger.error(f"Doc2Vec 모델 로딩 실패: {e}")
            self.doc2vec_model = None
            self.doc2vec_loaded = False
            raise

        try:
            # CNN 모델 로드
            logger.info(f"CNN 모델 로딩: {Config.CNN_MODEL_PATH}")
            self.cnn_model = tf.keras.models.load_model(str(Config.CNN_MODEL_PATH))
            self.cnn_loaded = True
            logger.info(f"  ✓ CNN 모델 로딩 완료")

        except Exception as e:
            logger.error(f"CNN 모델 로딩 실패: {e}")
            self.cnn_model = None
            self.cnn_loaded = False
            raise

        # 전처리기 초기화
        self.preprocessor = DataPreprocessor()

        logger.info("모든 모델 로딩 완료")

    def is_ready(self) -> bool:
        """모델이 준비되었는지 확인"""
        return self.doc2vec_loaded and self.cnn_loaded

    def _vectorize_text(self, tokens: List[str]) -> np.ndarray:
        """
        토큰 리스트를 Doc2Vec 벡터로 변환

        Args:
            tokens: 토큰 리스트

        Returns:
            100차원 벡터
        """
        if not tokens:
            return np.zeros(Config.DOC2VEC_VECTOR_SIZE)

        try:
            vector = self.doc2vec_model.infer_vector(tokens)
        except Exception as e:
            logger.warning(f"벡터화 실패, 제로 벡터 반환: {e}")
            vector = np.zeros(Config.DOC2VEC_VECTOR_SIZE)

        return vector

    def _prepare_model_input(
        self,
        original_processed: Dict,
        related_processed: List[Dict]
    ) -> List[np.ndarray]:
        """
        모델 입력 데이터 준비

        Args:
            original_processed: 전처리된 원본 영상 데이터
            related_processed: 전처리된 관련 영상 데이터 리스트 (최대 9개)

        Returns:
            CNN 모델 입력 형식 [original_vector, related1, ..., related9]
        """
        text_types = Config.TEXT_COMBINATIONS[Config.CURRENT_TEXT_COMBINATION]

        # 원본 영상 벡터화
        original_tokens = self.preprocessor.combine_texts(original_processed, text_types)
        original_vector = self._vectorize_text(original_tokens).reshape(100, 1)

        if Config.USE_RELATED_VIDEOS:
            # 관련 영상 포함 (OR 모델)
            input_data = [original_vector.reshape(1, 100, 1)]

            # 관련 영상 9개 벡터화 (부족하면 제로 패딩)
            for i in range(Config.NUM_RELATED_VIDEOS):
                if i < len(related_processed):
                    related_tokens = self.preprocessor.combine_texts(
                        related_processed[i], text_types
                    )
                    related_vector = self._vectorize_text(related_tokens).reshape(100, 1)
                else:
                    # 부족한 경우 제로 벡터
                    related_vector = np.zeros((100, 1))

                input_data.append(related_vector.reshape(1, 100, 1))

            logger.debug(
                f"입력 데이터 준비 완료: 원본 1개 + 관련 {len(related_processed)}개"
            )
        else:
            # 원본만 사용 (O 모델)
            input_data = [original_vector.reshape(1, 100, 1)]
            logger.debug("입력 데이터 준비 완료: 원본 1개")

        return input_data

    def predict(self, video_data: Dict) -> Dict:
        """
        영상 데이터를 분석하여 Fake/Real 판정

        Args:
            video_data: {
                'videoId': str,
                'title': str,
                'description': str,
                'comments': List[str],
                'relatedVideos': List[Dict]
            }

        Returns:
            {
                'prediction': 'Fake' | 'Real',
                'fakeProbability': float,
                'confidence': float,
                'details': {...}
            }
        """
        if not self.is_ready():
            raise RuntimeError("모델이 로딩되지 않았습니다")

        logger.info(f"영상 분석 시작: {video_data.get('videoId', 'unknown')}")

        # 1. 댓글 리스트를 텍스트로 변환
        comments = video_data.get('comments', [])
        if isinstance(comments, list):
            comment_text = ' '.join(comments)
        else:
            comment_text = str(comments)

        # 2. 원본 영상 전처리
        original_data = {
            'videoId': video_data.get('videoId', ''),
            'title': video_data.get('title', ''),
            'description': video_data.get('description', ''),
            'comment': comment_text
        }
        original_processed = self.preprocessor.preprocess_video_data(original_data)

        # 3. 관련 영상 전처리
        related_videos = video_data.get('relatedVideos', [])
        related_processed = []

        for related in related_videos:
            # 관련 영상도 댓글이 있으면 처리
            related_comments = related.get('comments', [])
            if isinstance(related_comments, list):
                related_comment_text = ' '.join(related_comments)
            else:
                related_comment_text = str(related_comments)

            related_data = {
                'videoId': related.get('videoId', ''),
                'title': related.get('title', ''),
                'description': related.get('description', ''),
                'comment': related_comment_text
            }
            related_processed.append(
                self.preprocessor.preprocess_video_data(related_data)
            )

        logger.debug(f"전처리 완료: 관련 영상 {len(related_processed)}개")

        # 4. 벡터화 및 모델 입력 준비
        input_data = self._prepare_model_input(original_processed, related_processed)

        # 5. CNN 예측
        prediction_proba = self.cnn_model.predict(input_data, verbose=0)[0][0]
        prediction_proba = float(prediction_proba)

        # 6. 판정
        if prediction_proba > 0.5:
            prediction = "Fake"
            confidence = prediction_proba
        else:
            prediction = "Real"
            confidence = 1.0 - prediction_proba

        # 7. 결과 포맷팅
        result = {
            'prediction': prediction,
            'fakeProbability': prediction_proba,
            'confidence': confidence,
            'details': {
                'fake_probability': prediction_proba,
                'real_probability': 1.0 - prediction_proba,
                'model_type': Config.MODEL_TYPE,
                'text_combination': Config.CURRENT_TEXT_COMBINATION
            }
        }

        logger.info(
            f"분석 완료: {prediction} (신뢰도: {confidence*100:.2f}%)"
        )

        return result


# 전역 인스턴스 (서버 시작 시 생성)
_engine: Optional[InferenceEngine] = None


def get_inference_engine() -> InferenceEngine:
    """
    추론 엔진 인스턴스 반환 (싱글톤)
    FastAPI dependency injection에서 사용
    """
    global _engine
    if _engine is None:
        _engine = InferenceEngine()
    return _engine
