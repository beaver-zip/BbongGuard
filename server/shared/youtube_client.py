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
        """
        YouTube API 클라이언트 초기화.

        Raises:
            ValueError: YOUTUBE_API_KEY가 설정되지 않은 경우.
        """
        if not Config.YOUTUBE_API_KEY:
            raise ValueError("YOUTUBE_API_KEY가 설정되지 않았습니다")

        self.youtube = build('youtube', 'v3', developerKey=Config.YOUTUBE_API_KEY)
        logger.info("YouTubeClient 초기화 완료")

    def get_video_info(self, video_id: str) -> Dict[str, any]:
        """
        YouTube API를 통해 비디오 정보를 가져옵니다.

        Args:
            video_id (str): 유튜브 비디오 ID.

        Returns:
            Dict[str, any]: 비디오 정보 (title, description, channel_title, published_at).
                            실패 시 빈 딕셔너리 반환.
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


# 싱글톤 인스턴스
_youtube_client_instance: Optional[YouTubeClient] = None


def get_youtube_client() -> YouTubeClient:
    """
    YouTubeClient의 싱글톤 인스턴스를 반환합니다.

    Returns:
        YouTubeClient: 초기화된 YouTubeClient 인스턴스.
    """
    global _youtube_client_instance

    if _youtube_client_instance is None:
        _youtube_client_instance = YouTubeClient()

    return _youtube_client_instance