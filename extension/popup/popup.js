// popup.js - 팝업 UI 로직 및 결과 표시

// DOM 요소
const states = {
  initial: document.getElementById('initial-state'),
  loading: document.getElementById('loading-state'),
  result: document.getElementById('result-state'),
  error: document.getElementById('error-state')
};

const buttons = {
  analyze: document.getElementById('analyze-btn'),
  reanalyze: document.getElementById('reanalyze-btn'),
  retry: document.getElementById('retry-btn')
};

// 상태 전환 함수
function showState(stateName) {
  Object.values(states).forEach(state => state.classList.add('hidden'));
  if (states[stateName]) {
    states[stateName].classList.remove('hidden');
  }
}

// 로딩 상태 메시지 업데이트
function updateLoadingMessage(message) {
  const loadingDetail = document.querySelector('.loading-detail');
  if (loadingDetail) {
    loadingDetail.textContent = message;
  }
}

// 에러 표시
function showError(message) {
  const errorMessage = document.getElementById('error-message');
  errorMessage.textContent = message;
  console.error('BbongGuard 에러:', message); // 콘솔에도 출력
  showState('error');
}

// 결과 표시
function showResult(data) {
  // 가짜뉴스 확률 표시 (0~1 범위를 0~100%로 변환)
  const probabilityRaw = data.fakeProbability || 0;
  const probability = probabilityRaw * 100;  // 0.7838 → 78.38
  const probabilityFill = document.getElementById('probability-fill');
  const probabilityText = document.getElementById('probability-text');

  probabilityFill.style.width = `${probability}%`;
  probabilityText.textContent = `${probability.toFixed(1)}%`;

  // 확률에 따른 색상 변경
  if (probability < 30) {
    probabilityText.style.color = '#10b981'; // 녹색
  } else if (probability < 70) {
    probabilityText.style.color = '#fbbf24'; // 노란색
  } else {
    probabilityText.style.color = '#ef4444'; // 빨간색
  }

  // 근거 표시
  const evidenceList = document.getElementById('evidence-list');
  evidenceList.innerHTML = '';

  if (data.evidence && data.evidence.length > 0) {
    data.evidence.forEach(item => {
      const li = document.createElement('li');
      li.textContent = item;
      evidenceList.appendChild(li);
    });
  } else {
    const li = document.createElement('li');
    li.textContent = '분석 근거가 제공되지 않았습니다.';
    evidenceList.appendChild(li);
  }

  // 영상 정보 표시
  const videoDetails = document.getElementById('video-details');
  videoDetails.innerHTML = `
    <p><strong>제목:</strong> ${data.videoInfo?.title || 'N/A'}</p>
    <p><strong>채널:</strong> ${data.videoInfo?.channelTitle || 'N/A'}</p>
    <p><strong>조회수:</strong> ${data.videoInfo?.viewCount ? Number(data.videoInfo.viewCount).toLocaleString() : 'N/A'}</p>
    <p><strong>업로드:</strong> ${data.videoInfo?.publishedAt ? new Date(data.videoInfo.publishedAt).toLocaleDateString('ko-KR') : 'N/A'}</p>
  `;

  showState('result');
}

// YouTube 영상 분석 시작
async function analyzeVideo() {
  try {
    showState('loading');
    updateLoadingMessage('YouTube 영상 정보 확인 중...');

    // 현재 탭에서 video ID 가져오기
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (!tab.url.includes('youtube.com/watch')) {
      throw new Error('YouTube 영상 페이지에서 실행해주세요.');
    }

    // Content script에 메시지 전송하여 video ID 가져오기
    let response;
    try {
      response = await chrome.tabs.sendMessage(tab.id, { action: 'getVideoId' });
    } catch (error) {
      // Content Script 연결 실패 - 프로그래밍 방식으로 재주입 시도
      console.log('Content Script 연결 실패, 재주입 시도...');

      try {
        await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ['content/content.js']
        });

        // 재주입 후 재시도
        await new Promise(resolve => setTimeout(resolve, 100)); // 100ms 대기
        response = await chrome.tabs.sendMessage(tab.id, { action: 'getVideoId' });
      } catch (reinjectError) {
        throw new Error('확장프로그램과 페이지 연결에 실패했습니다. 페이지를 새로고침한 후 다시 시도해주세요.');
      }
    }

    if (!response || !response.videoId) {
      throw new Error('영상 ID를 가져올 수 없습니다.');
    }

    const videoId = response.videoId;
    updateLoadingMessage('YouTube Data API 호출 중...');

    // Background script를 통해 API 호출
    const result = await chrome.runtime.sendMessage({
      action: 'analyzeVideo',
      videoId: videoId
    });

    if (result.error) {
      throw new Error(result.error);
    }

    // 결과 표시
    showResult(result.data);

  } catch (error) {
    console.error('분석 중 오류:', error);
    showError(error.message || '알 수 없는 오류가 발생했습니다.');
  }
}

// 이벤트 리스너
buttons.analyze.addEventListener('click', analyzeVideo);
buttons.reanalyze.addEventListener('click', analyzeVideo);
buttons.retry.addEventListener('click', analyzeVideo);

// 팝업 열릴 때 초기 상태 확인
document.addEventListener('DOMContentLoaded', async () => {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (!tab.url.includes('youtube.com/watch')) {
      showError('YouTube 영상 페이지에서만 사용할 수 있습니다.');
    } else {
      showState('initial');
    }
  } catch (error) {
    showError('확장프로그램 초기화 중 오류가 발생했습니다.');
  }
});
