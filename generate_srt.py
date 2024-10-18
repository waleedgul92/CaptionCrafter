import os
import argparse
from pydub import AudioSegment

def split_text_into_sentences(text):
    """Split text into sentences or chunks based on punctuation."""
    # You can customize this to split by sentences or any other rule.
    sentences = text.split(". ")
    return [sentence.strip() + "." for sentence in sentences if sentence]

def apply_timestamps_to_chunks(audio_file, chunks):
    """Apply timestamps to chunks of text based on audio duration."""
    audio = AudioSegment.from_file(audio_file)
    total_duration = len(audio) / 1000  # Convert to seconds
    chunk_duration = total_duration / len(chunks)  # Approximate duration per chunk

    results = []
    start_time = 0.0

    for chunk in chunks:
        end_time = start_time + chunk_duration
        results.append((start_time, end_time, chunk))
        start_time = end_time  # Move to next chunk

    return results

def save_transcription_to_srt(transcription_results, output_srt_file):
    with open(output_srt_file, 'w', encoding='utf-8') as f:
        for i, (start, end, text) in enumerate(transcription_results):
            f.write(f"{i + 1}\n")
            start_srt = f"{int(start // 3600):02}:{int((start % 3600) // 60):02}:{int(start % 60):02},{int((start % 1) * 1000):03}"
            end_srt = f"{int(end // 3600):02}:{int((end % 3600) // 60):02}:{int(end % 60):02},{int((end % 1) * 1000):03}"
            f.write(f"{start_srt} --> {end_srt}\n")
            f.write(f"{text}\n\n")
    print(f"SRT file saved as {output_srt_file}")

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Convert transcribed text to SRT with timestamps.")
    parser.add_argument('audio_file', type=str, help="Path to the original audio file")
    parser.add_argument('transcription_file', type=str, help="Path to the transcribed text file")
    
    args = parser.parse_args()
    audio_file_path = args.audio_file
    transcription_file_path = args.transcription_file

    # Read the transcribed text from file
    with open(transcription_file_path, 'r', encoding='utf-8') as f:
        transcribed_text = f.read()

    # Split the text into sentences or chunks
    text_chunks = split_text_into_sentences(transcribed_text)

    # Apply timestamps based on audio duration
    transcription_results = apply_timestamps_to_chunks(audio_file_path, text_chunks)

    # Save the transcription results to an SRT file
    output_srt_file = os.path.splitext(transcription_file_path)[0] + ".srt"
    save_transcription_to_srt(transcription_results, output_srt_file)
