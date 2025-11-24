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

    # CORS 설정 (Chrome Extension 연동을 위해)
    CORS_ORIGINS = [
        "chrome-extension://*",
        "http://localhost:*",
        "http://127.0.0.1:*"
    ]

    # YouTube API 설정 (옵션 - 필요시 서버에서도 데이터 수집 가능)
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

    # WebShare 프록시 설정 (자막 IP 차단 우회용)
    WEBSHARE_PROXY_USERNAME = os.getenv("WEBSHARE_PROXY_USERNAME", "")
    WEBSHARE_PROXY_PASSWORD = os.getenv("WEBSHARE_PROXY_PASSWORD", "")

    # RAG 시스템 설정
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

    # RAG 파라미터
    RAG_MAX_CLAIMS = int(os.getenv("RAG_MAX_CLAIMS", "5"))
    RAG_MAX_COMMENTS = int(os.getenv("RAG_MAX_COMMENTS", "10"))  # 댓글 수집 및 사용 개수
    RAG_MAX_SEARCH_RESULTS = int(os.getenv("RAG_MAX_SEARCH_RESULTS", "10"))
    RAG_TOP_EVIDENCE = int(os.getenv("RAG_TOP_EVIDENCE", "5"))
    RAG_ENABLE_CACHING = os.getenv("RAG_ENABLE_CACHING", "true").lower() == "true"

    # ChromaDB 설정
    CHROMADB_DIR = BASE_DIR / "data" / "chromadb"
    CHROMADB_COLLECTION_NAME = "evidence_store"

    # LLM 설정
    LLM_MODEL = "gpt-4o"
    LLM_TEMPERATURE = 0.1  # 낮을수록 일관성 있는 답변
    LLM_MAX_TOKENS = 2000

    # 출처 리스트 경로
    SOURCE_LISTS_DIR = BASE_DIR / "data" / "source_lists"
    WHITELIST_PATH = SOURCE_LISTS_DIR / "whitelist.json"
    BLACKLIST_PATH = SOURCE_LISTS_DIR / "blacklist.json"

    @classmethod
    def validate_rag(cls):
        """RAG 설정 검증"""
        errors = []

        # API 키 확인
        if not cls.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY가 설정되지 않았습니다")

        if not cls.TAVILY_API_KEY:
            errors.append("TAVILY_API_KEY가 설정되지 않았습니다")

        # 출처 리스트 디렉토리 확인
        if not cls.SOURCE_LISTS_DIR.exists():
            errors.append(f"출처 리스트 디렉토리가 없습니다: {cls.SOURCE_LISTS_DIR}")

        return errors

    @classmethod
    def print_config(cls):
        """설정 출력"""
        print("="*70)
        print("BbongGuard RAG 서버 설정")
        print("="*70)
        print(f"서버 주소: {cls.HOST}:{cls.PORT}")
        print(f"LLM 모델: {cls.LLM_MODEL}")
        print(f"최대 주장 수: {cls.RAG_MAX_CLAIMS}")
        print(f"댓글 수집/사용: {cls.RAG_MAX_COMMENTS}개")
        print(f"검색 결과: {cls.RAG_MAX_SEARCH_RESULTS}개")
        print(f"Evidence: 상위 {cls.RAG_TOP_EVIDENCE}개")
        print("="*70)
