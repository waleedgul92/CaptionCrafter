import os
import argparse
import speech_recognition as sr
from pydub import AudioSegment

import os
import argparse
from moviepy import VideoFileClip
from faster_whisper import WhisperModel
from pydub import AudioSegment
import speech_recognition as sr
from io import BytesIO
from faster_whisper import WhisperModel
import logging
logger= logging.getLogger(__name__)

def extract_audio(input_video, input_video_name):
    output_directory = "../files"
    os.makedirs(output_directory, exist_ok=True)
    extracted_audio_path = f"../files/audio-{input_video_name}.wav"

    logger.info(f"Extracting audio from video: {input_video} to {extracted_audio_path}")
    if not os.path.exists(input_video):
        logger.error(f"The video file '{input_video}' was not found.")
        raise FileNotFoundError(f"The video file '{input_video}' was not found.")
    
    try:
        logger.info("Starting audio extraction...")
        video_clip = VideoFileClip(input_video)
        audio_clip = video_clip.audio
        audio_clip.write_audiofile(extracted_audio_path)
        audio_clip.close()  
        video_clip.close() 
        logger.info(f"Audio extracted successfully to {extracted_audio_path}") 
    except Exception as e:
        logger.error(f"Error extracting audio: {e}")
        print(f"Error extracting audio: {e}")
        raise

    return extracted_audio_path



def transcribe_audio_to_text(audio_file , language="ja",model_size="tiny",device="cpu",compute_type="int8"): 
    
    model_size = model_size
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments, info = model.transcribe(
        audio_file,
        language = language  , # Specify the language code for Hindi
        beam_size=5,
        vad_filter=True,
        task="transcribe", 
        vad_parameters={"threshold": 0.5, "min_silence_duration_ms": 1000, }  ,# 1 sec silence
        
    )
    ## sgement => start , end , text
    ## info => language, duration, num_segments, etc.

    return segments



def format_timestamp(seconds):
    logger.info(f"Formatting timestamp for {seconds} seconds")
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    logger.info(f"Formatted timestamp: {hours:02}:{minutes:02}:{secs:02}.{millis:03}")
    return f"{hours:02}:{minutes:02}:{secs:02}.{millis:03}"

def save_transcription_to_txt(segments, audio_filename=None, language="unknown"):
    """
    Save transcription with descriptive filename: transcript_audiofilename_language.vtt
    """
    logger.info("Saving transcription to VTT file")
    output_directory = "../files"
    os.makedirs(output_directory, exist_ok=True)
    
    # Create descriptive filename
    if audio_filename:
        # Remove file extension and "audio-" prefix if present
        clean_name = audio_filename.replace("audio-", "").split('.')[0]
        output_filename = f"transcript_{clean_name}_{language}.vtt"
    else:
        output_filename = f"transcript_unknown_{language}.vtt"
    
    output_txt_file = os.path.join(output_directory, output_filename)
    
    with open(output_txt_file, 'w', encoding='utf-8') as f:
        f.write("WEBVTT\n\n")
        logger.info(f"Transcription file created at {output_txt_file}")
        for i, segment in enumerate(segments, 1):
            start_time = format_timestamp(segment.start)
            end_time = format_timestamp(segment.end)
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{segment.text}\n\n")
            logger.info(f"Segment {i}: {start_time} --> {end_time} | {segment.text}")

    return output_txt_file


def save_translated_text(text, audio_filename=None, source_language="unknown", target_language="unknown"):
    """
    Save translated text with descriptive filename: transcript_translated_audiofilename_sourcelang_targetlang.vtt
    """
    output_directory = "../files"
    os.makedirs(output_directory, exist_ok=True)
    logger.info("Saving translated text to VTT file")
    
    # Create descriptive filename
    if audio_filename:
        # Remove file extension and "audio-" prefix if present
        clean_name = audio_filename.replace("audio-", "").split('.')[0]
        output_filename = f"transcript_translated_{clean_name}_{source_language}_{target_language}.vtt"
    else:
        output_filename = f"transcript_translated_unknown_{source_language}_{target_language}.vtt"
    
    output_txt_file = os.path.join(output_directory, output_filename)
    
    with open(output_txt_file, 'w', encoding='utf-8') as f:
        f.write(text + "\n")
        logger.info(f"Translated text file created at {output_txt_file}")
    
    return output_txt_file

# print(transcribe_audio_to_text("./files/audio-Episode_8.wav"))