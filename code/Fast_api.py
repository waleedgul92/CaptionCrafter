from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List
import chardet
from fastapi.responses import FileResponse

import logging
import uvicorn
import os
import tempfile
import glob
import atexit
import asyncio
from pathlib import Path

# Assuming these are in your project structure
from transcribe import extract_audio, transcribe_audio_to_text, save_transcription_to_txt, save_translated_text
from model import load_gemini_model
llm = load_gemini_model() # Make sure 'model.py' exists and load_gemini_model works
from translate import translate_text # Make sure 'translate.py' exists and translate_text works

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic BaseModels for request/response validation
class AudioExtractionResponse(BaseModel):
    extracted_audio_path: str = Field(..., description="The file path where the extracted audio is saved on the server.")
    message: str = Field("Audio extracted successfully", description="A confirmation message for successful audio extraction.")

class TranscriptionRequest(BaseModel):
    language: str = Field(default="ja", description="The language code (e.g., 'en', 'ja', 'de') for the audio to be transcribed. This helps Whisper select the correct language model.")
    model_size: str = Field(default="tiny", description="The size of the Whisper model to use for transcription. Smaller models are faster but less accurate, larger models are slower but more accurate. Options include: 'tiny', 'base', 'small', 'medium'.")
    device: str = Field(default="cpu", description="The computing device to use for transcription. 'cpu' for CPU processing, 'cuda' for NVIDIA GPUs.")
    compute_type: str = Field(default="int8", description="The computation type for the model. 'int8' for integer 8-bit, 'float16' for half-precision floating-point, 'float32' for full-precision floating-point. 'int8' is generally faster but might slightly reduce accuracy.")

class TranscriptionResponse(BaseModel):
    description: str = Field(..., description="A detailed description of the transcription process outcome.")
    transcript_path: str = Field(..., description="The file path where the generated transcript (VTT format) is saved on the server.")
    message: str = Field("Transcription completed successfully", description="A confirmation message for successful transcription.")

class TranslationRequest(BaseModel):
    source_language: str = Field(..., description="The original language of the input text (e.g., 'English', 'Japanese').")
    target_language: str = Field(..., description="The language into which the text should be translated (e.g., 'English', 'German').")

class TranslationResponse(BaseModel):
    description: str = Field(..., description="A detailed description of the translation process outcome.")
    output_file: str = Field(..., description="The file path where the translated subtitle (VTT format) is saved on the server.")
    message: str = Field("Translation completed successfully", description="A confirmation message for successful translation.")

class FileDownloadResponse(BaseModel):
    filename: str = Field(..., description="The name of the file being downloaded.")
    file_path: str = Field(..., description="The server-side path to the file.")
    file_size: int = Field(..., description="The size of the file in bytes.")

class ErrorResponse(BaseModel):
    error: str = Field(..., description="A brief error message indicating the type of error.")
    detail: str = Field(..., description="Detailed information about the error.")
    status_code: int = Field(..., description="The HTTP status code associated with the error.")

class CleanupResponse(BaseModel):
    message: str = Field(..., description="A summary message about the cleanup operation.")
    cleaned_files: List[str] = Field(..., description="A list of file paths that were successfully removed during cleanup.")
    files_count: int = Field(..., description="The total number of files that were attempted to be cleaned up.")

app = FastAPI(
    title="CaptionCrafter API",
    description="""
    This API provides functionality to generate subtitles from video files.
    It integrates Whisper ASR for transcription and a large language model (LLM) for translation.
    Automatic cleanup of intermediate files is handled to manage server storage.
    """,
    version="2.0.0"
)

origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:63342", # Often used by PyCharm's live server
    "null", # For local file testing in some browsers
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

async def add_to_cleanup(file_path: str):
    """Adds a file path to a set of intermediate files to be cleaned up later."""
    if file_path and await asyncio.to_thread(os.path.exists, file_path):
        intermediate_files.add(file_path)
        logger.info(f"Added to cleanup tracking: {file_path}")

