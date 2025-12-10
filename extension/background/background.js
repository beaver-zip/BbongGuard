// background.js - 백그라운드 서비스 워커 (통합 버전)

// ==========================================
// 1. Time Utils (time-utils.js)
// ==========================================

/**
 * ISO 8601 Duration 문자열을 초 단위 정수로 변환합니다.
 * 예: "PT1H2M10S" -> 3730
 */
function parseISODuration(duration) {
  if (!duration) return 0;
  
  const match = duration.match(/PT(\d+H)?(\d+M)?(\d+S)?/);
  if (!match) return 0;

  const hours = (parseInt(match[1]) || 0);
  const minutes = (parseInt(match[2]) || 0);
  const seconds = (parseInt(match[3]) || 0);

  return hours * 3600 + minutes * 60 + seconds;
}


// ==========================================
// 2. YouTube API (youtube-api.js)
// ==========================================

const YOUTUBE_API_BASE_URL = 'https://www.googleapis.com/youtube/v3';

// API 키 가져오기
async function getApiKey() {
  return new Promise((resolve, reject) => {
    chrome.storage.local.get(['youtubeApiKey'], (result) => {
      if (result.youtubeApiKey) {
        resolve(result.youtubeApiKey);
      } else {
        reject(new Error('YouTube API 키가 설정되지 않았습니다. 확장프로그램 설정 페이지에서 API 키를 입력해주세요.'));
      }
    });
  });
}

// 영상 정보 가져오기
async function getVideoInfo(videoId) {
  try {
    const apiKey = await getApiKey();
    const url = `${YOUTUBE_API_BASE_URL}/videos?part=snippet,statistics,contentDetails&id=${videoId}&key=${apiKey}`;

    const response = await fetch(url);
    const data = await response.json();

    if (!response.ok) {
      const errorMessage = data.error?.message || 'YouTube API 호출 실패';
      const errorCode = response.status;

      if (errorCode === 400) {
        throw new Error(`잘못된 요청: ${errorMessage} (API 키 형식을 확인해주세요)`);
      } else if (errorCode === 403) {
        throw new Error(`권한 없음: ${errorMessage} (YouTube Data API v3가 활성화되어 있는지 확인해주세요)`);
      } else if (errorCode === 429) {
        throw new Error(`할당량 초과: 일일 YouTube API 할당량을 초과했습니다`);
      } else {
        throw new Error(`YouTube API 오류 (${errorCode}): ${errorMessage}`);
      }
    }

    if (!data.items || data.items.length === 0) {
      throw new Error('영상을 찾을 수 없습니다.');
    }

    const video = data.items[0];
    return {
      videoId: videoId,
      title: video.snippet.title,
      description: video.snippet.description,
      channelTitle: video.snippet.channelTitle,
      channelId: video.snippet.channelId,
      publishedAt: video.snippet.publishedAt,
      thumbnailUrl: video.snippet.thumbnails.high?.url || video.snippet.thumbnails.default.url,
      viewCount: video.statistics.viewCount,
      likeCount: video.statistics.likeCount,
      commentCount: video.statistics.commentCount,
      duration: video.contentDetails.duration,
      tags: video.snippet.tags || []
    };

  } catch (error) {
    console.error('영상 정보 가져오기 실패:', error);
    throw error;
  }
}



// 관련 영상 가져오기
async function getRelatedVideos(videoId, maxResults = 9) {
  try {
    const apiKey = await getApiKey();
    const url = `${YOUTUBE_API_BASE_URL}/search?part=snippet&relatedToVideoId=${videoId}&type=video&maxResults=${maxResults}&key=${apiKey}`;

    const response = await fetch(url);
    const data = await response.json();

    if (!response.ok) {
      console.warn('관련 영상을 가져올 수 없습니다:', data.error?.message);
      return [];
    }

    const relatedVideos = data.items?.map(item => ({
      videoId: item.id.videoId,
      title: item.snippet.title,
      description: item.snippet.description || "",
      channelTitle: item.snippet.channelTitle,
      thumbnailUrl: item.snippet.thumbnails.default.url
    })) || [];

    return relatedVideos;

  } catch (error) {
    console.error('관련 영상 가져오기 실패:', error);
    return [];
  }
}


// ==========================================
// 3. Inference API (inference-api.js)
// ==========================================

