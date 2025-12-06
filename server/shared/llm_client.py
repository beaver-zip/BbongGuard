"""
OpenAI LLM 클라이언트.
GPT-4o를 사용한 비동기 호출을 담당합니다.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from openai import AsyncOpenAI

from ..config import Config

logger = logging.getLogger(__name__)


class LLMClient:
    """OpenAI GPT-4o 비동기 클라이언트."""

    def __init__(self, model: Optional[str] = None):
        """
        OpenAI 클라이언트를 초기화합니다.

        Args:
            model (Optional[str]): 사용할 모델명 (기본값: Config 설정).

        Raises:
            ValueError: API Key가 설정되지 않은 경우.
        """
        if not Config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다")

        self.client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = model if model else Config.LLM_MODEL
        self.temperature = Config.LLM_TEMPERATURE
        self.max_tokens = Config.LLM_MAX_TOKENS

        logger.info(f"LLMClient 초기화 완료 - 모델: {self.model}")

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        채팅 완성 API를 호출합니다.

        Args:
            messages (List[Dict[str, str]]): 대화 메시지 목록 (예: [{"role": "user", "content": "..."}]).
            temperature (Optional[float]): 샘플링 온도 (기본값: Config 설정).
            max_tokens (Optional[int]): 최대 생성 토큰 수 (기본값: Config 설정).
            response_format (Optional[Dict]): 응답 형식 지정 (예: {"type": "json_object"}).

        Returns:
            str: LLM이 생성한 응답 텍스트.

        Raises:
            Exception: API 호출 실패 시 예외 발생.
        """
        try:
            params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature if temperature is not None else self.temperature,
                "max_tokens": max_tokens if max_tokens is not None else self.max_tokens
            }

            if response_format:
                params["response_format"] = response_format

            response = await self.client.chat.completions.create(**params)

            content = response.choices[0].message.content
            logger.debug(f"LLM 응답: {content[:100]}...")

            return content

        except Exception as e:
            logger.error(f"LLM API 호출 실패: {e}")
            raise

    async def chat_completion_json(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        JSON 형식의 응답을 요청하고 파싱합니다.

        Args:
            messages (List[Dict[str, str]]): 대화 메시지 목록.
            temperature (Optional[float]): 샘플링 온도.
            max_tokens (Optional[int]): 최대 생성 토큰 수.

        Returns:
            Dict[str, Any]: 파싱된 JSON 객체.

        Raises:
            ValueError: JSON 파싱 실패 시 발생.
        """
        response_text = await self.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )

        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"LLM JSON 응답 파싱 실패: {e}\n응답: {response_text}")
            raise ValueError(f"JSON 파싱 실패: {e}")

    async def chat_completion_image(
        self,
        messages: List[Dict[str, Any]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        이미지가 포함된 멀티모달 채팅 완성 API를 호출합니다 (GPT-4o Vision).

        Args:
            messages (List[Dict[str, Any]]): 이미지 URL이 포함된 메시지 목록.
            temperature (Optional[float]): 샘플링 온도.
            max_tokens (Optional[int]): 최대 생성 토큰 수.
            response_format (Optional[Dict]): 응답 형식.

        Returns:
            str: LLM이 생성한 응답 텍스트.

        Raises:
            Exception: API 호출 실패 시 예외 발생.
        """
        try:
            params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature if temperature is not None else self.temperature,
                "max_tokens": max_tokens if max_tokens is not None else self.max_tokens
            }

            if response_format:
                params["response_format"] = response_format

            response = await self.client.chat.completions.create(**params)
            content = response.choices[0].message.content
            logger.debug(f"LLM(Vision) 응답: {content[:100]}...")
            return content

        except Exception as e:
            logger.error(f"LLM(Vision) API 호출 실패: {e}")
            raise


# 싱글톤 인스턴스
_llm_client_instance: Optional[LLMClient] = None


async def get_llm_client() -> LLMClient:
    """
    LLMClient의 싱글톤 인스턴스를 반환합니다.

    Returns:
        LLMClient: 초기화된 LLMClient 인스턴스.
    """
    global _llm_client_instance

    if _llm_client_instance is None:
        _llm_client_instance = LLMClient()

    return _llm_client_instance
