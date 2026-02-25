import os
import glob
import requests

def get_translated_subtitles(file_path, source_lang_full, target_lang_full, source_lang_code):
    base_url = "http://localhost:8000"
    folder_path = os.path.dirname(file_path)
    base_name = os.path.basename(file_path)
    
    with open(file_path, "rb") as f:
        files = {"audio_file": (base_name, f, "application/octet-stream")}
        data = {"language": source_lang_code, "model_size": "small", "device": "cpu", "compute_type": "int8"}
        requests.post(f"{base_url}/transcribe_audio", files=files, data=data)

    transcript_response = requests.get(f"{base_url}/download_transcript")
    transcript_filename = os.path.join(folder_path, f"original_{base_name}.vtt")
    
    with open(transcript_filename, "wb") as f:
        f.write(transcript_response.content)

    with open(transcript_filename, "rb") as f:
        files = {"input_file": (os.path.basename(transcript_filename), f, "text/vtt")}
        data = {"source_language": source_lang_full, "target_language": target_lang_full}
        requests.post(f"{base_url}/translate_text", files=files, data=data)

    translated_response = requests.get(f"{base_url}/download_translated_subtitle")
    translated_filename = os.path.join(folder_path, f"translated_{base_name}.vtt")
    
    with open(translated_filename, "wb") as f:
        f.write(translated_response.content)

    return translated_filename

def process_folder(folder_path):
    folder_name = os.path.basename(os.path.normpath(folder_path))
    parts = folder_name.split('_')
    source_lang_full = parts[0]
    target_lang_full = parts[1]
    
    lang_to_code = {
        "english": "en",
        "japanese": "ja",
        "german": "de",
        "spanish": "es",
        "french": "fr",
        "chinese": "zh",
        "italian": "it",
        "korean": "ko",
        "russian": "ru",
        "portuguese": "pt",
        "arabic": "ar",
        "hindi": "hi"
    }
    
    source_lang_code = lang_to_code.get(source_lang_full.lower(), "")

    video_extensions = ["*.mp4", "*.mkv", "*.avi", "*.mov", "*.ts"]
    video_files = []
    for ext in video_extensions:
        video_files.extend(glob.glob(os.path.join(folder_path, ext)))

    for video_file in video_files:
        get_translated_subtitles(video_file, source_lang_full, target_lang_full, source_lang_code)

if __name__ == "__main__":
    process_folder("japanese_english")