from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union
import chardet
from fastapi.responses import FileResponse

import logging
import uvicorn
import shutil
import os
import tempfile
import glob
import atexit
from pathlib import Path

from transcribe import extract_audio, transcribe_audio_to_text, save_transcription_to_txt, save_translated_text
from model import load_gemini_model
llm = load_gemini_model()
from translate import translate_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic BaseModels for request/response validation
class AudioExtractionResponse(BaseModel):
    extracted_audio_path: str
    message: str = "Audio extracted successfully"

class TranscriptionRequest(BaseModel):
    language: str = Field(default="ja", description="Language code for transcription")
    model_size: str = Field(default="tiny", description="Whisper model size")
    device: str = Field(default="cpu", description="Device to use for processing")
    compute_type: str = Field(default="int8", description="Compute type for processing")

class TranscriptionResponse(BaseModel):
    description: str
    transcript_path: str
    message: str = "Transcription completed successfully"

class TranslationRequest(BaseModel):
    source_language: str = Field(..., description="Source language for translation")
    target_language: str = Field(..., description="Target language for translation")

class TranslationResponse(BaseModel):
    description: str
    output_file: str
    message: str = "Translation completed successfully"

class FileDownloadResponse(BaseModel):
    filename: str
    file_path: str
    file_size: int

class ErrorResponse(BaseModel):
    error: str
    detail: str
    status_code: int

class CleanupResponse(BaseModel):
    message: str
    cleaned_files: List[str]
    files_count: int

app = FastAPI(
    title="Subtitle Generator API",
    description="API for generating subtitles from video files using Whisper ASR with automatic cleanup.",
    version="2.0.0"
)

origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:63342",
    "null",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables to store current file information and cleanup tracking
current_audio_filename = None
current_transcript_path = None
current_translated_path = None
intermediate_files = set()  # Track all intermediate files for cleanup

def add_to_cleanup(file_path: str):
    """Add a file to the cleanup tracking set"""
    if file_path and os.path.exists(file_path):
        intermediate_files.add(file_path)
        logger.info(f"Added to cleanup tracking: {file_path}")

def cleanup_intermediate_files() -> CleanupResponse:
    """Clean up all tracked intermediate files"""
    cleaned_files = []
    
    # Clean tracked intermediate files
    for file_path in list(intermediate_files):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                cleaned_files.append(file_path)
                logger.info(f"Cleaned up intermediate file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up {file_path}: {e}")
        finally:
            intermediate_files.discard(file_path)
    
    # Clean up any remaining files in the files directory that match our patterns
    files_dir = Path("../files")
    if files_dir.exists():
        patterns = ["audio-*.wav", "transcript_*.vtt"]
        for pattern in patterns:
            for file_path in files_dir.glob(pattern):
                try:
                    if file_path.exists():
                        file_path.unlink()
                        cleaned_files.append(str(file_path))
                        logger.info(f"Cleaned up pattern file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up {file_path}: {e}")
    
    return CleanupResponse(
        message=f"Cleanup completed. Removed {len(cleaned_files)} files.",
        cleaned_files=cleaned_files,
        files_count=len(cleaned_files)
    )

@app.post("/extract_audio", response_model=AudioExtractionResponse)
async def extract_audio_endpoint(video_file: UploadFile = File(...)):
    """
    Endpoint to extract audio from a video file and return the path to the extracted audio.
    """
    global current_audio_filename
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_video_path = os.path.join(temp_dir, video_file.filename)
            
            # Save the uploaded video file to the temporary directory
            with open(input_video_path, "wb") as f:
                shutil.copyfileobj(video_file.file, f)

            # Extract audio from the video file
            video_name = os.path.splitext(video_file.filename)[0]
            extracted_audio_path = extract_audio(input_video_path, video_name)
            
            # Store the audio filename for later use and add to cleanup tracking
            current_audio_filename = os.path.basename(extracted_audio_path)
            add_to_cleanup(extracted_audio_path)
            
            return AudioExtractionResponse(
                extracted_audio_path=extracted_audio_path,
                message="Audio extracted successfully"
            )
    
    except Exception as e:
        logger.error(f"Error extracting audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transcribe_audio", response_model=TranscriptionResponse)
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
    global current_transcript_path, current_audio_filename
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_audio_path = os.path.join(temp_dir, audio_file.filename)
            
            # Save the uploaded audio file to the temporary directory
            with open(input_audio_path, "wb") as f:
                shutil.copyfileobj(audio_file.file, f)

            # Transcribe the audio file
            segments = transcribe_audio_to_text(input_audio_path, language, model_size, device, compute_type)

            # Save transcription with descriptive filename
            current_transcript_path = save_transcription_to_txt(
                segments, 
                audio_filename=audio_file.filename or current_audio_filename,
                language=language
            )
            
            # Add transcript to cleanup tracking
            add_to_cleanup(current_transcript_path)
            
            return TranscriptionResponse(
                description="Transcription file saved successfully.",
                transcript_path=current_transcript_path,
                message="Transcription completed successfully"
            )
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/translate_text", response_model=TranslationResponse)
async def translate_text_endpoint(
    input_file: UploadFile = File(...),
    source_language: str = Form(...),
    target_language: str = Form(...),
):
    """
    Endpoint to translate text from source to target language.
    """
    global current_translated_path, current_audio_filename
    try:
        text_from_file = ""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file_path = os.path.join(temp_dir, input_file.filename or "uploaded_text_file.vtt")
            
            # Save uploaded file
            with open(temp_file_path, "wb") as f_write:
                shutil.copyfileobj(input_file.file, f_write)

            # Read the file
            with open(temp_file_path, "r", encoding="utf-8") as f_read:
                text_from_file = f_read.read()


        translated_text, current_translated_path = translate_text(
            llm, 
            text_from_file, 
            target_language, 
            source_language,
        )
        
        if current_translated_path is None:
            raise HTTPException(status_code=500, detail="Translation failed")

        # Add translated file to cleanup tracking (but don't clean it immediately as user needs to download)
        # We'll clean it up only on explicit cleanup or app shutdown
        add_to_cleanup(current_translated_path)

        return TranslationResponse(
            description="Translation file saved successfully.",
            output_file=current_translated_path,
            message="Translation completed successfully"
        )

    except Exception as e:
        logger.error(f"Error translating text: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download_transcript")