async def cleanup_intermediate_files() -> CleanupResponse:
    """
    Cleans up all tracked intermediate files and any other temporary files
    residing in the designated 'files' directory.
    """
    cleaned_files = []
    
    # Clean tracked intermediate files
    for file_path in list(intermediate_files):
        try:
            if await asyncio.to_thread(os.path.exists, file_path):
                await asyncio.to_thread(os.remove, file_path)
                cleaned_files.append(file_path)
                logger.info(f"Cleaned up intermediate file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up {file_path}: {e}")
        finally:
            intermediate_files.discard(file_path)
    
    # Clean up any remaining files in the files directory that match our patterns
    files_dir = Path("../files")
    if await asyncio.to_thread(files_dir.exists):
        patterns = ["audio-*.wav", "transcript_*.vtt", "transcript_translated_*.vtt"] # Include translated files
        for pattern in patterns:
            for file_path in await asyncio.to_thread(files_dir.glob, pattern):
                try:
                    if await asyncio.to_thread(file_path.exists):
                        await asyncio.to_thread(file_path.unlink)
                        cleaned_files.append(str(file_path))
                        logger.info(f"Cleaned up pattern file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up {file_path}: {e}")
    
    return CleanupResponse(
        message=f"Cleanup completed. Removed {len(cleaned_files)} files.",
        cleaned_files=cleaned_files,
        files_count=len(cleaned_files)
    )

async def save_uploaded_file(uploaded_file: UploadFile, file_path: str):
    """Async helper to save uploaded file."""
    with open(file_path, "wb") as f:
        while chunk := await uploaded_file.read(8192):  # Read in chunks to avoid memory issues
            f.write(chunk)
    await uploaded_file.seek(0)  # Reset file pointer for potential reuse

async def read_file_with_encoding_detection(file_path: str) -> str:
    """Async helper to read file with encoding detection."""
    raw_data = await asyncio.to_thread(open(file_path, 'rb').read)
    result = await asyncio.to_thread(chardet.detect, raw_data)
    encoding = result['encoding'] if result['encoding'] else 'utf-8'
    
    def _read_file():
        with open(file_path, "r", encoding=encoding) as f:
            return f.read()
    
    return await asyncio.to_thread(_read_file)

@app.post("/extract_audio", response_model=AudioExtractionResponse, summary="Extract Audio from Video",
          description="Uploads a video file and extracts its audio content, saving it as a WAV file. The path to the extracted audio is returned for subsequent transcription.")
async def extract_audio_endpoint(
    video_file: UploadFile = File(..., description="The video file (e.g., MP4, MKV, TS, MOV) from which to extract audio.")
):
    """
    Endpoint to extract audio from a video file and return the path to the extracted audio.
    """
    global current_audio_filename
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_video_path = os.path.join(temp_dir, video_file.filename)
            
            # Save the uploaded video file to the temporary directory
            await save_uploaded_file(video_file, input_video_path)

            # Extract audio from the video file
            video_name = os.path.splitext(video_file.filename)[0]
            extracted_audio_path = await asyncio.to_thread(extract_audio, input_video_path, video_name)
            
            # Store the audio filename for later use and add to cleanup tracking
            current_audio_filename = os.path.basename(extracted_audio_path)
            await add_to_cleanup(extracted_audio_path)
            
            return AudioExtractionResponse(
                extracted_audio_path=extracted_audio_path,
                message="Audio extracted successfully"
            )
    
    except Exception as e:
        logger.error(f"Error extracting audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transcribe_audio", response_model=TranscriptionResponse, summary="Transcribe Audio to Text",
          description="Transcribes an audio file into text using the specified Whisper ASR model. The resulting transcript is saved as a VTT file.")
