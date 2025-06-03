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


def extract_audio(input_video, input_video_name):
    extracted_audio_path = f"./files/audio-{input_video_name}.wav"

    if not os.path.exists(input_video):
        raise FileNotFoundError(f"The video file '{input_video}' was not found.")
    
    try:
        video_clip = VideoFileClip(input_video)
        audio_clip = video_clip.audio
        audio_clip.write_audiofile(extracted_audio_path)
        audio_clip.close()  
        video_clip.close()  
    except Exception as e:
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
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}.{millis:03}"

def save_transcription_to_txt(segments):
    output_txt_file = "./files/transcription.vtt"
    with open(output_txt_file, 'w', encoding='utf-8') as f:
        f.write("WEBVTT\n\n")
        for i, segment in enumerate(segments, 1):
            start_time = format_timestamp(segment.start)
            end_time = format_timestamp(segment.end)
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{segment.text}\n\n")



def save_translated_text(text):
    output_txt_file = "./files/transcription_trans.vtt"
    with open(output_txt_file, 'w', encoding='utf-8') as f:
        f.write(text + "\n")
# print(transcribe_audio_to_text("./files/audio-Episode_8.wav"))