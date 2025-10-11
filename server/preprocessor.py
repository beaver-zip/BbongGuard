"""
데이터 전처리 모듈
Chrome Extension에서 받은 데이터를 모델 입력 형식으로 변환
"""

import nltk
from nltk.tokenize import word_tokenize
from typing import List, Dict

# NLTK 데이터 확인 및 다운로드
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt_tab', quiet=True)


class DataPreprocessor:
    """텍스트 데이터 전처리"""

    def tokenize(self, text: str) -> List[str]:
        """
        텍스트를 토큰으로 분리

        Args:
            text: 입력 텍스트

        Returns:
            토큰 리스트
        """
        if not text or not isinstance(text, str):
            return []

        # 소문자 변환
        text = text.lower()

        # 토큰화
        tokens = word_tokenize(text)

        return tokens

    def preprocess_video_data(self, video_data: Dict) -> Dict:
        """
        단일 비디오 데이터 전처리

        Args:
            video_data: {
                'title': str,
                'description': str,
                'comment': str (또는 comments: List[str])
            }

        Returns:
            전처리된 데이터 (원본 + 토큰)
        """
        # 댓글 처리: 리스트면 공백으로 합치기
        comment_text = video_data.get('comment', '')
        if isinstance(comment_text, list):
            comment_text = ' '.join(comment_text)

        title = video_data.get('title', '')
        description = video_data.get('description', '')

        return {
            'video_id': video_data.get('videoId', ''),
            'title': title,
            'description': description,
            'comment': comment_text,
            'title_tokens': self.tokenize(title),
            'description_tokens': self.tokenize(description),
            'comment_tokens': self.tokenize(comment_text)
        }

    def combine_texts(self, processed_data: Dict, text_types: List[str]) -> List[str]:
        """
        여러 텍스트 필드를 결합

        Args:
            processed_data: preprocess_video_data()의 결과
            text_types: 결합할 필드 이름 리스트 (예: ['title', 'description', 'comment'])

        Returns:
            결합된 토큰 리스트
        """
        combined_tokens = []

        for text_type in text_types:
            field_name = f'{text_type}_tokens'
            if field_name in processed_data:
                combined_tokens.extend(processed_data[field_name])

        return combined_tokens