async def transcribe_audio_endpoint(
    audio_file: UploadFile = File(..., description="The audio file to be transcribed. This is typically the output from the `/extract_audio` endpoint."),
    language: str = Form("ja", description="The language of the audio content. E.g., 'en' for English, 'ja' for Japanese, 'de' for German."),
    model_size: str = Form("small", description="The size of the Whisper model to use for transcription. Available options: 'tiny', 'base', 'small', 'medium'."),
    device: str = Form("cpu", description="The computing device for transcription. 'cpu' for CPU, 'cuda' for GPU."),
    compute_type: str = Form("int8", description="The precision for computations. 'int8' (integer 8-bit) for faster processing, 'float16' (half-precision) for balanced performance, 'float32' (full-precision) for maximum accuracy.")
):
    """
    Endpoint to transcribe audio to text using Whisper ASR.
    You can select from 'tiny', 'base', 'small', or 'medium' models for transcription.
    """
    global current_transcript_path, current_audio_filename
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_audio_path = os.path.join(temp_dir, audio_file.filename)
            
            # Save the uploaded audio file to the temporary directory
            await save_uploaded_file(audio_file, input_audio_path)

            # Transcribe the audio file, passing the model_size
            segments = await asyncio.to_thread(transcribe_audio_to_text, input_audio_path, language, model_size, device, compute_type)

            # Save transcription with descriptive filename
            current_transcript_path = await asyncio.to_thread(
                save_transcription_to_txt,
                segments, 
                audio_filename=audio_file.filename or current_audio_filename,
                language=language
            )
            
            # Add transcript to cleanup tracking
            await add_to_cleanup(current_transcript_path)
            
            return TranscriptionResponse(
                description="Transcription file saved successfully.",
                transcript_path=current_transcript_path,
                message="Transcription completed successfully"
            )
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/translate_text", response_model=TranslationResponse, summary="Translate Transcript Text",
          description="Translates the content of a VTT transcript file from a source language to a target language using a large language model (LLM). The translated text is saved as a new VTT file.")
async def translate_text_endpoint(
    input_file: UploadFile = File(..., description="The input VTT transcript file to be translated."),
    source_language: str = Form(..., description="The original language of the text in the input file (e.g., 'English', 'Japanese')."),
    target_language: str = Form(..., description="The desired language for the translated output (e.g., 'English', 'German')."),
):
    """
    Endpoint to translate text from source to target language.
    """
    global current_translated_path, current_audio_filename
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file_path = os.path.join(temp_dir, input_file.filename or "uploaded_text_file.vtt")
            
            # Save uploaded file
            await save_uploaded_file(input_file, temp_file_path)

            # Read the file with encoding detection
            text_from_file = await read_file_with_encoding_detection(temp_file_path)

        translated_text, current_translated_path = await asyncio.to_thread(
            translate_text,
            llm, 
            text_from_file, 
            target_language, 
            source_language,
        )
        
        if current_translated_path is None:
            raise HTTPException(status_code=500, detail="Translation failed")

        # Add translated file to cleanup tracking (but don't clean it immediately as user needs to download)
        await add_to_cleanup(current_translated_path)

        return TranslationResponse(
            description="Translation file saved successfully.",
            output_file=current_translated_path,
            message="Translation completed successfully"
        )

    except Exception as e:
        logger.error(f"Error translating text: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download_transcript", summary="Download Original Transcript",
         description="Downloads the most recently generated original transcript file (VTT format) from the server. This file contains the text transcribed from the audio.")
async def download_transcript():
    """
    Endpoint to download the most recent generated transcript file.
    """
    global current_transcript_path
    try:
        # If we have a current transcript path, use it
        if current_transcript_path and await asyncio.to_thread(os.path.exists, current_transcript_path):
            transcript_path = current_transcript_path
        else:
            # Fallback: look for the most recent transcript file
            transcript_files = await asyncio.to_thread(glob.glob, "../files/transcript_*.vtt")
            if not transcript_files:
                raise HTTPException(status_code=404, detail="No transcript file found")
            # Get the most recently created file
            transcript_path = await asyncio.to_thread(max, transcript_files, key=os.path.getctime)
        
        if not await asyncio.to_thread(os.path.exists, transcript_path):
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

