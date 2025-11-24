"""YouTube Data API v3 클라이언트"""

import logging
import tempfile
import os
from typing import Dict, List, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api.proxies import WebshareProxyConfig
import re
import time
import random
import yt_dlp

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
        비디오 정보 가져오기

        Args:
            video_id: YouTube 비디오 ID

        Returns:
            비디오 정보 딕셔너리 (title, description, channel_title 등)
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

        Args:
            video_id: YouTube 비디오 ID
            max_results: 최대 댓글 수

        Returns:
            댓글 텍스트 리스트
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

            if len(comments) == 0:
                logger.warning(f"댓글이 0개입니다 (video_id: {video_id}) - 댓글 비활성화 또는 댓글 없음")
            else:
                logger.info(f"댓글 {len(comments)}개 가져오기 완료")
            return comments

        except HttpError as e:
            error_reason = e.error_details[0].get('reason', 'unknown') if e.error_details else 'unknown'
            error_message = e.error_details[0].get('message', str(e)) if e.error_details else str(e)

            if error_reason == 'commentsDisabled':
                logger.warning(f"댓글 비활성화됨 (video_id: {video_id})")
            elif error_reason == 'quotaExceeded':
                logger.error(f"YouTube API 할당량 초과 (video_id: {video_id})")
            elif error_reason == 'videoNotFound':
                logger.error(f"영상을 찾을 수 없음 (video_id: {video_id})")
            else:
                logger.error(f"댓글 가져오기 실패 (video_id: {video_id}): {error_reason} - {error_message}")

            return []

        except Exception as e:
            logger.error(f"댓글 가져오기 중 예기치 않은 오류 (video_id: {video_id}): {type(e).__name__}: {e}")
            return []

    def get_transcript(self, video_id: str, languages: List[str] = None) -> str:
        """
        비디오 자막(스크립트) 가져오기

        Args:
            video_id: YouTube 비디오 ID
            languages: 선호 언어 리스트 (기본: ['ko', 'en'])

        Returns:
            자막 텍스트 (전체 스크립트)
        """
        if languages is None:
            languages = ['ko', 'en']

        try:
            # WebShare 프록시 설정 (IP 차단 우회)
            proxy_config = None
            if Config.WEBSHARE_PROXY_USERNAME and Config.WEBSHARE_PROXY_PASSWORD:
                proxy_config = WebshareProxyConfig(
                    proxy_username=Config.WEBSHARE_PROXY_USERNAME,
                    proxy_password=Config.WEBSHARE_PROXY_PASSWORD
                )
                logger.info("WebShare 프록시 사용")

            # 재시도 로직 (Exponential Backoff)
            max_retries = 5
            base_delay = 4

            for attempt in range(max_retries):
                try:
                    # 자막 가져오기 (언어 우선순위: 한국어 → 영어)
                    # 매 시도마다 새로운 API 인스턴스 생성 (프록시 로테이션 효과 기대)
                    api = YouTubeTranscriptApi(proxy_config=proxy_config)
                    
                    # get_transcript가 아니라 fetch를 사용해야 함 (이전 코드 복원)
                    fetched_transcript = api.fetch(video_id, languages=languages)

                    # 텍스트만 추출하여 결합
                    script = ' '.join([entry['text'] for entry in fetched_transcript])

                    logger.info(f"자막 가져오기 완료: {len(script)}자")
                    return script

                except (TranscriptsDisabled, NoTranscriptFound):
                    # 이건 재시도해도 소용없음
                    logger.warning(f"자막을 찾을 수 없음 (재시도 안함): {video_id}")
                    return ""

                except Exception as e:
                    error_msg = str(e)
                    is_proxy_error = "Tunnel connection failed" in error_msg or "500" in error_msg
                    is_rate_limit = "429" in error_msg or "Too Many Requests" in error_msg
                    
                    if is_proxy_error or is_rate_limit:
                        if attempt < max_retries - 1:
                            # 프록시 에러인 경우, 다음 시도부터는 프록시 해제 (Direct 연결 시도)
                            if is_proxy_error and proxy_config is not None:
                                logger.warning(f"프록시 오류 감지 ({error_msg}). 다음 시도는 프록시 없이 진행합니다.")
                                proxy_config = None
                            
                            # 지수 백오프 + Jitter
                            delay = base_delay * (2 ** attempt) + (random.random() * 2)
                            logger.warning(f"자막 가져오기 에러 (시도 {attempt+1}/{max_retries}): {error_msg[:100]}... {delay:.1f}초 후 재시도...")
                            time.sleep(delay)
                            continue
                    
                    # 재시도 대상이 아니거나 마지막 시도면 에러 로그 남기고 종료
                    logger.error(f"자막 가져오기 실패 (시도 {attempt+1}/{max_retries}): {e}")
                    if attempt == max_retries - 1:
                        return ""
                    
                    # 그 외 에러는 즉시 종료
                    return ""

            # youtube_transcript_api 실패 시 yt-dlp로 fallback
            logger.info("youtube_transcript_api 실패, yt-dlp로 자막 추출 시도...")
            return self._get_transcript_via_ytdlp(video_id, languages)

        except Exception as e:
            logger.error(f"자막 가져오기 최종 실패: {e}")
            # yt-dlp fallback 시도
            return self._get_transcript_via_ytdlp(video_id, languages)

    def _get_transcript_via_ytdlp(self, video_id: str, languages: List[str] = None) -> str:
        """
        yt-dlp를 사용하여 자막 추출 (fallback)

        Args:
            video_id: YouTube 비디오 ID
            languages: 선호 언어 리스트

        Returns:
            자막 텍스트
        """
        if languages is None:
            languages = ['ko', 'en']

        video_url = f"https://www.youtube.com/watch?v={video_id}"

        # 임시 디렉토리에 자막 파일 저장
        with tempfile.TemporaryDirectory() as tmp_dir:
            ydl_opts = {
                'skip_download': True,  # 영상은 다운로드하지 않음
                'writesubtitles': True,  # 수동 자막
                'writeautomaticsub': True,  # 자동 생성 자막
                'subtitleslangs': languages,
                'subtitlesformat': 'vtt',  # WebVTT 형식
                'outtmpl': os.path.join(tmp_dir, '%(id)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                # SABR 스트리밍 우회
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web'],
                    }
                },
            }

            try:
                logger.info(f"yt-dlp로 자막 추출 시도: {video_id}")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(video_url, download=True)

                # 자막 파일 찾기
                for lang in languages:
                    # 수동 자막 먼저 시도
                    subtitle_file = os.path.join(tmp_dir, f"{video_id}.{lang}.vtt")
                    if os.path.exists(subtitle_file):
                        transcript = self._parse_vtt_file(subtitle_file)
                        if transcript:
                            logger.info(f"yt-dlp 자막 추출 성공 (수동, {lang}): {len(transcript)}자")
                            return transcript

                    # 자동 생성 자막 시도
                    auto_subtitle_file = os.path.join(tmp_dir, f"{video_id}.{lang}.vtt")
                    if os.path.exists(auto_subtitle_file):
                        transcript = self._parse_vtt_file(auto_subtitle_file)
                        if transcript:
                            logger.info(f"yt-dlp 자막 추출 성공 (자동, {lang}): {len(transcript)}자")
                            return transcript

                # 임시 디렉토리의 모든 vtt 파일 확인
                for filename in os.listdir(tmp_dir):
                    if filename.endswith('.vtt'):
                        filepath = os.path.join(tmp_dir, filename)
                        transcript = self._parse_vtt_file(filepath)
                        if transcript:
                            logger.info(f"yt-dlp 자막 추출 성공 ({filename}): {len(transcript)}자")
                            return transcript

                logger.warning(f"yt-dlp로도 자막을 찾을 수 없음: {video_id}, Whisper로 음성 인식 시도...")
                return self._get_transcript_via_whisper(video_id)

            except Exception as e:
                logger.error(f"yt-dlp 자막 추출 실패: {type(e).__name__}: {e}")
                # Whisper fallback
                return self._get_transcript_via_whisper(video_id)

    def _parse_vtt_file(self, filepath: str) -> str:
        """
        VTT 자막 파일을 파싱하여 텍스트만 추출

        Args:
            filepath: VTT 파일 경로

        Returns:
            자막 텍스트
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            lines = content.split('\n')
            text_lines = []

            for line in lines:
                line = line.strip()
                # WEBVTT 헤더, 타임스탬프, 빈 줄 스킵
                if not line:
                    continue
                if line.startswith('WEBVTT'):
                    continue
                if line.startswith('NOTE'):
                    continue
                if '-->' in line:  # 타임스탬프 라인
                    continue
                if re.match(r'^\d+$', line):  # 숫자만 있는 라인 (인덱스)
                    continue
                # HTML 태그 제거
                line = re.sub(r'<[^>]+>', '', line)
                if line:
                    text_lines.append(line)

            # 중복 제거 (연속된 동일 라인)
            unique_lines = []
            prev_line = None
            for line in text_lines:
                if line != prev_line:
                    unique_lines.append(line)
                    prev_line = line

            return ' '.join(unique_lines)

        except Exception as e:
            logger.error(f"VTT 파일 파싱 실패: {e}")
            return ""

    def _get_transcript_via_whisper(self, video_id: str) -> str:
        """
        Whisper를 사용하여 오디오에서 자막 추출 (최종 fallback)

        Args:
            video_id: YouTube 비디오 ID

        Returns:
            자막 텍스트
        """
        try:
            import whisper
        except ImportError:
            logger.error("Whisper가 설치되지 않았습니다. pip install openai-whisper 실행 필요")
            return ""

        video_url = f"https://www.youtube.com/watch?v={video_id}"

        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = os.path.join(tmp_dir, f"{video_id}.mp3")

            # 1. 오디오만 다운로드
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': audio_path.replace('.mp3', '.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
                'no_warnings': True,
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web'],
                    }
                },
            }

            try:
                logger.info(f"Whisper용 오디오 다운로드 시작: {video_id}")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([video_url])

                # 다운로드된 오디오 파일 찾기
                audio_file = None
                for filename in os.listdir(tmp_dir):
                    if filename.endswith(('.mp3', '.m4a', '.wav', '.webm')):
                        audio_file = os.path.join(tmp_dir, filename)
                        break

                if not audio_file or not os.path.exists(audio_file):
                    logger.error("오디오 파일 다운로드 실패")
                    return ""

                file_size = os.path.getsize(audio_file)
                logger.info(f"오디오 다운로드 완료: {file_size / 1024 / 1024:.2f}MB")

                # 2. Whisper로 음성 인식
                logger.info("Whisper 모델 로드 중... (처음 실행 시 다운로드됨)")
                # 'base' 모델 사용 (속도와 정확도 밸런스)
                # 'tiny': 가장 빠름, 'small': 더 정확, 'medium': 더욱 정확
                model = whisper.load_model("base")

                logger.info("Whisper 음성 인식 시작...")
                result = model.transcribe(
                    audio_file,
                    language="ko",  # 한국어
                    fp16=False,  # CPU에서 실행 시 False
                )

                transcript = result.get("text", "")
                if transcript:
                    logger.info(f"Whisper 자막 추출 성공: {len(transcript)}자")
                    return transcript.strip()
                else:
                    logger.warning("Whisper가 텍스트를 추출하지 못함")
                    return ""

            except Exception as e:
                logger.error(f"Whisper 자막 추출 실패: {type(e).__name__}: {e}")
                return ""


# 싱글톤 인스턴스
_youtube_client_instance: Optional[YouTubeClient] = None


def get_youtube_client() -> YouTubeClient:
    """YouTubeClient 싱글톤 인스턴스 반환"""
    global _youtube_client_instance

    if _youtube_client_instance is None:
        _youtube_client_instance = YouTubeClient()

    return _youtube_client_instance
