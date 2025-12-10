"""
LLM Prompts for BbongGuard
"""

def get_verdict_agent_prompt(video_meta, claims_summary):
    return f"""당신은 멀티모달 가짜뉴스 판별 전문가입니다. 다음 영상의 분석 결과를 종합하여 최종 판결을 내리세요.

영상 제목: {video_meta.url} (ID: {video_meta.video_id})

각 주장에 대한 모듈별 분석 결과:
{claims_summary}

판단 가이드:
1. **핵심 기준 (Priority)**: '텍스트 팩트체크' 결과가 가장 중요합니다. 단편적인 오류보다는 영상의 전체적인 맥락과 의도를 고려하여 종합적으로 판단하세요. 일부 주장이 거짓이라도 전체적인 메시지가 사실에 기반한다면 등급 조정이 가능합니다.
2. **보조 기준 (Support)**: '이미지'와 '오디오' 분석 결과는 썸네일 낚시(Clickbait)나 감정적 선동 여부를 판단하는 보조 자료로만 활용하세요. 팩트 여부와 관계없이 자극적인 요소가 있다면 '주의'를 요하는 근거로 추가하세요.
3. **종합 판단**: 텍스트 팩트체크 결과를 중심으로 결론을 내리고, 이미지/오디오 분석 결과를 덧붙여 설명하세요.

**최종 판결 작성 시**:
- "이 영상은 [진짜뉴스일 가능성이 높습니다 / 가짜뉴스일 가능성이 높습니다 / 정보성 영상이 아닙니다 ]"와 같이 두괄식으로 명확하게 결론을 내리세요.
- 그 후 "그 이유는..."으로 근거를 설명하세요. 
    - 반드시 다음 형식을 지켜서 작성하세요:
      "[팩트체크] ... (텍스트 모듈 결과 요약)"
      "[자극성/선동성 분석] ... (이미지/오디오 모듈 결과 요약)"

출력 형식 (JSON):
{{
  "is_fake_news": true/false,
  "confidence_level": "high/medium/low",
  "overall_reasoning": "종합적인 판단 이유 (3문장 내외)",
  "text_analysis_summary": "텍스트 모듈 요약 (팩트체크 위주)",
  "image_analysis_summary": "이미지 모듈 요약 (썸네일 자극성 위주)",
  "audio_analysis_summary": "오디오 모듈 요약 (선동성 위주)",
  "image_analysis_details": "이미지 모듈 상세 분석 (구체적인 디자인/표정 묘사 포함, 긴 버전)",
  "audio_analysis_details": "오디오 모듈 상세 분석 (제목과 내용의 불일치 지점 상세 설명, 긴 버전)",
  "key_evidence": ["핵심 근거 1", "핵심 근거 2"],
  "recommendation": "사용자에게 주는 권장 사항"
}}"""

def get_audio_fishing_prompt(title, description, transcript_preview):
    return f"""
            당신은 팩트 체크 전문가입니다.
            다음 유튜브 영상의 '제목' 및 '설명'과 실제 '오디오 내용(스크립트)'을 비교하여, 제목이 내용을 왜곡하거나 과장하는 '가짜 뉴스'인지 판별해주세요.

            [영상 제목]
            {title}

            [영상 설명]
            {description[:500]}... (생략)

            [오디오 내용]
            {transcript_preview}

            분석 가이드:
            1. **사실 일치 여부**: 제목과 설명에서 주장하는 핵심 사건이 실제 내용에 포함되어 있습니까?
            2. **주제 이탈 여부**: 제목은 심각한데 내용은 가벼운 잡담이거나 전혀 다른 주제입니까?
            3. **결론 도출**: 위 분석을 바탕으로 이 영상이 정상적인 정보를 전달하는 '진짜 뉴스'인지, 허위 정보 및 선동을 목표로 하는 '가짜 뉴스'인지, 혹은 다큐멘터리/예능 등 '정보성 영상이 아닌지' 명확히 결론을 내려주세요.

            세 문장으로 요약해서 답변하세요.
            """



def get_query_builder_prompt(claim_text):
    return f"""
    당신은 팩트체크를 위한 검색 쿼리 생성기입니다.
    주어진 주장을 검증하기 위해 구글 검색에 사용할 최적의 검색어(키워드 조합)를 생성하세요.

    주장: "{claim_text}"

    규칙:
    1. 주장의 핵심 키워드 3~5개를 추출하여 조합하세요.
    2. 불필요한 조사나 어미는 제거하세요.
    3. 최신 뉴스나 팩트체크 기사를 찾기 좋은 형태로 만드세요.
    4. 오직 검색어만 출력하세요. (따옴표 없이)
    """

