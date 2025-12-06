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
  // 탭 전환 로직
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      // 모든 탭 비활성화
      tabBtns.forEach(b => b.classList.remove('active'));
      tabContents.forEach(c => c.classList.remove('active'));

      // 선택된 탭 활성화
      btn.classList.add('active');
      const tabId = btn.dataset.tab;
      document.getElementById(`tab-${tabId}`).classList.add('active');
    });
  });

  // Verdict 표시
  const verdict = data.verdict;
  const verdictContainer = document.getElementById('verdict-container');
  
  // 초기화
  verdictContainer.className = 'verdict-container';
  verdictContainer.innerHTML = '';

  if (verdict.is_fake_news) {
    verdictContainer.classList.add('fake');
    verdictContainer.innerHTML = `
      <span class="verdict-icon">⚠️</span>
      <p class="verdict-text">가짜뉴스일 가능성이 높습니다</p>
    `;
  } else {
    verdictContainer.classList.add('real');
    verdictContainer.innerHTML = `
      <span class="verdict-icon">✅</span>
      <p class="verdict-text">진짜 뉴스일 가능성이 높습니다</p>
    `;
  }

  // 종합 근거 표시
  const overallReasoning = document.getElementById('overall-reasoning');
  overallReasoning.textContent = verdict.overall_reasoning || "판단 근거가 제공되지 않았습니다.";

  // 상세 근거 (모듈별 요약) 표시
  document.getElementById('text-analysis-summary').textContent = verdict.text_analysis_summary || "분석 결과 없음";
  document.getElementById('image-analysis-summary').textContent = verdict.image_analysis_summary || "분석 결과 없음";
  document.getElementById('audio-analysis-summary').textContent = verdict.audio_analysis_summary || "분석 결과 없음";

  // [New] 상세 분석 내용 표시 (Details Tab)
  document.getElementById('image-analysis-details').textContent = verdict.image_analysis_details || "상세 분석 결과가 없습니다.";
  document.getElementById('audio-analysis-details').textContent = verdict.audio_analysis_details || "상세 분석 결과가 없습니다.";

  // [New] 텍스트 상세 분석 (Claims) 표시
  const textDetailsContainer = document.getElementById('text-analysis-details');
  textDetailsContainer.innerHTML = ''; // 초기화

  if (data.text_result && data.text_result.claims && data.text_result.claims.length > 0) {
    data.text_result.claims.forEach(claim => {
      const claimItem = document.createElement('div');
      claimItem.className = 'claim-item';
      
      let statusIcon = '❓';
      let statusClass = 'unknown';
      let statusText = '판단 불가';

      if (claim.verdict_status === 'verified_true') {
        statusIcon = '✅';
        statusClass = 'true';
        statusText = '사실';
      } else if (claim.verdict_status === 'verified_false') {
        statusIcon = '❌';
        statusClass = 'false';
        statusText = '거짓';
      }

      claimItem.innerHTML = `
        <div class="claim-header">
          <span class="claim-status ${statusClass}">${statusIcon} ${statusText}</span>
          <p class="claim-text">${claim.claim_text}</p>
        </div>
        <p class="claim-reason">${claim.verdict_reason || '근거가 제공되지 않았습니다.'}</p>
      `;
      textDetailsContainer.appendChild(claimItem);
    });
  } else {
    textDetailsContainer.innerHTML = '<p class="detail-text">추출된 주장이 없습니다.</p>';
  }

  // 근거 표시


  // 영상 정보 표시
  const videoDetails = document.getElementById('video-details');
  videoDetails.innerHTML = `
    <p><strong>제목:</strong> ${data.videoInfo?.title || 'N/A'}</p>
    <p><strong>채널:</strong> ${data.videoInfo?.channelTitle || 'N/A'}</p>
    <p><strong>조회수:</strong> ${data.videoInfo?.viewCount ? Number(data.videoInfo.viewCount).toLocaleString() : 'N/A'}</p>
    <p><strong>업로드:</strong> ${data.videoInfo?.publishedAt ? new Date(data.videoInfo.publishedAt).toLocaleDateString('ko-KR') : 'N/A'}</p>
  `;

  // [New] 텍스트 출처 표시
  const existingSources = document.getElementById('sources-section');
  if (existingSources) existingSources.remove();

  if (data.textSources && data.textSources.length > 0) {
    const sourcesSection = document.createElement('div');
    sourcesSection.id = 'sources-section';
    sourcesSection.className = 'evidence-section'; // 스타일 재사용
    sourcesSection.style.marginTop = '15px';
    
    const h3 = document.createElement('h3');
    h3.textContent = '참고 출처';
    sourcesSection.appendChild(h3);
    
    const ul = document.createElement('ul');
    ul.className = 'evidence-list';
    
    data.textSources.forEach(source => {
      const li = document.createElement('li');
      const link = document.createElement('a');
      link.href = source.url;
      link.textContent = source.title || source.url;
      link.target = '_blank'; // 새 탭에서 열기
      link.style.color = '#3b82f6'; // 링크 색상 (파란색)
      link.style.textDecoration = 'underline';
      
      li.appendChild(link);
      ul.appendChild(li);
    });
    
    sourcesSection.appendChild(ul);
    
    // evidence-section 뒤에 추가
    const evidenceSection = document.querySelector('.evidence-section');
    if (evidenceSection && evidenceSection.parentNode) {
        evidenceSection.parentNode.insertBefore(sourcesSection, evidenceSection.nextSibling);
    }
  }

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

// 설정 버튼 이벤트 리스너
document.getElementById('settings-btn').addEventListener('click', () => {
  if (chrome.runtime.openOptionsPage) {
    chrome.runtime.openOptionsPage();
  } else {
    window.open(chrome.runtime.getURL('options/options.html'));
  }
});

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
