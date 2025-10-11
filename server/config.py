"""
BbongGuard 추론 서버 설정
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Config:
    """서버 설정 관리"""

    # 서버 설정
    HOST = os.getenv("SERVER_HOST", "0.0.0.0")
    PORT = int(os.getenv("SERVER_PORT", "8000"))

    # 경로 설정
    BASE_DIR = Path(__file__).parent
    MODEL_DIR = BASE_DIR / "models"

    # 모델 파일 경로
    DOC2VEC_MODEL_PATH = MODEL_DIR / "doc2vec.model"
    CNN_MODEL_PATH = MODEL_DIR / "OR-TDC.h5"

    # Doc2Vec 설정
    DOC2VEC_VECTOR_SIZE = 100

    # 모델 설정
    MODEL_TYPE = "OR-TDC"  # Original + Related + Title + Description + Comments
    USE_RELATED_VIDEOS = True
    NUM_RELATED_VIDEOS = 9

    # 텍스트 조합 설정
    TEXT_COMBINATIONS = {
        'T': ['title'],
        'D': ['description'],
        'C': ['comment'],
        'TD': ['title', 'description'],
        'TC': ['title', 'comment'],
        'DC': ['description', 'comment'],
        'TDC': ['title', 'description', 'comment']
    }

    # 현재 모델의 텍스트 조합
    CURRENT_TEXT_COMBINATION = 'TDC'

    # CORS 설정 (Chrome Extension 연동을 위해)
    CORS_ORIGINS = [
        "chrome-extension://*",
        "http://localhost:*",
        "http://127.0.0.1:*"
    ]

    # YouTube API 설정 (옵션 - 필요시 서버에서도 데이터 수집 가능)
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

    @classmethod
    def validate(cls):
        """설정 검증"""
        errors = []

        # 모델 디렉토리 확인
        if not cls.MODEL_DIR.exists():
            errors.append(f"모델 디렉토리가 존재하지 않습니다: {cls.MODEL_DIR}")

        # Doc2Vec 모델 파일 확인
        if not cls.DOC2VEC_MODEL_PATH.exists():
            errors.append(f"Doc2Vec 모델 파일이 없습니다: {cls.DOC2VEC_MODEL_PATH}")

        # CNN 모델 파일 확인
        if not cls.CNN_MODEL_PATH.exists():
            errors.append(f"CNN 모델 파일이 없습니다: {cls.CNN_MODEL_PATH}")

        return errors

    @classmethod
    def print_config(cls):
        """설정 출력"""
        print("="*70)
        print("BbongGuard 추론 서버 설정")
        print("="*70)
        print(f"서버 주소: {cls.HOST}:{cls.PORT}")
        print(f"모델 디렉토리: {cls.MODEL_DIR}")
        print(f"Doc2Vec 모델: {cls.DOC2VEC_MODEL_PATH}")
        print(f"CNN 모델: {cls.CNN_MODEL_PATH}")
        print(f"모델 타입: {cls.MODEL_TYPE}")
        print(f"텍스트 조합: {cls.CURRENT_TEXT_COMBINATION}")
        print(f"관련 영상 사용: {cls.USE_RELATED_VIDEOS} (최대 {cls.NUM_RELATED_VIDEOS}개)")
        print("="*70)
