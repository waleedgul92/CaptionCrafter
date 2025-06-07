let selectedFile = null;
let translationCompleted = false; // Track if translation is completed

const fileInput = document.getElementById('videoUpload');
const generateBtn = document.getElementById('generateBtn');
const fileNameDisplay = document.getElementById('fileName');
const statusDisplay = document.getElementById('status');
const sourceLangSelect = document.getElementById('sourceLang');
const targetLangSelect = document.getElementById('targetLang');
const downloadBtn = document.getElementById('downloadBtn');

const API_BASE_URL = 'http://localhost:8000';

const languageCodeMap = {
  "english": "en",
  "hindi": "hi",
  "german": "de",
  "chinese": "zh",
  "korean": "ko",
  "japanese": "ja"
};

if (!fileInput) console.error("Error: Element with ID 'videoUpload' not found.");
if (!generateBtn) console.error("Error: Element with ID 'generateBtn' not found.");
if (!fileNameDisplay) console.error("Error: Element with ID 'fileName' not found.");
if (!statusDisplay) console.error("Error: Element with ID 'status' not found.");
if (!sourceLangSelect) console.error("Error: Element with ID 'sourceLang' not found.");
if (!targetLangSelect) console.error("Error: Element with ID 'targetLang' not found.");
if (!downloadBtn) console.error("Error: Element with ID 'downloadBtn' not found.");

if (fileInput) {
  fileInput.addEventListener('change', () => {
    const file = fileInput.files[0];
    if (file) {
      const allowedTypes = ['video/mp4', 'video/x-matroska', 'video/MP2T', 'video/quicktime'];
      const allowedExtensions = ['.mp4', '.mkv', '.ts', '.mov'];
      const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();

      if (!allowedTypes.includes(file.type) && !allowedExtensions.includes(fileExtension)) {
        updateStatus(`❌ Invalid file type (${file.type || fileExtension}). Please upload a .mp4, .mkv, .ts, or .mov file.`, 'error');
        selectedFile = null;
        fileNameDisplay.textContent = 'No video selected';
        fileInput.value = '';
        disableDownloadButton();
        return;
      }

      selectedFile = file;
      fileNameDisplay.textContent = `Selected: ${file.name}`;
      updateStatus(`✅ Selected: ${file.name}`, 'success');
      disableDownloadButton(); // Reset download button when new file is selected
      translationCompleted = false;
    } else {
      selectedFile = null;
      fileNameDisplay.textContent = 'No video selected';
      updateStatus('');
      disableDownloadButton();
      translationCompleted = false;
    }
  });
}

