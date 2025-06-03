document.addEventListener('DOMContentLoaded', () => {
    const videoUpload = document.getElementById("videoUpload");
    const fileNameSpan = document.getElementById("fileName");
    const generateBtn = document.getElementById("generateBtn");
    const downloadBtn = document.getElementById("downloadBtn");
    const sourceLangSelect = document.getElementById("sourceLang");
    const targetLangSelect = document.getElementById("targetLang");

    const API_BASE_URL = "http://localhost:8000";
    const SERVER_TRANSCRIPTION_FILENAME = "transcription.txt";
    const SERVER_TRANSLATED_FILENAME = "translated_text.txt";

    const languageMap = {
        "english": "en",
        "hindi": "hi",
        "german": "de",
        "chinese": "zh",
        "korean": "ko",
        "japanese": "ja"
    };

    let currentDownloadableFilename = "";

    if (videoUpload) {
        videoUpload.addEventListener("change", (event) => {
            const file = event.target.files[0];
            if (fileNameSpan) {
                fileNameSpan.textContent = file ? file.name : "No video selected";
            }
            if (file && downloadBtn) {
                downloadBtn.disabled = true;
                downloadBtn.classList.remove("active");
                currentDownloadableFilename = "";
            }
        });
    }

    if (generateBtn) {
        generateBtn.addEventListener("click", async () => {
            if (!videoUpload || videoUpload.files.length === 0) {
                alert("Please upload a video file.");
                return;
            }
            const videoFile = videoUpload.files[0];

            if (!sourceLangSelect || !targetLangSelect) {
                alert("Language select elements not found.");
                return;
            }
            const sourceLangValue = sourceLangSelect.value;
            const targetLangValue = targetLangSelect.value;

            if (!sourceLangValue || !targetLangValue) {
                alert("Please select both source and target languages.");
                return;
            }

            if (sourceLangValue === targetLangValue) {
                alert("Source and target language cannot be the same.");
                return;
            }

            const sourceLangCode = languageMap[sourceLangValue.toLowerCase()];
            const targetLangCode = languageMap[targetLangValue.toLowerCase()];

            if (!sourceLangCode || !targetLangCode) {
                alert("Invalid language selection or mapping not found.");
                return;
            }

            generateBtn.textContent = "Generating (1/2)...";
            generateBtn.disabled = true;
            if (downloadBtn) {
                downloadBtn.disabled = true;
                downloadBtn.classList.remove("active");
            }

            try {
                const transcribeFormData = new FormData();
                transcribeFormData.append("audio_file", videoFile);
                transcribeFormData.append("language", sourceLangCode);

                const transcribeResponse = await fetch(`${API_BASE_URL}/transcribe_audio`, {
                    method: "POST",
                    body: transcribeFormData,
                });

                if (!transcribeResponse.ok) {
                    const errorData = await transcribeResponse.json().catch(() => null);
                    const detail = errorData?.detail || `Transcription failed: ${transcribeResponse.statusText}`;
                    throw new Error(detail);
                }
                await transcribeResponse.json();


                generateBtn.textContent = "Generating (2/2)...";

                const translateFormData = new FormData();
                translateFormData.append("input_path", SERVER_TRANSCRIPTION_FILENAME);
                translateFormData.append("source_language", sourceLangCode);
                translateFormData.append("target_language", targetLangCode);

                const translateResponse = await fetch(`${API_BASE_URL}/translate_text`, {
                    method: "POST",
                    body: translateFormData,
                });

                if (!translateResponse.ok) {
                    const errorData = await translateResponse.json().catch(() => null);
                    const detail = errorData?.detail || `Translation failed: ${translateResponse.statusText}`;
                    throw new Error(detail);
                }
                await translateResponse.json();

                currentDownloadableFilename = SERVER_TRANSLATED_FILENAME;
                if (downloadBtn) {
                    downloadBtn.disabled = false;
                    downloadBtn.classList.add("active");
                }
                alert("Subtitles generated successfully! Ready for download.");

            } catch (error) {
                alert(`Error: ${error.message}`);
            } finally {
                generateBtn.textContent = "Generate Subtitle";
                generateBtn.disabled = false;
            }
        });
    }

    if (downloadBtn) {
        downloadBtn.addEventListener("click", () => {
            if (!currentDownloadableFilename) {
                alert("No subtitle file is ready for download or filename is missing.");
                return;
            }
            const downloadUrl = `${API_BASE_URL}/download/${currentDownloadableFilename}`;
            
            const anchor = document.createElement('a');
            anchor.href = downloadUrl;
            anchor.download = currentDownloadableFilename;
            document.body.appendChild(anchor);
            anchor.click();
            document.body.removeChild(anchor);
        });
    }
});