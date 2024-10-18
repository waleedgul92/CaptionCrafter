import os
import argparse
import speech_recognition as sr
from pydub import AudioSegment

def transcribe_audio_to_text(audio_file):
    recognizer = sr.Recognizer()
    with sr.AudioFile(audio_file) as source:
        audio_data = recognizer.record(source)
        try:
            text = recognizer.recognize_whisper(audio_data)
            return text
        except sr.UnknownValueError:
            print("Audio not understood.")
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service; {e}")
            return ""

def save_transcription_to_txt(transcription_text, output_txt_file):
    with open(output_txt_file, 'w', encoding='utf-8') as f:
        f.write(transcription_text)
    print(f"Transcription saved to: {output_txt_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transcribe audio file to plain text.")
    parser.add_argument('audio_file', type=str, help="Path to the input audio file")
    args = parser.parse_args()
    audio_file_path = args.audio_file

    transcription_text = transcribe_audio_to_text(audio_file_path)

    audio_file_name = os.path.splitext(os.path.basename(audio_file_path))[0]
    output_txt_file_name = f"{audio_file_name}_transcription.txt"
    save_transcription_to_txt(transcription_text, output_txt_file_name)