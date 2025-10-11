# 🛡️ BbongGuard - YouTube 가짜뉴스 탐지 확장프로그램

YouTube 영상의 가짜뉴스 여부를 AI로 분석하여 알려주는 Chrome 확장프로그램입니다.

## 📋 기능

- YouTube 영상의 가짜뉴스 확률 분석
- YouTube Data API v3를 통한 영상 정보, 댓글, 관련 영상 수집
- AI 추론 서버를 통한 종합 분석
- 직관적인 UI로 분석 결과 표시

## 🏗️ 프로젝트 구조

```
BbongGuard/
├── extension/                 # Chrome 확장프로그램
│   ├── manifest.json         # 확장프로그램 설정
│   ├── popup/                # 팝업 UI
│   │   ├── popup.html
│   │   ├── popup.css
│   │   └── popup.js
│   ├── content/              # Content script
│   │   └── content.js
│   ├── background/           # Background service worker
│   │   └── background.js
│   ├── api/                  # API 통신 모듈
│   │   ├── youtube-api.js
│   │   └── inference-api.js
│   ├── utils/                # 유틸리티
│   │   ├── config.js
│   │   └── video-info-extractor.js
│   └── icons/                # 확장프로그램 아이콘
│
├── server/                    # FastAPI 추론 서버
│   ├── main.py               # FastAPI 애플리케이션
│   ├── config.py             # 서버 설정
│   ├── models.py             # API 요청/응답 스키마
│   ├── preprocessor.py       # 데이터 전처리
│   ├── inference.py          # 추론 엔진
│   └── models/               # 학습된 모델 파일 (GitHub 제외)
│       ├── OR-TDC.h5        # CNN 모델 (237MB)
│       └── doc2vec.model    # Doc2Vec 모델 (13MB)
│
├── .env                       # 환경 변수
├── .gitignore                 # Git ignore (모델 파일 제외)
├── .venv/                     # Python 가상환경
└── requirements.txt           # Python 의존성
```

## 🚀 설치 방법

### 1. 저장소 클론

```bash
git clone https://github.com/beaver-zip/BbongGuard.git
cd BbongGuard
```

### 2. 환경 변수 설정

`.env` 파일에 YouTube API 키를 추가하세요:

```env
YOUTUBE_API_KEY=your_api_key_here
INFERENCE_SERVER_URL=http://localhost:8000
```