// 추론 서버 URL 가져오기
async function getInferenceServerUrl() {
  return new Promise((resolve, reject) => {
    chrome.storage.local.get(['inferenceServerUrl'], (result) => {
      if (result.inferenceServerUrl) {
        resolve(result.inferenceServerUrl);
      } else {
        resolve('http://localhost:8000');
      }
    });
  });
}

/**
 * 추론 서버로 데이터를 전송하고 분석 결과를 스트리밍(NDJSON)으로 수신합니다.
 * 
 * @param {Object} videoData - 영상 메타데이터
 * @returns {Promise<Object>} 분석 결과 객체 (verdict, evidence, details 등)
 * @throws {Error} 서버 통신 오류 또는 분석 실패 시
 */
async function analyzeWithInferenceServer(videoData) {
  try {
    const serverUrl = await getInferenceServerUrl();
    const endpoint = `${serverUrl}/api/analyze-multimodal`;

    const payload = {
      video_id: videoData.videoId,
      title: videoData.title,
      description: videoData.description || "",
      duration_sec: videoData.durationSec || 0,
      channel_title: videoData.channelTitle,
      views: parseInt(videoData.viewCount) || 0,
      thumbnail_url: videoData.thumbnailUrl
    };

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || errorData.message || `추론 서버 응답 오류 (${response.status})`);
    }

    // Streaming Response 처리 (NDJSON)
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let finalResult = null;

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Buffer에서 줄바꿈(\n)을 찾아서 처리하는 방식 (Robust NDJSON parsing)
        let boundary = buffer.indexOf('\n');
        
        while (boundary !== -1) {
          const chunk = buffer.slice(0, boundary).trim();
          buffer = buffer.slice(boundary + 1); // 처리된 부분 제거

          if (chunk) {
            try {
              const msg = JSON.parse(chunk);
              
              if (msg.type === 'progress') {
                // 팝업에 진행 상황 전달
                chrome.runtime.sendMessage({
                  action: 'analysisProgress',
                  message: msg.message
                }).catch(() => {});
                
                // 진행 상황 storage에도 저장 (팝업 재오픈 시 복원용)
                const currentState = await getAnalysisState();
                if (currentState && 
                    currentState.status === 'analyzing' && 
                    currentState.videoId === payload.video_id) {
                  await saveAnalysisState({
                    ...currentState,
                    progress: msg.message
                  });
                }
              } else if (msg.type === 'result') {
                finalResult = msg.data;
              } else if (msg.type === 'error') {
                throw new Error(msg.message);
              }
            } catch (e) {
              console.warn('JSON Parse Error:', e, 'Chunk:', chunk);
              // 치명적이지 않은 파싱 에러는 무시하고 계속 진행
            }
          }
          boundary = buffer.indexOf('\n');
        }
      }
    } catch (streamError) {
      throw streamError;
    }

    if (!finalResult) {
      throw new Error("서버로부터 유효한 분석 결과를 받지 못했습니다.");
    }

    const verdict = finalResult.final_verdict;

    return {
      verdict: verdict,
      evidence: verdict.key_evidence && verdict.key_evidence.length > 0 ? verdict.key_evidence : [verdict.overall_reasoning],
      textSources: verdict.text_sources || [],
      details: verdict,
      text_result: finalResult.text_result 
    };

  } catch (error) {
    console.error('추론 서버 통신 실패:', error);
    if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
      throw new Error('추론 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.');
    }
    throw error;
  }
}


// ==========================================
// 4. Analysis State Management
// ==========================================

// 분석 상태 저장
async function saveAnalysisState(state) {
  await chrome.storage.local.set({ analysisState: state });
}

// 분석 상태 조회
async function getAnalysisState() {
  const result = await chrome.storage.local.get(['analysisState']);
  return result.analysisState || null;
}

// 분석 상태 초기화
async function clearAnalysisState() {
  await chrome.storage.local.remove(['analysisState']);
}

// 알림 전송
function sendNotification(title, message, videoId) {
  console.log('알림 전송 시도:', { title, message, videoId });
  
  try {
    chrome.notifications.create(
      `analysis-${videoId}`,
      {
        type: 'basic',
        iconUrl: chrome.runtime.getURL('icons/icon128.png'),
        title: title,
        message: message
      },
      (notificationId) => {
        if (chrome.runtime.lastError) {
          console.error('알림 생성 실패:', chrome.runtime.lastError.message);
        } else {
          console.log('알림 생성 성공:', notificationId);
        }
      }
    );
  } catch (error) {
    console.error('알림 전송 중 예외 발생:', error);
  }
}

