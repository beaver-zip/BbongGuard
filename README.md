# 🛡️ BbongGuard - 멀티모달 가짜뉴스 탐지 플랫폼

BbongGuard는 YouTube 영상의 **텍스트(자막/댓글), 이미지(프레임), 오디오(음성)**를 종합적으로 분석하여 가짜뉴스, 낚시성 콘텐츠, 선동적인 영상을 탐지하는 AI 기반 확장프로그램입니다.

## 🔄 분석 파이프라인 (Analysis Pipeline)

BbongGuard의 분석은 다음 5단계의 논리적 흐름으로 진행됩니다.

### 1. 텍스트 분석 (Text Analysis) - 기반 구축
가장 먼저 실행되며, 이후 멀티모달 분석의 기초가 됩니다.
- **자막 생성**: 영상의 자막(Transcript)을 추출하거나, 없을 경우 STT(Speech-to-Text)를 수행합니다.
- **주장 추출**: LLM이 자막, 제목, 설명을 분석하여 팩트체크가 필요한 핵심 주장을 추출합니다.
- **팩트체크**: Tavily API로 웹 검색을 수행하여 각 주장에 대한 증거를 수집하고 진위를 판정합니다.

### 2. 멀티모달 병렬 분석 (Parallel Multimodal Analysis)
텍스트 분석이 완료되면, 이미지와 오디오 분석이 동시에 실행됩니다.
- **이미지 분석**:
    - **OCR 및 필터링**: 썸네일의 텍스트를 추출하고 낚시성 키워드를 검사합니다.
    - **심층 분석**: 1차 필터링 결과가 의심스러울 경우, Vision LLM이 텍스트 밀도, 디자인 스타일, 인물 표정 등을 분석하여 위험도를 평가합니다.
- **오디오 분석**:
    - **자막 재사용**: 텍스트 모듈에서 생성된 자막을 공유받아 중복 연산을 방지합니다.
    - **선동 탐지**: LLM이 오디오 전체 맥락을 분석하여 보이스피싱 패턴이나 과도한 공포 조장 등 선동적 요소를 탐지합니다.

### 3. 결과 집계 및 부분 성공 처리
- `asyncio`를 활용하여 각 모듈의 결과를 비동기적으로 수집합니다.
- 특정 모듈(예: 이미지 분석)이 실패하더라도 전체 프로세스를 중단하지 않고, 성공한 모듈의 결과만으로 분석을 지속하는 **부분 성공(Partial Success)** 로직이 적용됩니다.

### 4. 최종 종합 판정 (Final Verdict)
- **Verdict Agent**: 텍스트, 이미지, 오디오 모듈의 개별 분석 결과를 종합합니다.
- **최종 판단**: 각 모듈의 발견 사항과 신뢰도를 고려하여 최종적인 가짜뉴스 여부, 신뢰도 등급, 그리고 판단 근거를 생성합니다.

---

## 🏗️ 프로젝트 구조

```
BbongGuard/
├── server/                    # FastAPI 백엔드 서버
│   ├── main.py               # API 엔트리포인트
│   ├── config.py             # 서버 설정
│   ├── text_module/          # 텍스트 분석 (RAG, 팩트체크)
│   ├── image_module/         # 이미지 분석 (자극성 탐지)
│   ├── audio_module/         # 오디오 분석 (선동성 탐지)
│   └── shared/               # 공통 모듈 (스키마, 로거, 유틸리티)
│
├── extension/                 # Chrome 확장프로그램 (클라이언트)
├── logs/                      # 분석 로그 (Git 제외)
├── .env                       # 환경 변수 설정
└── requirements.txt           # Python 의존성
```

---

## 🚀 설치 및 실행 방법

### 1. 필수 요구사항
- Python 3.10 이상
- FFmpeg (오디오/비디오 처리에 필요)
- OpenAI API Key (GPT-4o 사용)
- Tavily API Key (웹 검색용)

### 2. 설치

```bash
# 저장소 클론
git clone https://github.com/beaver-zip/BbongGuard.git
cd BbongGuard

# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate  # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 3. 환경 변수 설정

`.env_example` 파일을 복사하여 `.env` 파일을 생성하고 실제 API 키를 입력하세요:

```bash
cp .env_example .env
```

`.env` 파일 예시:

```ini
# Server Configuration
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# API Keys
OPENAI_API_KEY=sk-your-actual-key-here
TAVILY_API_KEY=tvly-your-actual-key-here
GOOGLE_APPLICATION_CREDENTIALS_PATH=path/to/google-service-account-key.json
NAVER_CLOVA_SPEECH_INVOKE_URL=https://clovaspeech-gw.ncloud.com/...
NAVER_CLOVA_SPEECH_SECRET_KEY=your-naver-key-here

# RAG Configuration
RAG_MAX_CLAIMS=5
RAG_MAX_SEARCH_RESULTS=10
RAG_TOP_EVIDENCE=5

# LLM Configuration
LLM_MODEL=gpt-4o
LLM_TEMPERATURE=0.1
```

### 4. 서버 실행

```bash
# 개발 모드 실행
uvicorn server.main:app --reload

# 또는 Python 모듈로 실행
python -m server.main
```

---

## 📡 API 사용법

### 멀티모달 분석 요청

**POST** `/api/analyze-multimodal`

```json
{
  "video_id": "VIDEO_ID",
  "title": "영상 제목",
  "description": "영상 설명",
  "transcript": "자막 텍스트 (선택 사항)",
  "duration_sec": 300
}
```

**Response Example:**

```json
{
  "video_id": "VIDEO_ID",
  "final_verdict": {
    "is_fake_news": false,
    "confidence_level": "high",
    "overall_reasoning": "텍스트 팩트체크 결과 사실로 확인되었으며...",
    "text_analysis_summary": "텍스트 분석 요약 (Short)",
    "image_analysis_summary": "이미지 분석 요약 (Short)",
    "audio_analysis_summary": "오디오 분석 요약 (Short)",
    "image_analysis_details": "이미지 상세 분석 (Long)",
    "audio_analysis_details": "오디오 상세 분석 (Long)",
    "recommendation": "안심하고 시청하셔도 됩니다."
  },
  "text_result": { ... },
  "image_result": { ... },
  "audio_result": { ... }
}
```

---

## ⚠️ 주의사항

- **비용**: OpenAI GPT-4o 및 Tavily API 사용에 따른 비용이 발생할 수 있습니다.
- **속도**: 멀티모달 분석은 영상 길이에 따라 수 초에서 수 분이 소요될 수 있습니다.
- **정확도**: AI 분석 결과는 보조적인 수단이며, 100% 정확성을 보장하지 않습니다.

## 📄 라이선스

MIT License