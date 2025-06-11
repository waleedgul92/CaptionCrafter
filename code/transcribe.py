import os
import argparse
import speech_recognition as sr
from pydub import AudioSegment
import re
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



def transcribe_audio_to_text(audio_file , language="ja",model_size="small",device="cpu",compute_type="int8"): 
    
    model_size = model_size
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments, info = model.transcribe(
        audio_file,
        language = language  , # Specify the language code for Hindi
        beam_size=5,
        vad_filter=True,
        task="transcribe", 
        vad_parameters={"threshold": 0.5, "min_silence_duration_ms": 1000}  ,# .5 sec silence
        
    )
    ## sgement => start , end , text
    ## info => language, duration, num_segments, etc.
    for segment in segments:
        print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")

    return segments



def format_timestamp(seconds):
    logger.info(f"Formatting timestamp for {seconds} seconds")
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    logger.info(f"Formatted timestamp: {hours:02}:{minutes:02}:{secs:02}.{millis:03}")
    return f"{hours:02}:{minutes:02}:{secs:02}.{millis:03}"

def save_transcription_to_txt(segments, audio_filename=None, language="unknown",max_chars_per_subtitle=150):
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
    
    with open(output_txt_file, 'w', encoding='utf-8', buffering=8192) as f:
            f.write("WEBVTT\n\n")
            logger.info(f"Transcription file created at {output_txt_file}")
            
            segment_count = 0
            for segment in segments:
                    # Split long segments into manageable chunks
                    segment_chunks = split_long_segment(segment, max_chars=max_chars_per_subtitle)
                    
                    for chunk in segment_chunks:
                        segment_count += 1
                        start_time = format_timestamp(chunk.start)
                        end_time = format_timestamp(chunk.end)
                        
                        # Clean and validate text
                        text = chunk.text.strip()
                        if not text:
                            continue
                            
                        # Write subtitle entry
                        f.write(f"{start_time} --> {end_time}\n")
                        f.write(f"{text}\n\n")
                        
                        # Log every 50 segments to avoid spam
                        if segment_count % 50 == 0:
                            logger.info(f"Processed {segment_count} segments...")


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
        output_filename = f"translated_transcript_{clean_name}_{source_language}_{target_language}.vtt"
    else:
        output_filename = f"translated_transcript_unknown_{source_language}_{target_language}.vtt"
    
    output_txt_file = os.path.join(output_directory, output_filename)
    
    with open(output_txt_file, 'w', encoding='utf-8') as f:
        f.write(text + "\n")
        logger.info(f"Translated text file created at {output_txt_file}")
    
    return output_txt_file

# print(transcribe_audio_to_text("./files/audio-Episode_8.wav"))



def split_long_segment(segment, max_chars=150, max_duration=8.0):
    """
    Split long segments into smaller chunks based on character count and duration
    """
    text = segment.text.strip()
    duration = segment.end - segment.start
    
    # If segment is within limits, return as is
    if len(text) <= max_chars and duration <= max_duration:
        return [segment]
    
    # Split by natural sentence boundaries first
    sentences = re.split(r'[.!?。！？]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if len(sentences) <= 1:
        # If no sentence boundaries, split by clauses or commas
        clauses = re.split(r'[,，、;；]+', text)
        clauses = [c.strip() for c in clauses if c.strip()]
        sentences = clauses if len(clauses) > 1 else [text]
    
    # Create new segments with estimated timestamps
    new_segments = []
    chars_per_second = len(text) / duration if duration > 0 else 1
    current_time = segment.start
    
    for i, sentence in enumerate(sentences):
        if not sentence:
            continue
            
        # Estimate duration for this sentence
        sentence_duration = len(sentence) / chars_per_second
        sentence_end = min(current_time + sentence_duration, segment.end)
        
        # Create a new segment-like object
        class SegmentChunk:
            def __init__(self, start, end, text):
                self.start = start
                self.end = end
                self.text = text
        
        new_segments.append(SegmentChunk(current_time, sentence_end, sentence))
        current_time = sentence_end
    
    return new_segments


# segments= transcribe_audio_to_text("../tests/chinese/video 2/audio-Episode 4.wav", language="zh", model_size="small", device="cpu")
# print(segments)