async def download_transcript():
    """
    Endpoint to download the most recent generated transcript file.
    """
    global current_transcript_path
    try:
        # If we have a current transcript path, use it
        if current_transcript_path and os.path.exists(current_transcript_path):
            transcript_path = current_transcript_path
        else:
            # Fallback: look for the most recent transcript file
            transcript_files = glob.glob("../files/transcript_*.vtt")
            if not transcript_files:
                raise HTTPException(status_code=404, detail="No transcript file found")
            # Get the most recently created file
            transcript_path = max(transcript_files, key=os.path.getctime)
        
        if not os.path.exists(transcript_path):
            raise HTTPException(status_code=404, detail="Transcript file not found")
        
        filename = os.path.basename(transcript_path)
        return FileResponse(
            path=transcript_path,
            filename=filename,
            media_type="text/vtt"
        )
    
    except Exception as e:
        logger.error(f"Error downloading transcript: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download_translated_subtitle")
async def download_translated_subtitle():
    """
    Endpoint to download the most recent translated subtitle file.
    """
    global current_translated_path
    try:
        # If we have a current translated path, use it
        if current_translated_path and os.path.exists(current_translated_path):
            translated_path = current_translated_path
        else:
            # Fallback: look for the most recent translated file
            translated_files = glob.glob("../files/transcript_translated_*.vtt")
            if not translated_files:
                raise HTTPException(status_code=404, detail="No translated subtitle file found. Please complete the translation process first.")
            # Get the most recently created file
            translated_path = max(translated_files, key=os.path.getctime)
        
        if not os.path.exists(translated_path):
            raise HTTPException(status_code=404, detail="Translated subtitle file not found. Please complete the translation process first.")
        
        filename = os.path.basename(translated_path)
        return FileResponse(
            path=translated_path,
            filename=filename,
            media_type="text/vtt"
        )
    
    except Exception as e:
        logger.error(f"Error downloading translated subtitle: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/cleanup", response_model=CleanupResponse)
async def cleanup_files():
    """
    Endpoint to manually trigger cleanup of intermediate files.
    """
    try:
        result = cleanup_intermediate_files()
        logger.info(f"Manual cleanup completed: {result.message}")
        return result
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify API status.
    """
    return {
        "status": "healthy",
        "message": "Subtitle Generator API is running",
        "llm_loaded": llm is not None,
        "intermediate_files_count": len(intermediate_files)
    }

@app.get("/files/status")
async def files_status():
    """
    Get status of current files and cleanup tracking.
    """
    files_dir = Path("../files")
    existing_files = []
    
    if files_dir.exists():
        for file_path in files_dir.iterdir():
            if file_path.is_file():
                existing_files.append({
                    "name": file_path.name,
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "tracked_for_cleanup": str(file_path) in intermediate_files
                })
    
    return {
        "current_audio_filename": current_audio_filename,
        "current_transcript_path": current_transcript_path,
        "current_translated_path": current_translated_path,
        "tracked_intermediate_files": list(intermediate_files),
        "existing_files": existing_files,
        "files_directory": str(files_dir)
    }

# # Register cleanup function to run on app shutdown
# @app.on_event("shutdown")
# async def shutdown_event():
#     """
#     Cleanup intermediate files when the application shuts down.
#     """
#     logger.info("Application shutting down, cleaning up intermediate files...")
#     try:
#         result = cleanup_intermediate_files()
#         logger.info(f"Shutdown cleanup completed: {result.message}")
#     except Exception as e:
#         logger.error(f"Error during shutdown cleanup: {e}")

# # Also register cleanup for when the process exits
# atexit.register(lambda: cleanup_intermediate_files())

if __name__ == "__main__":
    # Run the FastAPI app with Uvicorn
    uvicorn.run(app, host="localhost", port=8000, log_level="info")