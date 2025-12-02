# 🛡️ BbongGuard - 멀티모달 가짜뉴스 탐지 플랫폼

BbongGuard는 YouTube 영상의 **텍스트(자막/댓글), 이미지(프레임), 오디오(음성)**를 종합적으로 분석하여 가짜뉴스, 낚시성 콘텐츠, 선동적인 영상을 탐지하는 AI 기반 확장프로그램입니다.

## 🌟 주요 기능

### 1. 텍스트 팩트체크 (Text Module)
- **RAG (Retrieval-Augmented Generation)**: Tavily API를 사용하여 웹에서 신뢰할 수 있는 증거를 수집하고, LLM(GPT-4o)이 주장의 진위를 판별합니다.
- **주장 추출**: 영상의 자막과 설명에서 핵심 주장을 추출합니다.
- **출처 검증**: 화이트리스트/블랙리스트 기반으로 신뢰할 수 있는 출처만 증거로 채택합니다.

### 2. 이미지 분석 (Image Module)
- **스트리밍 샘플링**: 영상을 다운로드하지 않고 스트리밍 URL을 통해 핵심 프레임(5장)을 즉시 추출하여 분석 속도를 극대화했습니다.
- **썸네일 재사용 탐지**: Google Cloud Vision API의 Web Detection으로 썸네일이 다른 곳에서 재사용된 것인지 탐지합니다.
- **프레임 맥락 분석**: Label Detection과 Text Detection으로 영상 내 객체와 텍스트를 추출하여 주장과의 일치 여부를 확인합니다.

### 3. 오디오 분석 (Audio Module)
- **음성 인식(STT)**: Naver Clova Speech API를 사용하여 영상의 오디오를 텍스트로 변환합니다.
- **제목 낚시 탐지**: 변환된 텍스트와 영상 제목을 비교하여, 제목이 실제 내용과 다른 낚시성 콘텐츠인지 LLM으로 판별합니다.
- **주제 이탈 감지**: 오디오 내용이 제목에서 암시한 주제와 크게 벗어났는지 확인합니다.

### 4. 3단계 판정 시스템 (Verdict Status)
- **verified_true**: 증거가 주장을 뒷받침함 (사실)
- **verified_false**: 증거가 주장을 반박함 (거짓)
- **insufficient_evidence**: 증거 부족으로 판정 불가

### 5. 종합 판정 (Verdict Agent)
- 텍스트, 이미지, 오디오 분석 결과를 LLM이 종합하여 최종 판정을 내립니다.
- **판정 요소**:
    - 텍스트 팩트체크 결과 (verified_true/verified_false/insufficient_evidence)
    - 이미지 재사용 및 맥락 일치 여부
    - 오디오 제목 낚시 및 주제 이탈 여부
- **최종 결과**: 종합적인 신뢰도(high/medium/low)와 권장 사항 제공

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

서버가 실행되면 `http://localhost:8000/docs`에서 API 문서를 확인할 수 있습니다.

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
- **속도**: 멀티모달 분석은 영상 길이에 따라 수 초에서 수 분이 소요될 수 있습니다. (스트리밍 최적화 적용됨)
- **정확도**: AI 분석 결과는 보조적인 수단이며, 100% 정확성을 보장하지 않습니다.

## 📄 라이선스

MIT License