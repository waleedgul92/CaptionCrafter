import os
import argparse
import speech_recognition as sr
from pydub import AudioSegment

def split_text(text, max_words=5):
    """Split text into segments not exceeding max_words."""
    words = text.split()
    segments = []
    current_segment = []

    for word in words:
        if len(current_segment) + 1 > max_words:
            segments.append(" ".join(current_segment))
            current_segment = [word]
        else:
            current_segment.append(word)

    if current_segment:
        segments.append(" ".join(current_segment))

    return segments

def transcribe_audio_with_dynamic_timestamps( audio_file, max_words=5):
    # Initialize recognizer
    recognizer = sr.Recognizer()

    # Load the audio file
    audio = AudioSegment.from_file(audio_file)

    # Prepare a list to hold the results
    results = []
    # Duration of each word (dynamically calculate later)
    total_duration = len(audio)
    subtitle_index = 0

    # Process the audio file in chunks
    chunk_duration = 10000  # Process 10-second chunks
    for i in range(0, total_duration, chunk_duration):
        # Extract audio chunk
        chunk = audio[i:i + chunk_duration]

        # Save chunk to a temporary file
        chunk_file = f"chunk_{subtitle_index}.wav"
        chunk.export(chunk_file, format="wav")

        # Recognize speech using Google Web Speech API
        with sr.AudioFile(chunk_file) as source:
            audio_data = recognizer.record(source)
            try:
                # Recognize speech and get the text
                text = recognizer.recognize_whisper(audio_data)
                start_time = i / 1000  # Convert milliseconds to seconds

                # Split the recognized text into smaller segments
                segments = split_text(text, max_words=max_words)

                # Check if segments are empty to avoid ZeroDivisionError
                if len(segments) > 0:
                    duration_per_segment = len(chunk) / len(segments)  # Dynamic time per segment
                    for segment in segments:
                        end_time = start_time + duration_per_segment / 1000  # Convert ms to s
                        results.append((start_time, end_time, segment))
                        start_time = end_time  # Update the start time for the next segment
                        subtitle_index += 1
                else:
                    print("No speech was recognized in this chunk.")
            except sr.UnknownValueError:
                print("Audio not understood.")
            except sr.RequestError as e:
                print(f"Could not request results from Google Speech Recognition service; {e}")

        # Delete the temporary chunk file after processing
        os.remove(chunk_file)

    return results

def save_transcription_to_srt(transcription_results, output_file):
    with open(output_file, 'w', encoding='utf-8') as f:
        for i, (start, end, text) in enumerate(transcription_results):
            # Write the index of the subtitle
            f.write(f"{i + 1}\n")
            # Convert start and end time to SRT format (HH:MM:SS,ms)
            start_srt = f"{int(start // 3600):02}:{int((start % 3600) // 60):02}:{int(start % 60):02},{int((start % 1) * 1000):03}"
            end_srt = f"{int(end // 3600):02}:{int((end % 3600) // 60):02}:{int(end % 60):02},{int((end % 1) * 1000):03}"
            f.write(f"{start_srt} --> {end_srt}\n")
            # Write the text
            f.write(f"{text}\n\n")

def save_transcription_to_txt(transcription_results, output_txt_file):
    with open(output_txt_file, 'w', encoding='utf-8') as f:
        for _, _, text in transcription_results:
            f.write(f"{text}\n")  # Write each segment on a new line

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Transcribe audio file to SRT format with dynamic timestamps.")
    parser.add_argument('audio_file', type=str, help="Path to the input audio file")
    parser.add_argument('--max-words', type=int, default=5, help="Maximum number of words per subtitle (default: 5)")

    # Parse arguments
    args = parser.parse_args()
    audio_file_path = args.audio_file
    language = args.language
    max_words = args.max_words

    # Get the base name of the audio file without extension
    audio_file_name = os.path.splitext(os.path.basename(audio_file_path))[0]
    audio_file_name = audio_file_name.split("-")[1]

    # Transcribe the audio with dynamic subtitles
    transcription_results = transcribe_audio_with_dynamic_timestamps( audio_file_path, max_words=max_words)

    # Define the output file name (original name + language)
    output_file_name = f"{audio_file_name}_{language}.srt"
    output_txt_file_name = f"{audio_file_name}_{language}.txt"  # Define the text output file name

    # Save transcription results to SRT file
    save_transcription_to_srt(transcription_results, output_file_name)
    save_transcription_to_txt(transcription_results, output_txt_file_name)  # Save to text file

    print(f"Transcription saved to: {output_file_name}")
    print(f"Transcription saved to: {output_txt_file_name}")

    # Delete the original audio file after transcription
    if os.path.exists(audio_file_path):
        os.remove(audio_file_path)
        print(f"Deleted the audio file: {audio_file_path}")