**YouTube API 키 발급 방법:**
1. [Google Cloud Console](https://console.cloud.google.com/)에 접속
2. 새 프로젝트 생성 또는 기존 프로젝트 선택
3. "API 및 서비스" > "사용 설정된 API 및 서비스"
4. "YouTube Data API v3" 검색 후 사용 설정
5. "사용자 인증 정보" > "사용자 인증 정보 만들기" > "API 키" 생성

### 3. Chrome 확장프로그램 로드

1. Chrome 브라우저에서 `chrome://extensions/` 접속
2. 우측 상단의 "개발자 모드" 활성화
3. "압축해제된 확장 프로그램을 로드합니다" 클릭
4. `BbongGuard/extension` 폴더 선택

### 4. 확장프로그램에 API 키 설정

확장프로그램이 로드되면, 다음 중 하나의 방법으로 API 키를 설정해야 합니다:

**방법 1: 설정 페이지 사용 (권장)**
1. Chrome 브라우저에서 `chrome://extensions/` 접속
2. BbongGuard 확장프로그램 찾기
3. "확장 프로그램 옵션" 또는 "세부정보" 클릭
4. 설정 페이지에서 API 키 입력 및 저장
5. "API 키 테스트" 버튼으로 정상 작동 확인

**방법 2: Chrome DevTools Console 사용**
1. 확장프로그램 아이콘 우클릭 > "검사" (또는 팝업 열기)
2. DevTools Console에서 다음 명령 실행:
```javascript
chrome.storage.local.set({ youtubeApiKey: 'YOUR_API_KEY_HERE' });
```

## 🐍 Python 백엔드 (추론 서버)

FastAPI 기반 추론 서버가 구현되어 있습니다. OR-TDC 모델 (Original + Related + Title + Description + Comments)을 사용하여 YouTube 영상의 가짜뉴스 여부를 판정합니다.

### 모델 정보

- **Doc2Vec**: 텍스트 임베딩 모델 (100차원 벡터)
- **CNN**: 1D Convolutional Neural Network (가짜뉴스 분류)
- **입력**: 원본 영상 + 관련 영상 9개의 텍스트 (제목, 설명, 댓글)
- **출력**: Fake/Real 판정 + 확률

### Python 환경 설정

```bash
# Python 3.10 이상 권장

# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate  # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 환경 변수 설정

```bash
# .env.example을 .env로 복사
cp .env.example .env

# .env 파일 수정 (필요시)
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
```

### 추론 서버 실행

```bash
# 방법 1: uvicorn 직접 실행
uvicorn server.main:app --host 0.0.0.0 --port 8000

# 방법 2: Python 모듈로 실행
python -m server.main

# 개발 모드 (자동 재시작)
uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
```

서버가 정상적으로 실행되면:
- API 문서: http://localhost:8000/docs
- 서버 상태: http://localhost:8000/health

### API 엔드포인트

**1. Health Check**
```
GET /health
```
서버 및 모델 로딩 상태 확인

**2. 영상 분석**
```
POST /api/analyze
Content-Type: application/json

{
  "videoId": "VIDEO_ID",
  "title": "영상 제목",
  "description": "영상 설명",
  "comments": ["댓글1", "댓글2", ...],
  "relatedVideos": [
    {
      "title": "관련 영상 제목",
      "description": "관련 영상 설명"
    },
    ...
  ]
}
```

응답:
```json
{
  "success": true,
  "videoId": "VIDEO_ID",
  "prediction": "Fake",
  "fakeProbability": 0.75,
  "confidence": 0.75,
  "details": {
    "fake_probability": 0.75,
    "real_probability": 0.25,
    "model_type": "OR-TDC",
    "text_combination": "TDC"
  }
}
```

## 📖 사용 방법

1. YouTube 영상 페이지에 접속
2. 확장프로그램 아이콘 클릭
3. "영상 분석하기" 버튼 클릭
4. 분석 결과 확인 (가짜뉴스 확률, 근거 등)

## 🛠️ 개발

### API 구조

**YouTube Data API 호출 항목:**
- `videos.list`: 영상 정보 (제목, 설명, 조회수 등)
- `commentThreads.list`: 댓글 (최대 20개)
- `search.list`: 관련 영상 목록 (최대 9개)

**추론 서버 API (TODO):**
```
POST /api/analyze
Content-Type: application/json

{
  "videoId": "...",
  "title": "...",
  "description": "...",
  "comments": [...],
  "thumbnailUrl": "..."
}

Response:
{
  "fakeProbability": 75.5,
  "evidence": ["...", "..."],
  "details": {...}
}
```

### 할당량 관리

YouTube Data API v3는 일일 10,000 units의 무료 할당량을 제공합니다:
- `videos.list`: 1 unit
- `commentThreads.list`: 1 unit (페이지당)
- `search.list`: 100 units

댓글이 많은 영상을 분석할 경우 할당량이 빠르게 소진될 수 있으므로 주의하세요.

## ⚠️ 주의사항

1. **API 키 보안**: Chrome 확장프로그램에 API 키를 직접 포함하면 노출 위험이 있습니다. 실제 배포 시에는 백엔드 프록시 서버를 통해 API를 호출하는 것을 권장합니다.

2. **할당량 제한**: YouTube API 무료 할당량을 초과하지 않도록 주의하세요.

3. **분석 결과**: AI 분석 결과는 참고용이며, 100% 정확하지 않을 수 있습니다.

## 📝 TODO

- [x] Extension과 Server 디렉토리 분리
- [x] .gitignore에 모델 파일 추가 (GitHub 업로드 방지)
- [x] 옵션 페이지 추가 (API 키 설정 UI)
- [ ] 백엔드 프록시 서버 구현 (API 키 보안)
- [ ] 분석 결과 캐싱
- [ ] 테스트 코드 작성
- [ ] 모델 성능 개선 및 재학습
- [ ] 배치 추론 지원 (여러 영상 동시 분석)

## 📄 라이선스

미정