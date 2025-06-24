# CaptionCrafter

CaptionCrafter is a web-based tool that automatically generates and translates subtitles for your videos. Simply upload a video, select the source and target languages, and let CaptionCrafter do the rest.

## Features

  - **Video to Subtitle Generation**: Upload a video file and get a subtitle file in return.
  - **Multi-language Support**: Supports various languages for both transcription and translation, including English, German, Chinese, Korean, and Japanese.
  - **Translation**: Translate the generated subtitles into different languages.
  - **Multiple Transcription Models**: Choose from different transcription models like 'tiny', 'base', 'small', and 'medium' for varying levels of accuracy and speed.
  - **Downloadable Subtitles**: Download the generated and translated subtitles in VTT format.

## How to Use

1.  **Upload Video**: Click on the "Upload Video" button to select a video file (.mp4, .mkv, .ts, .mov).
2.  **Select Languages**: Choose the source language of the video and the target language for the subtitles.
3.  **Select Model**: Pick a transcription model from the dropdown.
4.  **Generate Subtitles**: Click the "Generate Subtitle" button.
5.  **Download**: Once the process is complete, the "Download Subtitle" button will become active. Click it to download your translated subtitle file.

## API Endpoints

CaptionCrafter provides the following API endpoints:

  - **`POST /extract_audio`**: Extracts audio from a video file.
  - **`POST /transcribe_audio`**: Transcribes an audio file into text.
  - **`POST /translate_text`**: Translates text from a source language to a target language.
  - **`GET /download_transcript`**: Downloads the generated transcript file.
  - **`GET /download_translated_subtitle`**: Downloads the translated subtitle file.
  - **`POST /cleanup`**: Cleans up intermediate files created during the process.
  - **`GET /health`**: Checks the health status of the API.
  - **`GET /files/status`**: Gets the status of the files on the server.

## Technologies Used

  - **Frontend**: HTML, CSS, JavaScript
  - **Backend**: Python, FastAPI
  - **Transcription**: faster\_whisper
  - **Translation**: Google Gemini
  - **Other Libraries**: moviepy, fastapi , langchain

## Setup

To set up the project locally, follow these steps:

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/waleedgul92/captioncrafter.git
    ```
2.  **Navigate to the project directory**:
    ```bash
    cd captioncrafter
    ```
3.  **Create a `keys.env` file** in the root directory and add your Google API key:
    ```
    GOOGLE_API_KEY="YOUR_API_KEY"
    ```
4.  **Install the required dependencies**.
    ```bash
    pip install -r requirements.txt
    ```
5.  **Run the FastAPI server**:
    ```bash
    uvicorn code.Fast_api:app --reload
    ```
6.  Open the `main.html` file in your browser to use the application.



## Video Demo
