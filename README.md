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
├── manifest.json              # Chrome 확장프로그램 설정
├── popup/                     # 팝업 UI
│   ├── popup.html
│   ├── popup.css
│   └── popup.js
├── content/                   # Content script
│   └── content.js
├── background/                # Background service worker
│   └── background.js
├── api/                       # API 통신 모듈
│   ├── youtube-api.js
│   └── inference-api.js
├── utils/                     # 유틸리티
│   ├── config.js
│   └── video-info-extractor.js
├── icons/                     # 확장프로그램 아이콘
├── .env                       # 환경 변수
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
4. `BbongGuard` 폴더 선택

### 4. 확장프로그램에 API 키 설정

확장프로그램이 로드되면, 다음 중 하나의 방법으로 API 키를 설정해야 합니다:

**방법 1: Chrome DevTools Console 사용**
1. 확장프로그램 아이콘 우클릭 > "검사" (또는 팝업 열기)
2. DevTools Console에서 다음 명령 실행:
```javascript
chrome.storage.local.set({ youtubeApiKey: 'YOUR_API_KEY_HERE' });
```

**방법 2: 설정 페이지 추가 (TODO)**
- 추후 옵션 페이지를 추가하여 UI로 설정 가능하도록 개선 예정

## 🐍 Python 백엔드 (추론 서버)

추론 서버는 추후 딥러닝 모델과 함께 구현될 예정입니다. 현재는 기본 구조만 제공됩니다.

### Python 환경 설정

```bash
# 가상환경 활성화
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate  # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 추론 서버 실행 (TODO)

추후 FastAPI 기반 추론 서버 구현 예정:

```bash
# 서버 실행 (예시)
uvicorn server.main:app --reload --port 8000
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
- `commentThreads.list`: 댓글 (최대 50개)
- `search.list`: 관련 영상 목록

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

- [ ] 추론 서버 구현 (딥러닝 모델 통합)
- [ ] 옵션 페이지 추가 (API 키 설정 UI)
- [ ] 백엔드 프록시 서버 구현 (API 키 보안)
- [ ] 분석 결과 캐싱
- [ ] 테스트 코드 작성

## 📄 라이선스

미정