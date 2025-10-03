// config.js - 설정 관리 유틸리티

// 기본 설정값
const DEFAULT_CONFIG = {
  inferenceServerUrl: 'http://localhost:8000',
  maxComments: 50,
  maxRelatedVideos: 10,
  apiTimeout: 30000 // 30초
};

// 설정 저장
async function saveConfig(config) {
  return new Promise((resolve) => {
    chrome.storage.local.set(config, () => {
      console.log('설정 저장 완료:', config);
      resolve();
    });
  });
}

// 설정 불러오기
async function loadConfig() {
  return new Promise((resolve) => {
    chrome.storage.local.get(Object.keys(DEFAULT_CONFIG), (result) => {
      const config = { ...DEFAULT_CONFIG, ...result };
      resolve(config);
    });
  });
}

// API 키 저장
async function saveApiKey(apiKey) {
  return new Promise((resolve) => {
    chrome.storage.local.set({ youtubeApiKey: apiKey }, () => {
      console.log('YouTube API 키 저장 완료');
      resolve();
    });
  });
}

// API 키 불러오기
async function loadApiKey() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['youtubeApiKey'], (result) => {
      resolve(result.youtubeApiKey || null);
    });
  });
}

// 설정 초기화
async function resetConfig() {
  return new Promise((resolve) => {
    chrome.storage.local.clear(() => {
      console.log('설정 초기화 완료');
      resolve();
    });
  });
}
