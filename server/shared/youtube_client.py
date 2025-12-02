"""YouTube Data API v3 클라이언트"""

import logging
import re
from typing import Dict, List, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..config import Config

logger = logging.getLogger(__name__)


class YouTubeClient:
    """YouTube Data API v3 클라이언트"""

    def __init__(self):
        """YouTube API 클라이언트 초기화"""
        if not Config.YOUTUBE_API_KEY:
            raise ValueError("YOUTUBE_API_KEY가 설정되지 않았습니다")

        self.youtube = build('youtube', 'v3', developerKey=Config.YOUTUBE_API_KEY)
        logger.info("YouTubeClient 초기화 완료")

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """YouTube URL에서 video ID 추출"""
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
            r'(?:embed\/)([0-9A-Za-z_-]{11})',
            r'^([0-9A-Za-z_-]{11})$'
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def get_video_info(self, video_id: str) -> Dict[str, any]:
        """
        비디오 정보 가져오기 (제목, 설명, 채널명 등)
        """
        try:
            request = self.youtube.videos().list(
                part='snippet',
                id=video_id
            )
            response = request.execute()

            if not response.get('items'):
                logger.error(f"비디오를 찾을 수 없습니다: {video_id}")
                return {}

            snippet = response['items'][0]['snippet']

            info = {
                'video_id': video_id,
                'title': snippet.get('title', ''),
                'description': snippet.get('description', ''),
                'channel_title': snippet.get('channelTitle', ''),
                'published_at': snippet.get('publishedAt', '')
            }

            logger.info(f"비디오 정보 가져오기 완료: {info['title']}")
            return info

        except HttpError as e:
            logger.error(f"YouTube API 에러: {e}")
            return {}

    def get_comments(self, video_id: str, max_results: int = None) -> List[str]:
        """
        비디오 댓글 가져오기
        """
        try:
            if max_results is None:
                max_results = Config.RAG_MAX_COMMENTS

            comments = []
            request = self.youtube.commentThreads().list(
                part='snippet',
                videoId=video_id,
                maxResults=min(max_results, 100),
                order='relevance',
                textFormat='plainText'
            )

            response = request.execute()

            for item in response.get('items', []):
                comment = item['snippet']['topLevelComment']['snippet']
                text = comment.get('textDisplay', '')
                if text:
                    comments.append(text)

            logger.info(f"댓글 {len(comments)}개 가져오기 완료")
            return comments

        except Exception as e:
            # 댓글이 비활성화된 경우 등은 에러가 아닌 경고로 처리하고 빈 리스트 반환
            logger.warning(f"댓글 가져오기 실패 (비활성화 또는 오류): {e}")
            return []

    def get_transcript(self, video_id: str, languages: List[str] = None) -> str:
        """
        [삭제됨] 자막 추출 기능 제거
        항상 빈 문자열을 반환하여 텍스트 모듈이 즉시 다음 단계로 넘어가게 함.
        """
        logger.debug("자막 추출 기능이 비활성화되어 건너뜁니다.")
        return ""


# 싱글톤 인스턴스
_youtube_client_instance: Optional[YouTubeClient] = None


def get_youtube_client() -> YouTubeClient:
    """YouTubeClient 싱글톤 인스턴스 반환"""
    global _youtube_client_instance

    if _youtube_client_instance is None:
        _youtube_client_instance = YouTubeClient()

    return _youtube_client_instance