// content.js - YouTube 페이지에 주입되는 스크립트
// YouTube 영상 페이지에서 video ID를 추출하는 역할

// URL에서 YouTube video ID 추출
function getVideoIdFromUrl() {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get('v');
}

// 현재 재생 중인 영상 정보 가져오기 (DOM에서 직접 추출)
function getVideoInfoFromDOM() {
  try {
    const videoTitle = document.querySelector('h1.ytd-watch-metadata yt-formatted-string')?.textContent || '';
    const channelName = document.querySelector('ytd-channel-name#channel-name yt-formatted-string')?.textContent || '';
    const viewCount = document.querySelector('ytd-watch-metadata #info-container span.view-count')?.textContent || '';

    return {
      title: videoTitle,
      channel: channelName,
      views: viewCount
    };
  } catch (error) {
    console.error('DOM에서 영상 정보 추출 실패:', error);
    return null;
  }
}

// 메시지 리스너
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getVideoId') {
    const videoId = getVideoIdFromUrl();
    const videoInfo = getVideoInfoFromDOM();

    sendResponse({
      videoId: videoId,
      domInfo: videoInfo
    });
  }

  return true; // 비동기 응답을 위해 true 반환
});

// 페이지 로드 시 video ID 확인 (디버깅용)
console.log('BbongGuard Content Script 로드됨');
console.log('현재 Video ID:', getVideoIdFromUrl());
