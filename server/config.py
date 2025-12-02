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

    # 1. 서버 기본 설정
    HOST = os.getenv("SERVER_HOST", "0.0.0.0")
    PORT = int(os.getenv("SERVER_PORT", "8000"))
    BASE_DIR = Path(__file__).parent

    # 2. CORS 설정
    CORS_ORIGINS = [
        "chrome-extension://*",
        "http://localhost:*",
        "http://127.0.0.1:*"
    ]

    # 3. Text Module (RAG) 설정
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
    
    # RAG 파라미터
    RAG_MAX_CLAIMS = int(os.getenv("RAG_MAX_CLAIMS", "5"))
    RAG_MAX_COMMENTS = int(os.getenv("RAG_MAX_COMMENTS", "10"))
    RAG_MAX_SEARCH_RESULTS = int(os.getenv("RAG_MAX_SEARCH_RESULTS", "10"))
    RAG_TOP_EVIDENCE = int(os.getenv("RAG_TOP_EVIDENCE", "5"))
    
    # 4. Image Module (Google Cloud) 설정
    GOOGLE_APPLICATION_CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_PATH", "")

    # 5. Audio Module (Naver Cloud) 설정
    NAVER_CLOVA_SPEECH_INVOKE_URL = os.getenv("NAVER_CLOVA_SPEECH_INVOKE_URL", "")
    NAVER_CLOVA_SPEECH_SECRET_KEY = os.getenv("NAVER_CLOVA_SPEECH_SECRET_KEY", "")

    # 6. 데이터 및 경로 설정
    CHROMADB_DIR = BASE_DIR / "data" / "chromadb"
    CHROMADB_COLLECTION_NAME = "evidence_store"
    SOURCE_LISTS_DIR = BASE_DIR / "data" / "source_lists"
    WHITELIST_PATH = SOURCE_LISTS_DIR / "whitelist.json"
    BLACKLIST_PATH = SOURCE_LISTS_DIR / "blacklist.json"

    # 7. LLM 설정
    LLM_MODEL = "gpt-4o"
    LLM_TEMPERATURE = 0.1
    LLM_MAX_TOKENS = 2000

    # 8. 유틸리티 설정
    # [수정] 프록시 설정 제거, API Key만 유지
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

    @classmethod
    def validate_config(cls):
        """서버 필수 설정 검증"""
        errors = []
        if not cls.OPENAI_API_KEY: errors.append("OPENAI_API_KEY Missing")
        if not cls.TAVILY_API_KEY: errors.append("TAVILY_API_KEY Missing")
        if not cls.GOOGLE_APPLICATION_CREDENTIALS_PATH: print("Warning: Google Key Missing")
        if not cls.NAVER_CLOVA_SPEECH_INVOKE_URL: print("Warning: Naver Key Missing")
        return errors

    @classmethod
    def print_config(cls):
        print("="*70)
        print("BbongGuard V2 Server Configured")
        print("="*70)