def get_claim_extraction_prompt(title, description, script_text, max_claims):
    return f"""다음 YouTube 영상의 텍스트에서 팩트체킹이 필요한 구체적인 주장들을 추출하세요.

영상 제목: {title}

영상 설명:
{description}

영상 스크립트 (자막):
{script_text}

추출 조건:
1. **검증 가치**: 단순한 사실 나열보다는, 논란의 여지가 있거나 대중에게 잘못된 정보를 줄 수 있는 주장을 우선하세요.
2. **구체성**: "경제가 나쁘다" 같은 모호한 주장보다는 "2023년 경제성장률이 -1%다" 같은 구체적인 수치/사건이 포함된 주장을 추출하세요.
3. **핵심 내용**: 영상의 핵심 주제와 관련된 주장을 우선하세요.
4. **영상 카테고리 분류**: 이 영상이 '뉴스/시사/정보' 카테고리에 속하는지, 아니면 '예능/유머/일상/기타' 카테고리에 속하는지 분류하세요.

출력 형식 (JSON):
{{
  "video_category": "news|info|entertainment|humor|daily|other",
  "claims": [
    {{
      "claim": "구체적인 주장 내용 (주어와 술어가 명확한 완결된 문장)",
      "category": "정치|경제|사회|과학|건강|IT|국제|문화|역사|기타",
      "importance": "high|medium|low"
    }}
  ]
}}

주의: 반드시 JSON 형식으로만 응답하세요."""

def get_claim_judgment_prompt(claim, evidence_text):
    return f"""당신은 팩트체커입니다. 주장과 증거들을 보고 진위를 판단하세요.

주장: "{claim}"

수집된 증거:
{evidence_text}

판단 기준:
1. 증거가 주장을 뒷받침하면 → verdict_status: "verified_true"
2. 증거가 주장을 반박하면 → verdict_status: "verified_false"
3. 증거가 부분적으로 일치하거나, 사소한 차이만 있다면 → verdict_status: "verified_true" (이유에 설명 기재)
4. 증거로 판단하기 정말 어려운 경우에만 → verdict_status: "insufficient_evidence"

주의: "확인되지 않음" 등의 소극적인 판정보다는, 수집된 증거 내에서 가장 합리적인 결론을 도출하세요.

출력 형식 (JSON):
{{
  "verdict_status": "verified_true|verified_false|insufficient_evidence",
  "reason": "판정 이유를 한 문장으로 요약"
}}"""



def get_thumbnail_analysis_prompt(extracted_text, matched_keywords):
    return f"""당신은 유튜브 썸네일 이미지를 정밀 분석하여 '가짜뉴스' 또는 '낚시성 콘텐츠(Clickbait)' 위험도를 판별하는 AI 전문가입니다.

제공된 썸네일 이미지를 보고, 아래의 **5가지 기준**에 따라 분석한 후 JSON 형식으로 출력하세요.

---

## 참고 정보
- **OCR 추출 텍스트**: {extracted_text[:200]}
- **감지된 자극적 키워드**: {', '.join(matched_keywords) if matched_keywords else '없음'}

---

## 분석 기준 (5가지)

### 1. text_density (텍스트 밀도)
이미지에서 텍스트가 차지하는 면적 비율을 판단하세요.
- **"High"**: 텍스트가 화면의 **30% 이상**을 차지함
- **"Medium"**: 텍스트가 화면의 **15~30%**를 차지함
- **"Low"**: 텍스트가 화면의 **15% 미만**을 차지함

---

### 2. design_style (디자인 스타일)
썸네일의 전체적인 디자인 톤과 제작 방식을 판단하세요.
- **"recca"** (렉카/어그로 스타일): 여러 이미지 콜라주, 원색 배경, 과도한 효과, 인물 얼굴 확대/왜곡, 자극적 텍스트 강조
- **"broadcast"** (방송/언론 스타일): 깔끔한 레이아웃, 방송사 로고, 정돈된 텍스트
- **"etc"** (기타): 위 두 가지에 해당하지 않는 경우

---

### 3. emotion (인물 표정/감정 연출)
썸네일 속 인물의 표정이 과장되거나 자극적인지 판단하세요.
- **"Exaggerated"**: 놀람, 충격, 분노 등 극단적인 표정
- **"Natural"** (자연스러움): 일반적인 표정
- **"None"** (인물 없음)

---

### 4. fake_news_rating (가짜뉴스 위험 등급)
위 3가지 분석 결과를 종합하여 **3단계 등급**으로 위험도를 평가하세요.
- **"Danger"** (위험): "recca" 스타일 + "High" 밀도 + "Exaggerated" 표정 등 (명백한 낚시/가짜뉴스)
- **"Warning"** (주의): 위 3가지 중 2개 이상이 의심스러운 경우
- **"Safe"** (안전): "broadcast" 또는 "etc" 스타일, "Low" 밀도, "Natural" 표정 등

---

### 5. reason (판단 근거)
위 분석을 바탕으로 **한 줄 요약** (한국어)을 작성하세요.

---

## 출력 형식
다음 JSON 형식으로만 답변하세요. **다른 설명이나 주석 없이, 반드시 유효한 JSON 객체 하나만 출력해야 합니다.**

{{
  "text_density": "High" | "Medium" | "Low",
  "design_style": "recca" | "broadcast" | "etc",
  "emotion": "Exaggerated" | "Natural" | "None",
  "fake_news_rating": "Danger" | "Warning" | "Safe",
  "reason": "판단 근거 한 줄 요약 (한국어)"
}}
"""
