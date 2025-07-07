import logging
import time
import re
from transcribe import save_translated_text  # Assuming this is in transcribe.py
from model import load_gemini_model          # Assuming this is in model.py

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# --- Helper Functions ---
def parse_vtt(vtt_content):
    """
    Parses VTT content into a list of dictionaries with 'timestamp' and 'text'.
    """
    content = vtt_content.strip().replace('\r\n', '\n')
    blocks = content.split('\n\n')

    subtitles = []
    start_index = 1 if blocks and blocks[0].strip() == "WEBVTT" else 0

    for i in range(start_index, len(blocks)):
        block = blocks[i].strip()
        if "-->" in block:
            lines = block.split('\n')
            timestamp = lines[0]
            text = "\n".join(lines[1:])
            subtitles.append({"timestamp": timestamp, "text": text})
    return subtitles


def reconstruct_vtt(subtitles):
    """Reconstructs VTT content from a list of subtitle dictionaries."""
    content = "WEBVTT\n\n"
    for sub in subtitles:
        content += f"{sub['timestamp']}\n{sub['text']}\n\n"
    return content.strip()


def clean_translation(text):
    """
    Removes unwanted artifacts and parenthetical explanations from translated text.
    """
    text = re.sub(r'\s*\([^)]*\)$', '', text.strip())
    return text.strip()


# --- Main Translation Function ---
def translate_text(llm, text, target_language="english", source_language="german", audio_filename=None, chunk_size=50, max_retries=3):
    """
    Translates VTT content robustly using an adaptive chunking strategy.
    """
    if not llm:
        logger.error("Translation model is not available.")
        return "Translation model is not available.", None

    try:
        original_subtitles = parse_vtt(text)
        if not original_subtitles:
            logger.error("No valid subtitle blocks found in the input text.")
            return "No valid subtitles found.", None
    except Exception as e:
        logger.error(f"Failed to parse VTT file: {e}")
        return f"Failed to parse VTT file: {e}", None

    # Add index to track position
    indexed_subtitles = [{"index": i, "timestamp": sub["timestamp"], "text": sub["text"]} for i, sub in enumerate(original_subtitles)]

    llm_with_temp = llm.with_config(configurable={'temperature': 0.1})
    all_processed_subs = []

    logger.info(f"Starting translation of {len(indexed_subtitles)} blocks in chunks up to {chunk_size}...")

    # --- Recursive Translator ---
    def _translate_chunk_recursively(chunk_of_subs):
        """
        Translates a chunk robustly, recursively splitting and falling back to line-by-line on error.
        """
        num_blocks = len(chunk_of_subs)
        if num_blocks == 0:
            return []

        # Base case
        if num_blocks == 1:
            for _ in range(max_retries):
                try:
                    prompt = f"Translate the following text from {source_language} to {target_language}. Do not add comments. TEXT: {chunk_of_subs[0]['text']}"
                    response = llm_with_temp.invoke(prompt)
                    translated_text = clean_translation(response.content)
                    if translated_text:
                        chunk_of_subs[0]['text'] = translated_text
                        return chunk_of_subs
                except Exception as e:
                    logger.error(f"Single-line translation failed, retrying... Error: {e}")
                    time.sleep(1)
            logger.error(f"Giving up on one line. Returning original to preserve timestamp.")
            return chunk_of_subs

        separator = "\n<--->\n"
        texts_to_translate = [sub['text'] for sub in chunk_of_subs]
        joined_text = separator.join(texts_to_translate)

        prompt = f"""
        You are an expert subtitle translator. Translate the following subtitles from {source_language} to {target_language}.

        - Each block is separated by '{separator}'.
        - Do not merge, omit, or add blocks. Translate each block exactly.
        - Return the translated text using the same '{separator}' separator.
        - Do NOT add extra text or comments.

        INPUT:
        {joined_text}

        OUTPUT:
        """

        for attempt in range(max_retries):
            try:
                response = llm_with_temp.invoke(prompt)
                translated_blob = response.content.strip()
                if not translated_blob:
                    raise ValueError("Empty translation result.")

                translated_texts = translated_blob.split(separator)
                if len(translated_texts) == num_blocks:
                    logger.info(f"Translated {num_blocks} blocks successfully.")
                    for i in range(num_blocks):
                        chunk_of_subs[i]['text'] = clean_translation(translated_texts[i])
                    return chunk_of_subs
                else:
                    logger.warning(f"Mismatched chunk size (expected {num_blocks}, got {len(translated_texts)}). Retrying...")
            except Exception as e:
                logger.error(f"Translation attempt {attempt + 1} failed: {e}")
                time.sleep(1)

        logger.warning(f"Translation failed for chunk of size {num_blocks}. Splitting further.")
        mid = num_blocks // 2
        return _translate_chunk_recursively(chunk_of_subs[:mid]) + _translate_chunk_recursively(chunk_of_subs[mid:])

    # --- Main Loop ---
    for i in range(0, len(indexed_subtitles), chunk_size):
        chunk = indexed_subtitles[i:i + chunk_size]
        logger.info(f"--- Processing chunk from index {i} ---")
        translated_chunk = _translate_chunk_recursively(chunk)
        all_processed_subs.extend(translated_chunk)
        time.sleep(1)

    logger.info("Translation finished. Sorting and saving...")

    # Sort by original order using index
    final_subs = sorted(all_processed_subs, key=lambda x: x['index'])

    try:
        final_vtt = reconstruct_vtt(final_subs)
        output_path = save_translated_text(final_vtt, audio_filename, source_language, target_language)
        logger.info(f"Saved to: {output_path}")
        return final_vtt, output_path
    except Exception as e:
        logger.error(f"Failed to save final file: {e}", exc_info=True)
        return "Failed during final file creation.", None
