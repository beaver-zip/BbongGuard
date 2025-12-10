// DOM Elements
const form = document.getElementById('settings-form');
const youtubeApiKeyInput = document.getElementById('youtube-api-key');
const inferenceServerUrlInput = document.getElementById('inference-server-url');
const testBtn = document.getElementById('test-btn');
const statusMessage = document.getElementById('status-message');
const statusIcon = document.getElementById('status-icon');
const statusText = document.getElementById('status-text');

// Load saved settings on page load
document.addEventListener('DOMContentLoaded', loadSettings);

// Form submit handler
form.addEventListener('submit', handleSaveSettings);

// Test button handler
testBtn.addEventListener('click', handleTestApiKey);

/**
 * Load saved settings from chrome.storage
 */
async function loadSettings() {
  try {
    const result = await chrome.storage.local.get([
      'youtubeApiKey',
      'inferenceServerUrl'
    ]);

    if (result.youtubeApiKey) {
      youtubeApiKeyInput.value = result.youtubeApiKey;
      showStatus('info', '✓', '저장된 설정을 불러왔습니다.');
    }

    if (result.inferenceServerUrl) {
      inferenceServerUrlInput.value = result.inferenceServerUrl;
    }
  } catch (error) {
    console.error('Failed to load settings:', error);
    showStatus('error', '✗', '설정을 불러오는데 실패했습니다.');
  }
}

/**
 * Save settings to chrome.storage
 */
async function handleSaveSettings(event) {
  event.preventDefault();

  const youtubeApiKey = youtubeApiKeyInput.value.trim();
  const inferenceServerUrl = inferenceServerUrlInput.value.trim();

  // Validation
  if (!youtubeApiKey) {
    showStatus('error', '✗', 'YouTube API 키를 입력해주세요.');
    youtubeApiKeyInput.focus();
    return;
  }

  if (!inferenceServerUrl) {
    showStatus('error', '✗', '추론 서버 URL을 입력해주세요.');
    inferenceServerUrlInput.focus();
    return;
  }

  // Validate API key format (basic check)
  if (!youtubeApiKey.startsWith('AIzaSy') || youtubeApiKey.length < 30) {
    showStatus('error', '✗', 'YouTube API 키 형식이 올바르지 않습니다.');
    youtubeApiKeyInput.focus();
    return;
  }

  // Validate URL format
  try {
    new URL(inferenceServerUrl);
  } catch (error) {
    showStatus('error', '✗', '추론 서버 URL 형식이 올바르지 않습니다.');
    inferenceServerUrlInput.focus();
    return;
  }

  // Disable form while saving
  setFormDisabled(true);

  try {
    await chrome.storage.local.set({
      youtubeApiKey,
      inferenceServerUrl
    });

    showStatus('success', '✓', '설정이 성공적으로 저장되었습니다!');

    // Re-enable form after 1 second
    setTimeout(() => {
      setFormDisabled(false);
    }, 1000);
  } catch (error) {
    console.error('Failed to save settings:', error);
    showStatus('error', '✗', `저장 실패: ${error.message}`);
    setFormDisabled(false);
  }
}

/**
 * Test YouTube API key by making a simple API call
 */
async function handleTestApiKey() {
  const youtubeApiKey = youtubeApiKeyInput.value.trim();

  if (!youtubeApiKey) {
    showStatus('error', '✗', 'API 키를 먼저 입력해주세요.');
    youtubeApiKeyInput.focus();
    return;
  }

  // Disable test button
  testBtn.disabled = true;
  testBtn.textContent = '테스트 중...';
  showStatus('info', '⏳', 'API 키를 테스트하고 있습니다...');

  try {
    // Make a simple API call to test the key (get video info for a known video)
    const testVideoId = 'jNQXAC9IVRw'; // YouTube의 "Me at the zoo" (첫 번째 YouTube 영상)
    const response = await fetch(
      `https://www.googleapis.com/youtube/v3/videos?id=${testVideoId}&part=snippet&key=${youtubeApiKey}`
    );

    const data = await response.json();

    if (response.ok && data.items && data.items.length > 0) {
      showStatus('success', '✓', 'API 키가 정상적으로 작동합니다!');
    } else if (data.error) {
      const errorMessage = data.error.message || '알 수 없는 오류';
      showStatus('error', '✗', `API 키 오류: ${errorMessage}`);

      // Provide helpful error messages
      if (data.error.code === 400) {
        showStatus('error', '✗', 'API 키 형식이 올바르지 않습니다.');
      } else if (data.error.code === 403) {
        showStatus('error', '✗', 'API 키가 유효하지 않거나 YouTube Data API가 활성화되지 않았습니다.');
      }
    } else {
      showStatus('error', '✗', 'API 응답이 예상과 다릅니다.');
    }
  } catch (error) {
    console.error('API test failed:', error);
    showStatus('error', '✗', `API 테스트 실패: ${error.message}`);
  } finally {
    testBtn.disabled = false;
    testBtn.textContent = 'API 키 테스트';
  }
}

/**
 * Show status message
 * @param {string} type - 'success', 'error', or 'info'
 * @param {string} icon - Icon to display
 * @param {string} message - Message text
 */
function showStatus(type, icon, message) {
  statusMessage.className = `status-message ${type}`;
  statusIcon.textContent = icon;
  statusText.textContent = message;

  // Auto-hide after 5 seconds for success/info messages
  if (type === 'success' || type === 'info') {
    setTimeout(() => {
      statusMessage.classList.add('hidden');
    }, 5000);
  }
}

/**
 * Enable/disable form inputs
 * @param {boolean} disabled
 */
function setFormDisabled(disabled) {
  youtubeApiKeyInput.disabled = disabled;
  inferenceServerUrlInput.disabled = disabled;
  testBtn.disabled = disabled;

  const submitBtn = form.querySelector('button[type="submit"]');
  submitBtn.disabled = disabled;
  submitBtn.textContent = disabled ? '저장 중...' : '저장';
}