@app.get("/download_translated_subtitle", summary="Download Translated Subtitle",
         description="Downloads the most recently generated translated subtitle file (VTT format) from the server. This file contains the translated text.")
async def download_translated_subtitle():
    """
    Endpoint to download the most recent translated subtitle file.
    """
    global current_translated_path
    try:
        # If we have a current translated path, use it
        if current_translated_path and await asyncio.to_thread(os.path.exists, current_translated_path):
            translated_path = current_translated_path
        else:
            # Fallback: look for the most recent translated file
            translated_files = await asyncio.to_thread(glob.glob, "../files/transcript_translated_*.vtt")
            if not translated_files:
                raise HTTPException(status_code=404, detail="No translated subtitle file found. Please complete the translation process first.")
            # Get the most recently created file
            translated_path = await asyncio.to_thread(max, translated_files, key=os.path.getctime)
        
        if not await asyncio.to_thread(os.path.exists, translated_path):
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

@app.post("/cleanup", response_model=CleanupResponse, summary="Clean Up Intermediate Files",
          description="Triggers an immediate cleanup of all intermediate audio and transcript files generated by the API to free up server space.")
async def cleanup_files():
    """
    Endpoint to manually trigger cleanup of intermediate files.
    """
    try:
        result = await cleanup_intermediate_files()
        logger.info(f"Manual cleanup completed: {result.message}")
        return result
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

@app.get("/health", summary="API Health Check",
         description="Provides a status check for the API, indicating if it's running, if the LLM is loaded, and the count of intermediate files being tracked.")
async def health_check():
    """
    Health check endpoint to verify API status.
    """
    return {
        "status": "healthy",
        "message": "CaptionCrafter API is running",
        "llm_loaded": llm is not None,
        "intermediate_files_count": len(intermediate_files)
    }

@app.get("/files/status", summary="Get Server File Status",
         description="Retrieves information about files currently managed by the API, including current audio, transcript, translated file paths, and a list of all existing files in the temporary directory along with their cleanup status.")
async def files_status():
    """
    Get status of current files and cleanup tracking.
    """
    files_dir = Path("../files")
    existing_files = []
    
    if await asyncio.to_thread(files_dir.exists):
        async def process_file(file_path):
            if await asyncio.to_thread(file_path.is_file):
                stat_result = await asyncio.to_thread(file_path.stat)
                return {
                    "name": file_path.name,
                    "path": str(file_path),
                    "size": stat_result.st_size,
                    "tracked_for_cleanup": str(file_path) in intermediate_files
                }
            return None
        
        # Process files concurrently
        tasks = []
        for file_path in await asyncio.to_thread(files_dir.iterdir):
            tasks.append(process_file(file_path))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        existing_files = [result for result in results if result is not None and not isinstance(result, Exception)]
    
    return {
        "current_audio_filename": current_audio_filename,
        "current_transcript_path": current_transcript_path,
        "current_translated_path": current_translated_path,
        "tracked_intermediate_files": list(intermediate_files),
        "existing_files": existing_files,
        "files_directory": str(files_dir)
    }

@app.on_event("shutdown")
async def shutdown_event():
    """
    Cleanup intermediate files when the application shuts down.
    """
    logger.info("Application shutting down, cleaning up intermediate files...")
    try:
        result = await cleanup_intermediate_files()
        logger.info(f"Shutdown cleanup completed: {result.message}")
    except Exception as e:
        logger.error(f"Error during shutdown cleanup: {e}")

# Also register cleanup for when the process exits (for cases where FastAPI might not cleanly shut down)
atexit.register(lambda: asyncio.run(cleanup_intermediate_files()))

if __name__ == "__main__":
    # Run the FastAPI app with Uvicorn
    uvicorn.run(app, host="localhost", port=8000, log_level="info")