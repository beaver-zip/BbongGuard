# 🛡️ BbongGuard - 멀티모달 가짜뉴스 탐지 플랫폼

BbongGuard는 YouTube 영상의 **텍스트(자막/댓글), 이미지(프레임), 오디오(음성)**를 종합적으로 분석하여 가짜뉴스, 낚시성 콘텐츠, 선동적인 영상을 탐지하는 AI 기반 확장프로그램입니다.

## 🌟 주요 기능

### 1. 텍스트 팩트체크 (Text Module)
- **RAG (Retrieval-Augmented Generation)**: Tavily API를 사용하여 웹에서 신뢰할 수 있는 증거를 수집하고, LLM(GPT-4o)이 주장의 진위를 판별합니다.
- **주장 추출**: 영상의 자막과 설명에서 핵심 주장을 추출합니다.
- **출처 검증**: 화이트리스트/블랙리스트 기반으로 신뢰할 수 있는 출처만 증거로 채택합니다.

### 2. 이미지 자극성 탐지 (Image Module)
- **스트리밍 샘플링**: 영상을 다운로드하지 않고 스트리밍 URL을 통해 0~90% 지점의 핵심 프레임(10장)을 즉시 추출하여 분석 속도를 극대화했습니다.
- **자극성(Provocation) 분석**: 화면 내 텍스트(OCR)가 실제 내용보다 과장되거나 자극적인지(Clickbait) 탐지합니다.
- **불일치(Inconsistency) 분석**: 썸네일이나 화면 텍스트가 영상의 실제 내용과 일치하는지 확인합니다.

### 3. 오디오 선동성 탐지 (Audio Module)
- **감정적 선동(Manipulation) 분석**: 화자의 목소리 톤과 감정을 분석하여, 내용에 비해 지나치게 격앙되거나 선동적인지 탐지합니다.
- **부자연스러움(Unnaturalness) 분석**: 기계음이나 인위적인 조작 흔적을 탐지합니다.

### 4. 종합 판정 (Verdict Agent)
- 텍스트, 이미지, 오디오 분석 결과를 종합하여 최종 판정을 내립니다.
- **판정 로직**:
    - **악의적인 가짜뉴스**: 팩트체크(거짓) + 자극성/선동성(높음)
    - **낚시성/과장된 콘텐츠**: 팩트체크(사실) + 자극성/선동성(높음)
    - **단순 오정보**: 팩트체크(거짓) + 자극성/선동성(낮음)

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

`.env` 파일을 생성하고 다음 정보를 입력하세요:

```ini
# Server Configuration
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# API Keys
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...

# RAG Configuration
RAG_MAX_CLAIMS=3
RAG_MAX_SEARCH_RESULTS=5
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