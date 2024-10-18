import os
import argparse
from moviepy.editor import VideoFileClip
from faster_whisper import WhisperModel

def extract_audio(input_video, input_video_name):
    extracted_audio = f"audio-{input_video_name}.wav"

    # Check if the input video file exists
    if not os.path.exists(input_video):
        raise FileNotFoundError(f"The video file '{input_video}' was not found.")

    # Load video file and extract audio using moviepy
    try:
        video_clip = VideoFileClip(input_video)
        audio_clip = video_clip.audio
        audio_clip.write_audiofile(extracted_audio)
        audio_clip.close()  # Close the audio file after extraction
        video_clip.close()  # Close the video file
    except Exception as e:
        print(f"Error extracting audio: {e}")
        raise

    return extracted_audio

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Extract audio from video.")
    parser.add_argument('input_video', type=str, help="Path to the input video file")
    
    # Parse arguments
    args = parser.parse_args()
    input_video = args.input_video
    input_video_name = os.path.splitext(os.path.basename(input_video))[0]

    # Call the function to extract audio
    extracted_audio = extract_audio(input_video, input_video_name)
    print(f"Audio extracted to: {extracted_audio}")
    print("Done!")
