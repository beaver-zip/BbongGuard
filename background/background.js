// background.js - 백그라운드 서비스 워커
// API 호출 및 데이터 처리를 담당

// API 모듈 import (Manifest V3에서는 importScripts 사용)
importScripts('../api/youtube-api.js', '../api/inference-api.js');

// 메시지 리스너
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'analyzeVideo') {
    handleVideoAnalysis(request.videoId)
      .then(result => sendResponse({ data: result }))
      .catch(error => sendResponse({ error: error.message }));

    return true; // 비동기 응답
  }
});

// 영상 분석 메인 함수
async function handleVideoAnalysis(videoId) {
  try {
    console.log('영상 분석 시작:', videoId);

    // 1. YouTube Data API로 영상 정보 수집
    const videoData = await fetchYouTubeData(videoId);

    // 2. 추론 서버로 데이터 전송
    const inferenceResult = await sendToInferenceServer(videoData);

    // 3. 결과 반환
    return {
      fakeProbability: inferenceResult.probability,
      evidence: inferenceResult.evidence,
      videoInfo: {
        title: videoData.title,
        channelTitle: videoData.channelTitle,
        viewCount: videoData.viewCount,
        publishedAt: videoData.publishedAt
      }
    };

  } catch (error) {
    console.error('영상 분석 중 오류:', error);
    throw error;
  }
}

// YouTube 데이터 수집 (youtube-api.js 사용)
async function fetchYouTubeData(videoId) {
  try {
    // 영상 정보, 댓글, 관련 영상 등을 수집
    const videoInfo = await getVideoInfo(videoId);
    const comments = await getVideoComments(videoId);
    const relatedVideos = await getRelatedVideos(videoId);

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
      comments: comments,
      relatedVideos: relatedVideos
    };

  } catch (error) {
    console.error('YouTube 데이터 수집 실패:', error);
    throw new Error('YouTube 데이터를 가져오는 데 실패했습니다.');
  }
}

// 추론 서버로 데이터 전송 (inference-api.js 사용)
async function sendToInferenceServer(videoData) {
  try {
    const result = await analyzeWithInferenceServer(videoData);
    return result;

  } catch (error) {
    console.error('추론 서버 통신 실패:', error);
    throw new Error('AI 분석에 실패했습니다.');
  }
}

console.log('BbongGuard Background Service Worker 실행 중');
