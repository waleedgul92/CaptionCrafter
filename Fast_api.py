from fastapi import FastAPI, HTTPException  ,UploadFile, File
from fastapi.middleware.cors import CORSMiddleware # To allow requests from your UI
from pydantic import BaseModel, HttpUrl , Field # For request/response validation
# from fastapi import FastAPI, HTTPException
from typing import List, Dict, Any, Optional

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
def transcribe_audio_endpoint(
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
def translate_text_endpoint(
    input_file: UploadFile = File(...),
    source_language: str = "japanese",
    target_language: str = "english",
    
):
    """
    Endpoint to translate text using a language model.
    """
    try:
        text_from_file = ""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Use a more descriptive name for the path of the saved text file
            temp_file_path = os.path.join(temp_dir, input_file.filename if input_file.filename else "uploaded_text_file.txt")
            
            # Save the uploaded file to the temporary path
            # input_file.file is a file-like object (SpooledTemporaryFile)
            with open(temp_file_path, "wb") as f_write: # Open in binary write mode
                shutil.copyfileobj(input_file.file, f_write) # Copy content
            
            # Now read the text from the temporary file we just saved
            with open(temp_file_path, "r", encoding="utf-8") as f_read: # Open in text read mode
                text_from_file = f_read.read()
        translated_text = translate_text(llm,text_from_file, target_language, source_language)
        save_translated_text(translated_text)
        # if os.path.exists(input_file):
        #     os.remove(input_file)
        return {"description": "Translation file saved successfully."}
    except Exception as e:
        logger.error(f"Error translating text: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    

