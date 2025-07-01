import os
from moviepy import VideoFileClip
from faster_whisper import WhisperModel
import logging
import re
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



def transcribe_audio_to_text(audio_file , language="ja",model_size="medium",device="cpu",compute_type="int8",max_duration=2.0): 
    
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    
    # Crucially, enable word_timestamps to get precise timing for each word
    segments, info = model.transcribe(
        audio_file,
        language=language,
        beam_size=5,
        word_timestamps=True,
        task="transcribe"
    )

    all_words = []
    for segment in segments:
        # segment.words is a generator of word objects, each with start, end, and word
        all_words.extend(list(segment.words))

    if not all_words:
        return []

    final_segments = []
    current_words = []
    current_start_time = all_words[0].start

    for word in all_words:
        # If adding the current word exceeds max_duration, finalize the previous segment
        if current_words and (word.end - current_start_time > max_duration):
            # Finalize the segment with the words collected so far
            segment_text = "".join(w.word for w in current_words)
            segment_end_time = current_words[-1].end
            final_segments.append({
                "start": current_start_time,
                "end": segment_end_time,
                "text": segment_text
            })
            
            # Start a new segment with the current word
            current_words = [word]
            current_start_time = word.start
        else:
            # Otherwise, add the word to the current segment
            current_words.append(word)

    # Add the final remaining segment after the loop
    if current_words:
        segment_text = "".join(w.word for w in current_words)
        segment_end_time = current_words[-1].end
        final_segments.append({
            "start": current_start_time,
            "end": segment_end_time,
            "text": segment_text
        })
        
    return final_segments



def split_long_segment(segment, max_chars=40, max_duration=5.0):
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


def format_timestamp(seconds):
    logger.debug(f"Formatting timestamp for {seconds} seconds")
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}.{millis:03}"

def save_transcription_to_txt(segments, audio_filename=None, language="unknown", max_chars_per_subtitle=30):
    """
    Enhanced save function with automatic splitting of long segments
    """
    logger.info("Saving transcription to VTT file with long sentence handling")
    output_directory = "../files"
    os.makedirs(output_directory, exist_ok=True)
    
    # Create descriptive filename
    if audio_filename:
        clean_name = audio_filename.replace("audio-", "").split('.')[0]
        output_filename = f"transcript_{clean_name}_{language}.vtt"
    else:
        output_filename = f"transcript_unknown_{language}.vtt"
    
    output_txt_file = os.path.join(output_directory, output_filename)
    
    try:
        with open(output_txt_file, 'w', encoding='utf-8', buffering=8192) as f:
            f.write("WEBVTT\n\n")
            logger.info(f"Transcription file created at {output_txt_file}")
            
            segment_count = 0
            for segment in segments:
                try:
                    # Handle both dictionary and object formats
                    if isinstance(segment, dict):
                        start_time_val = segment["start"]
                        end_time_val = segment["end"]
                        text_val = segment["text"]
                    else:
                        start_time_val = segment.start
                        end_time_val = segment.end
                        text_val = segment.text
                    
                    segment_count += 1
                    start_time = format_timestamp(start_time_val)
                    end_time = format_timestamp(end_time_val)
                    
                    # Clean and validate text
                    text = text_val.strip()
                    if not text:
                        continue
                        
                    # Write subtitle entry
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{text}\n\n")
                    
                    # Log every 50 segments to avoid spam
                    if segment_count % 50 == 0:
                        logger.info(f"Processed {segment_count} segments...")
                        
                except Exception as e:
                    logger.warning(f"Error processing segment: {e}")
                    continue
                    
            logger.info(f"Successfully saved {segment_count} segments to {output_txt_file}")
            
    except Exception as e:
        logger.error(f"Error saving transcription file: {e}")
        raise
    
    return output_txt_file

def save_translated_text(text, audio_filename=None, source_language="unknown", target_language="unknown"):
    """
    Enhanced save function with better error handling and memory management
    """
    output_directory = "../files"
    os.makedirs(output_directory, exist_ok=True)
    logger.info("Saving translated text to VTT file")
    
    # Create descriptive filename
    if audio_filename:
        clean_name = audio_filename.replace("audio-", "").split('.')[0]
        output_filename = f"translated_transcript_{clean_name}_{source_language}_{target_language}.vtt"
    else:
        output_filename = f"translated_transcript_unknown_{source_language}_{target_language}.vtt"
    
    output_txt_file = os.path.join(output_directory, output_filename)
    
    try:
        # Handle very large text files by writing in chunks
        with open(output_txt_file, 'w', encoding='utf-8', buffering=8192) as f:
            if isinstance(text, str):
                # For very large strings, write in chunks
                chunk_size = 8192  # 8KB chunks
                for i in range(0, len(text), chunk_size):
                    f.write(text[i:i+chunk_size])
            else:
                f.write(str(text))
            f.write("\n")
            
        logger.info(f"Translated text file created at {output_txt_file}")
        
        # Verify file was written correctly
        if os.path.exists(output_txt_file):
            file_size = os.path.getsize(output_txt_file)
            logger.info(f"File size: {file_size} bytes")
        
    except Exception as e:
        logger.error(f"Error saving translated text: {e}")
        raise
    
    return output_txt_file