// ==========================================
// 5. Main Background Logic
// ==========================================

// 메시지 리스너
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'analyzeVideo') {
    handleVideoAnalysis(request.videoId)
      .then(result => sendResponse({ data: result }))
      .catch(error => sendResponse({ error: error.message }));

    return true; // 비동기 응답
  }

  if (request.action === 'getAnalysisState') {
    getAnalysisState().then(state => sendResponse({ state }));
    return true;
  }

  if (request.action === 'clearAnalysisState') {
    clearAnalysisState().then(() => sendResponse({ success: true }));
    return true;
  }
});

// 영상 분석 메인 함수
async function handleVideoAnalysis(videoId) {
  try {
    console.log('영상 분석 시작:', videoId);

    // 분석 시작 상태 저장
    await saveAnalysisState({
      videoId: videoId,
      status: 'analyzing',
      progress: 'YouTube 영상 정보 수집 중...',
      startedAt: Date.now()
    });

    // 1. YouTube Data API로 영상 정보 수집
    const videoData = await fetchYouTubeData(videoId);

    // 진행 상황 업데이트
    await saveAnalysisState({
      videoId: videoId,
      status: 'analyzing',
      progress: 'AI 서버에서 분석 중...',
      videoTitle: videoData.title,
      startedAt: Date.now()
    });

    // 2. 추론 서버로 데이터 전송
    const inferenceResult = await sendToInferenceServer(videoData);

    // 3. 결과 구성
    const result = {
      verdict: inferenceResult.verdict,
      evidence: inferenceResult.evidence,
      textSources: inferenceResult.textSources,
      text_result: inferenceResult.text_result,
      videoInfo: {
        title: videoData.title,
        channelTitle: videoData.channelTitle,
        viewCount: videoData.viewCount,
        publishedAt: videoData.publishedAt
      }
    };

    // 분석 완료 상태 저장
    await saveAnalysisState({
      videoId: videoId,
      status: 'completed',
      result: result,
      completedAt: Date.now()
    });

    // 완료 알림 전송
    sendNotification(
      'BbongGuard 분석 완료',
      `"${videoData.title.substring(0, 30)}..." 분석이 완료되었습니다.`,
      videoId
    );

    return result;

  } catch (error) {
    console.error('영상 분석 중 오류:', error);

    // 에러 상태 저장
    await saveAnalysisState({
      videoId: videoId,
      status: 'error',
      error: error.message,
      errorAt: Date.now()
    });

    // 에러 알림 전송
    sendNotification(
      'BbongGuard 분석 실패',
      error.message.substring(0, 50),
      videoId
    );

    throw error;
  }
}

// YouTube 데이터 수집
async function fetchYouTubeData(videoId) {
  try {
    const videoInfo = await getVideoInfo(videoId);
    const relatedVideos = await getRelatedVideos(videoId);

    const durationSec = parseISODuration(videoInfo.duration);

    return {
      videoId: videoId,
      title: videoInfo.title,
      description: videoInfo.description,
      channelTitle: videoInfo.channelTitle,
      channelId: videoInfo.channelId,
      publishedAt: videoInfo.publishedAt,
      viewCount: videoInfo.viewCount,
      likeCount: videoInfo.likeCount,
      thumbnailUrl: videoInfo.thumbnailUrl,
      durationSec: durationSec,
      relatedVideos: relatedVideos
    };

  } catch (error) {
    console.error('YouTube 데이터 수집 실패:', error);
    throw new Error(`YouTube 데이터 수집 실패: ${error.message}`);
  }
}

// 추론 서버로 데이터 전송
async function sendToInferenceServer(videoData) {
  try {
    const result = await analyzeWithInferenceServer(videoData);
    return result;

  } catch (error) {
    console.error('추론 서버 통신 실패:', error);
    throw new Error(`AI 분석 실패: ${error.message}`);
  }
}

console.log('BbongGuard Background Service Worker 실행 중 (통합 버전)');

// 수정사항
// 1. 확률 매핑 수정
// 2. 댓글 수집 제거