if (generateBtn) {
  generateBtn.addEventListener('click', async () => {
    if (!selectedFile) {
      updateStatus('❌ Please select a video file first.', 'error');
      return;
    }
    
    const selectedSourceLangValue = sourceLangSelect.value;
    if (!selectedSourceLangValue) {
        updateStatus('❌ Please select a source language.', 'error');
        return;
    }

    const selectedTargetLangValue = targetLangSelect.value;
    if (!selectedTargetLangValue) {
        updateStatus('❌ Please select a target language for translation.', 'error');
        return;
    }

    const languageCodeForTranscription = languageCodeMap[selectedSourceLangValue.toLowerCase()];
    if (!languageCodeForTranscription) {
        updateStatus(`❌ Transcription language code not found for "${selectedSourceLangValue}".`, 'error');
        return;
    }

    const sourceLangForTranslation = sourceLangSelect.options[sourceLangSelect.selectedIndex].text;
    const targetLangForTranslation = targetLangSelect.options[targetLangSelect.selectedIndex].text;

    updateStatus('⏳ Step 1: Uploading and extracting audio...', 'info');
    generateBtn.disabled = true;
    disableDownloadButton();
    translationCompleted = false;

    const formDataExtract = new FormData();
    formDataExtract.append('video_file', selectedFile);

    try {
      // --- Step 1: Extract Audio ---
      const extractResponse = await fetch(`${API_BASE_URL}/extract_audio`, {
        method: 'POST',
        body: formDataExtract
      });
      if (!extractResponse.ok) {
        const errData = await extractResponse.json().catch(() => ({ detail: "Audio extraction failed. Status: " + extractResponse.status }));
        throw new Error(errData.detail || "Audio extraction failed. Status: " + extractResponse.status);
      }
      const extractData = await extractResponse.json();
      updateStatus('✅ Step 1: Audio extracted. Server path: ' + extractData.extracted_audio_path, 'success');
      console.log("Extracted audio path on server:", extractData.extracted_audio_path);

      // --- Step 2: Transcribe Audio ---
      updateStatus('⏳ Step 2: Transcribing audio (generates transcript.vtt on server)...', 'info');
      const formDataTranscribe = new FormData();
      formDataTranscribe.append('audio_file', selectedFile);
      formDataTranscribe.append('language', languageCodeForTranscription);
      
      const transcribeResponse = await fetch(`${API_BASE_URL}/transcribe_audio`, {
        method: 'POST',
        body: formDataTranscribe
      });
      if (!transcribeResponse.ok) {
        const errData = await transcribeResponse.json().catch(() => ({ detail: "Transcription failed. Status: " + transcribeResponse.status }));
        throw new Error(errData.detail || "Transcription failed. Status: " + transcribeResponse.status);
      }
      const transcribeData = await transcribeResponse.json();
      updateStatus('✅ Step 2: Transcription successful. Server: ' + transcribeData.description, 'success');

      // --- Step 3: Translate Transcript ---
      updateStatus('⏳ Step 3: Fetching transcript and translating...', 'info');

      // First, fetch the transcript file from the server
      const transcriptResponse = await fetch(`${API_BASE_URL}/download_transcript`, {
        method: 'GET'
      });

      if (!transcriptResponse.ok) {
        throw new Error(`Failed to fetch transcript file. Status: ${transcriptResponse.status}`);
      }

      // Convert the response to a Blob, then to a File
      const transcriptBlob = await transcriptResponse.blob();
      const transcriptFile = new File([transcriptBlob], 'transcript.vtt', { 
        type: 'text/vtt' 
      });

      console.log("Transcript file to translate:", transcriptFile);

      const formDataTranslate = new FormData();
      formDataTranslate.append('input_file', transcriptFile);
      formDataTranslate.append('source_language', sourceLangForTranslation);  
      formDataTranslate.append('target_language', targetLangForTranslation);

      const translateResponse = await fetch(`${API_BASE_URL}/translate_text`, {
        method: 'POST',
        body: formDataTranslate
      });

      if (!translateResponse.ok) {
        const errData = await translateResponse.json().catch(() => ({ detail: "Translation failed. Status: " + translateResponse.status }));
        throw new Error(errData.detail || "Translation failed. Status: " + translateResponse.status);
      }

      const translateData = await translateResponse.json();
      updateStatus('✅ Step 3: Translation successful! Ready to download translated subtitles.', 'success');
      console.log("Translation completed:", translateData);

      // Enable download button after successful translation
      translationCompleted = true;
      enableDownloadButton();

    } catch (error) {
      if (error.response) {
        const errData = await error.response.json();
        updateStatus(`❌ Error: ${errData.detail || JSON.stringify(errData)}`, 'error');
      } else {
        updateStatus(`❌ Error: ${error.message || JSON.stringify(error)}`, 'error');
      }
      disableDownloadButton();
      translationCompleted = false;
    } finally {
      generateBtn.disabled = false;
    }
  });
}

// Download button functionality
if (downloadBtn) {
  downloadBtn.addEventListener('click', async () => {
    if (!translationCompleted || downloadBtn.disabled) {
      updateStatus('❌ Please complete the translation process first.', 'error');
      return;
    }

    try {
      updateStatus('⏳ Downloading translated subtitles...', 'info');
      
      // Fetch the translated subtitle file
      const downloadResponse = await fetch(`${API_BASE_URL}/download_translated_subtitle`, {
        method: 'GET'
      });

      if (!downloadResponse.ok) {
        throw new Error(`Download failed. Status: ${downloadResponse.status}`);
      }

      // Get the file as a blob
      const fileBlob = await downloadResponse.blob();
      
      // Create download link
      const downloadUrl = window.URL.createObjectURL(fileBlob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = 'transcript_translated.vtt';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      
      // Clean up the object URL
      window.URL.revokeObjectURL(downloadUrl);
      
      updateStatus('✅ Translated subtitles downloaded successfully!', 'success');
      
    } catch (error) {
      updateStatus(`❌ Download failed: ${error.message}`, 'error');
      console.error('Download error:', error);
    }
  });
}

function updateStatus(message, type = 'info') {
  if (statusDisplay) {
    statusDisplay.textContent = message;
    statusDisplay.className = `status-message ${type}`;
  } else {
    console.log(`Status: [${type}] ${message}`);
  }
}

function enableDownloadButton() {
  if (downloadBtn) {
    downloadBtn.disabled = false;
    downloadBtn.classList.add('active');
    downloadBtn.textContent = '📥 Download Translated Subtitles';
    // Remove any inline styles to let CSS classes take over
    downloadBtn.style.backgroundColor = '';
    downloadBtn.style.color = '';
    downloadBtn.style.opacity = '';
    downloadBtn.style.cursor = '';
  }
}

function disableDownloadButton() {
  if (downloadBtn) {
    downloadBtn.disabled = true;
    downloadBtn.classList.remove('active');
    downloadBtn.textContent = 'Download Subtitle';
    // Let CSS handle the disabled styling
  }
}