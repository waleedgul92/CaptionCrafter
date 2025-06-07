from fastapi import FastAPI, HTTPException  ,UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware # To allow requests from your UI
from pydantic import BaseModel, HttpUrl , Field # For request/response validation
# from fastapi import FastAPI, HTTPException
from typing import List, Dict, Any, Optional 
import chardet
from fastapi.responses import FileResponse

import logging
import uvicorn
import shutil
import os
import tempfile 

from transcribe import extract_audio , transcribe_audio_to_text , save_transcription_to_txt , save_translated_text
from model import load_gemini_model
llm = load_gemini_model()
from translate import translate_text


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Subtitle Generator API",
    description="API for generating subtitles from video files using Whisper ASR.",
)
origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:63342", # Common port for PyCharm/WebStorm local server
    "null", 
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],

)


@app.post("/extract_audio")
async def extract_audio_endpoint(video_file: UploadFile = File(...)):
    """
    Endpoint to extract audio from a video file and return the path to the extracted audio.
    """
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_video_path = os.path.join(temp_dir, video_file.filename)
            
            # Save the uploaded video file to the temporary directory
            with open(input_video_path, "wb") as f:
                shutil.copyfileobj(video_file.file, f)

            # Extract audio from the video file
            extracted_audio_path = extract_audio(input_video_path, os.path.splitext(video_file.filename)[0])
            
            return {"extracted_audio_path": extracted_audio_path}
    
    except Exception as e:
        logger.error(f"Error extracting audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/transcribe_audio")
async def transcribe_audio_endpoint(
    audio_file: UploadFile = File(...),
    language: str = "ja",
    model_size: str = "tiny",
    device: str = "cpu",
    compute_type: str = "int8",
):
    """
    Endpoint to transcribe audio to text using Whisper ASR.
    """
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_audio_path = os.path.join(temp_dir, audio_file.filename)
            
            # Save the uploaded audio file to the temporary directory
            with open(input_audio_path, "wb") as f:
                shutil.copyfileobj(audio_file.file, f)

            # Transcribe the audio file
            segments = transcribe_audio_to_text(input_audio_path, language, model_size, device, compute_type)

            save_transcription_to_txt(segments)
            # if os.path.exists(input_audio_path):
            #     os.remove(input_audio_path)
            return {"description": "Transcription file saved successfully."}
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/translate_text")
async def translate_text_endpoint(
    input_file: UploadFile = File(...),
    source_language: str = Form(...),
    target_language: str = Form(...),
):
    try:
        text_from_file = ""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file_path = os.path.join(temp_dir, input_file.filename or "uploaded_text_file.vtt")
            
            # Save uploaded file
            with open(temp_file_path, "wb") as f_write:
                shutil.copyfileobj(input_file.file, f_write)

            # Detect encoding

            with open(temp_file_path, "r", encoding="utf-8") as f_read:
                text_from_file = f_read.read()
        translated_text = translate_text(llm, text_from_file, target_language, source_language)
        output_path=save_translated_text(translated_text)

        return {"description": "Translation file saved successfully.","output_file": output_path}

    except Exception as e:
        logger.error(f"Error translating text: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/download_transcript")
async def download_transcript():
    """
    Endpoint to download the generated transcript file.
    """
    try:
        # Assuming your transcript is saved as 'transcript.vtt' in the current directory
        # Adjust the path according to where your save_transcription_to_txt function saves the file
        transcript_path = "../files/transcription.vtt"  # Update this path as needed
        
        if not os.path.exists(transcript_path):
            raise HTTPException(status_code=404, detail="Transcript file not found")
        
        return FileResponse(
            path=transcript_path,
            filename="transcript.vtt",
            media_type="text/vtt"
        )
    
    except Exception as e:
        logger.error(f"Error downloading transcript: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    

@app.get("/download_transcript")
async def download_transcript():
    """
    Endpoint to download the generated transcript file (original, not translated).
    """
    try:
        # Assuming your transcript is saved as 'transcript.vtt' in the current directory
        # Adjust the path according to where your save_transcription_to_txt function saves the file
        transcript_path = "../files/transcription.vtt"  # Update this path as needed
        
        if not os.path.exists(transcript_path):
            raise HTTPException(status_code=404, detail="Transcript file not found")
        
        return FileResponse(
            path=transcript_path,
            filename="transcript.vtt",
            media_type="text/vtt"
        )
    
    except Exception as e:
        logger.error(f"Error downloading transcript: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download_translated_subtitle")
async def download_translated_subtitle():
    """
    Endpoint to download the translated subtitle file.
    """
    try:
        # Path to the translated subtitle file
        translated_subtitle_path = "../files/transcription_translated.vtt"  # Update this path as needed
        
        if not os.path.exists(translated_subtitle_path):
            raise HTTPException(status_code=404, detail="Translated subtitle file not found. Please complete the translation process first.")
        
        return FileResponse(
            path=translated_subtitle_path,
            filename="transcript_translated.vtt",
            media_type="text/vtt"
        )
    
    except Exception as e:
        logger.error(f"Error downloading translated subtitle: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Run the FastAPI app with Uvicorn
    uvicorn.run(app, host="localhost", port=8000, log_level="info")