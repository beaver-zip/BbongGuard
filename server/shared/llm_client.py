"""
OpenAI LLM 클라이언트
GPT-4o를 사용한 비동기 호출
"""

import logging
import json
from typing import Dict, Any, Optional, List
from openai import AsyncOpenAI
import asyncio

from ..config import Config

logger = logging.getLogger(__name__)


class LLMClient:
    """OpenAI GPT-4o 비동기 클라이언트"""

    def __init__(self):
        """OpenAI 클라이언트 초기화"""
        if not Config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다")

        self.client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.LLM_MODEL
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
        채팅 완성 API 호출

        Args:
            messages: 메시지 목록 [{"role": "user", "content": "..."}]
            temperature: 샘플링 온도 (기본값: Config.LLM_TEMPERATURE)
            max_tokens: 최대 토큰 수 (기본값: Config.LLM_MAX_TOKENS)
            response_format: 응답 형식 (예: {"type": "json_object"})

        Returns:
            LLM 응답 텍스트
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
        JSON 형식 응답을 요청하는 채팅 완성

        Args:
            messages: 메시지 목록
            temperature: 샘플링 온도
            max_tokens: 최대 토큰 수

        Returns:
            파싱된 JSON 객체
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

    async def extract_claims(
        self,
        title: str,
        description: str,
        comments: List[str],
        transcript: str = None,
        max_claims: int = 5
    ) -> List[Dict[str, Any]]:
        """
        텍스트에서 팩트체킹이 필요한 주장 추출

        Args:
            title: 영상 제목
            description: 영상 설명
            comments: 댓글 목록
            transcript: 영상 스크립트 (자막)
            max_claims: 최대 추출할 주장 수

        Returns:
            주장 목록 [{"claim": "...", "category": "...", "importance": "...", "keywords": [...]}]
        """
        # 모든 댓글 사용 (이미 Config.RAG_MAX_COMMENTS 개수만큼만 수집됨)
        top_comments = '\n'.join(comments) if comments else "댓글 없음"

        # 스크립트가 너무 길면 앞부분만 사용 (토큰 제한)
        script_text = ""
        if transcript:
            max_script_length = 50000  # 약 12.5k 토큰 (GPT-4o는 충분히 처리 가능)
            if len(transcript) > max_script_length:
                script_text = transcript[:max_script_length] + "...(중략)"
            else:
                script_text = transcript
        else:
            script_text = "자막 없음"

        prompt = f"""다음 YouTube 영상의 텍스트에서 팩트체킹이 필요한 구체적인 주장들을 추출하세요.

영상 제목: {title}

영상 설명:
{description}

영상 스크립트 (자막):
{script_text}

주요 댓글:
{top_comments}

추출 조건:
1. **검증 가치**: 단순한 사실 나열보다는, 논란의 여지가 있거나 대중에게 잘못된 정보를 줄 수 있는 주장을 우선하세요.
2. **구체성**: "경제가 나쁘다" 같은 모호한 주장보다는 "2023년 경제성장률이 -1%다" 같은 구체적인 수치/사건이 포함된 주장을 추출하세요.
3. **핵심 내용**: 영상의 핵심 주제와 관련된 주장을 우선하세요.
4. 중요도 높은 순서로 최대 {max_claims}개

출력 형식 (JSON):
{{
  "claims": [
    {{
      "claim": "구체적인 주장 내용 (주어와 술어가 명확한 완결된 문장)",
      "category": "정치|경제|사회|과학|건강|IT|국제|문화|역사|기타",
      "importance": "high|medium|low"
    }}
  ]
}}

주의: 반드시 JSON 형식으로만 응답하세요."""



        messages = [{"role": "user", "content": prompt}]

        try:
            result = await self.chat_completion_json(messages)
            claims = result.get('claims', [])
            logger.info(f"주장 추출 완료: {len(claims)}개")
            return claims
        except Exception as e:
            logger.error(f"주장 추출 실패: {e}")
            return []

    async def judge_claim(
        self,
        claim: str,
        evidence_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        주장을 증거 기반으로 판정 (3가지 상태)

        Args:
            claim: 판정할 주장
            evidence_list: 증거 목록 [{"source_title": "...", "snippet": "...", ...}]

        Returns:
            판정 결과 {"verdict_status": str, "reason": "..."}
        """
        # 증거가 없으면 바로 insufficient_evidence 반환
        if not evidence_list:
            return {
                "verdict_status": "insufficient_evidence",
                "reason": "관련 증거를 찾지 못했습니다."
            }

        # Evidence 포맷팅 (출처 강조)
        evidence_text = ""
        for i, ev in enumerate(evidence_list, 1):
            domain = ev.get('domain', 'Unknown')
            source_title = ev.get('source_title', 'Unknown')
            snippet = ev.get('snippet', 'N/A')

            evidence_text += f"\n{i}. [{domain}] {source_title}\n"
            evidence_text += f"   내용: {snippet}\n"

        prompt = f"""당신은 팩트체커입니다. 주장과 증거들을 보고 진위를 판단하세요.

주장: "{claim}"

수집된 증거:
{evidence_text}

판단 기준:
1. 증거가 주장을 뒷받침하면 → verdict_status: "verified_true"
2. 증거가 주장을 반박하면 → verdict_status: "verified_false"  
3. 증거로 판단하기 어려우면 → verdict_status: "insufficient_evidence"

출력 형식 (JSON):
{{
  "verdict_status": "verified_true|verified_false|insufficient_evidence",
  "reason": "판정 이유를 한 문장으로 요약"
}}"""

        messages = [{"role": "user", "content": prompt}]

        try:
            result = await self.chat_completion_json(messages)
            verdict_status = result.get('verdict_status', 'insufficient_evidence')
            
            # 유효성 검사
            if verdict_status not in ["verified_true", "verified_false", "insufficient_evidence"]:
                verdict_status = "insufficient_evidence"
            
            reason = result.get('reason', '판정 이유 없음')

            logger.info(f"주장 판정 완료: {claim[:50]}... -> {verdict_status}")
            return {
                "verdict_status": verdict_status,
                "reason": reason
            }
        except Exception as e:
            logger.error(f"주장 판정 실패: {e}")
            # 실패 시 기본값
            return {
                "verdict_status": "insufficient_evidence",
                "reason": f"판정 중 오류: {str(e)}"
            }

    async def chat_completion_image(
        self,
        messages: List[Dict[str, Any]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        이미지가 포함된 채팅 완성 API 호출 (GPT-4o Vision)

        Args:
            messages: 메시지 목록 (이미지 포함)
            temperature: 샘플링 온도
            max_tokens: 최대 토큰 수
            response_format: 응답 형식

        Returns:
            LLM 응답 텍스트
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

    async def analyze_visual_provocation(
        self,
        base64_images: List[str],
        claims: List[str]
    ) -> Dict[str, Any]:
        """
        이미지만으로 시각적 자극성을 분석합니다. (텍스트가 없는 경우)

        Args:
            base64_images: Base64 인코딩된 이미지 리스트
            claims: 핵심 주장 리스트

        Returns:
            분석 결과 JSON
        """
        claim_texts = "\n".join([f"- {c}" for c in claims])
        
        # 이미지 메시지 구성 (최대 3장만 사용)
        content = [
            {"type": "text", "text": f"""
            다음은 유튜브 영상의 주요 프레임입니다. 화면 내에 텍스트는 감지되지 않았습니다.
            이 이미지들이 시청자를 자극하거나 선동하기 위해 과장된 시각적 연출(섬네일 낚시, 충격적인 합성 등)을 사용하고 있는지 분석해주세요.

            [핵심 주장]
            {claim_texts}

            분석 기준:
            1. 시각적 자극성 (Visual Provocation): 0~10점. (10: 혐오스럽거나 충격적인 이미지, 과도한 합성)
            2. 관련성 (Relevance): 0~10점. (10: 주장과 밀접하게 관련된 이미지)

            결과를 JSON 형식으로 반환해주세요:
            {{
                "provocation_score": int,
                "relevance_score": int,
                "summary": "한 줄 요약 (예: 자극적인 합성은 없으나 주장과 무관한 이미지를 사용함)"
            }}
            """}
        ]
        
        # 이미지 추가 (최대 3장)
        for img_b64 in base64_images[:3]:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{img_b64}"
                }
            })

        messages = [{"role": "user", "content": content}]

        try:
            response_text = await self.chat_completion_image(
                messages=messages,
                response_format={"type": "json_object"}
            )
            return json.loads(response_text)
        except Exception as e:
            logger.error(f"시각적 자극성 분석 실패: {e}")
            return {"provocation_score": 0, "relevance_score": 0, "summary": "분석 실패"}


# 싱글톤 인스턴스
_llm_client_instance: Optional[LLMClient] = None


async def get_llm_client() -> LLMClient:
    """LLMClient 싱글톤 인스턴스 반환"""
    global _llm_client_instance

    if _llm_client_instance is None:
        _llm_client_instance = LLMClient()

    return _llm_client_instance
