import logging
import time
import re
from transcribe import save_translated_text # Assuming this is in transcribe.py
from model import load_gemini_model      # Assuming this is in model.py

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# --- Helper Functions (No Changes) ---
def parse_vtt(vtt_content):
    """
    Parses VTT content into a list of dictionaries, each with 'timestamp' and 'text'.
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
def translate_text(llm, text, target_language="english", source_language="japanese", audio_filename=None, chunk_size=50, max_retries=3):
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

    llm_with_temp = llm.with_config(configurable={'temperature': 0.1})
    all_processed_subs = []

    logger.info(f"Starting translation of {len(original_subtitles)} blocks in chunks up to {chunk_size}...")

    # --- NEW: Internal recursive translation function ---
    def _translate_chunk_recursively(chunk_of_subs):
        """
        Translates a given chunk. If it fails, splits the chunk in half and retries on each half.
        Returns the translated chunk or the original if all attempts fail.
        """
        num_blocks_in_chunk = len(chunk_of_subs)
        
        # Base case: If the chunk is empty or invalid, return it as is.
        if num_blocks_in_chunk == 0:
            return []
        
        # Base case: For a single line, do a simple, robust translation.
        if num_blocks_in_chunk == 1:
            try:
                # Use a simpler prompt for single lines to be safe
                single_prompt = f"Translate the following text from {source_language} to {target_language}. Do not add comments. TEXT: {chunk_of_subs[0]['text']}"
                response = llm_with_temp.invoke(single_prompt)
                translated_text = clean_translation(response.content)
                chunk_of_subs[0]['text'] = translated_text
                return chunk_of_subs
            except Exception as e:
                logger.error(f"Failed to translate single line: {chunk_of_subs[0]['text']}. Error: {e}")
                return chunk_of_subs # Return original on error

        separator = "\n<--->\n"
        texts_to_translate = [sub['text'] for sub in chunk_of_subs]
        joined_text_for_prompt = separator.join(texts_to_translate)
        
        prompt = f"""
        You are an expert subtitle translator. Your task is to translate a batch of subtitles from {source_language} to {target_language}.
        Follow these rules precisely:
        1. The input below is a series of text blocks separated by a specific marker: '{separator}'.
        2. Translate the content of each block into {target_language}.
        3. Your output MUST contain the exact same number of blocks ({num_blocks_in_chunk}), separated by the same '{separator}' marker.
        4. NEVER merge or omit any blocks. The block count must match perfectly.
        5. Preserve all original HTML tags like <i>...</i>.
        6. Do not add any extra text, explanations, or comments.

        INPUT TEXT:
        {joined_text_for_prompt}

        OUTPUT TEXT:
        """

        for attempt in range(max_retries):
            try:
                logger.info(f"Attempting to translate a chunk of size {num_blocks_in_chunk} (Attempt {attempt + 1}/{max_retries})")
                response = llm_with_temp.invoke(prompt)
                translated_blob = response.content

                if not translated_blob or not translated_blob.strip():
                     raise ValueError("API call returned empty content.")

                translated_texts = translated_blob.split(separator)

                if len(translated_texts) == num_blocks_in_chunk:
                    logger.info(f"Successfully translated chunk of size {num_blocks_in_chunk}.")
                    for j, sub in enumerate(chunk_of_subs):
                        sub['text'] = clean_translation(translated_texts[j])
                    return chunk_of_subs # Success!
                else:
                    logger.warning(f"Mismatched line count in chunk of size {num_blocks_in_chunk} (got {len(translated_texts)}).")
                    continue # Try again
            
            except Exception as e:
                logger.error(f"Error on attempt {attempt + 1} for chunk of {num_blocks_in_chunk}: {e}")
                time.sleep(1)

        # --- DIVIDE AND CONQUER ---
        logger.warning(f"Chunk of size {num_blocks_in_chunk} failed all retries. Splitting it.")
        mid_point = num_blocks_in_chunk // 2
        first_half = chunk_of_subs[:mid_point]
        second_half = chunk_of_subs[mid_point:]

        # Recursively process each half and combine the results
        translated_first_half = _translate_chunk_recursively(first_half)
        translated_second_half = _translate_chunk_recursively(second_half)
        
        return translated_first_half + translated_second_half

    # --- Main Loop ---
    for i in range(0, len(original_subtitles), chunk_size):
        chunk = original_subtitles[i:i + chunk_size]
        logger.info(f"--- Processing main chunk starting at block {i+1} ---")
        
        processed_chunk = _translate_chunk_recursively(chunk)
        all_processed_subs.extend(processed_chunk)
        
        time.sleep(1) # Rate limit between main chunks

    logger.info(f"All chunks processed. Final list contains {len(all_processed_subs)} blocks.")
    
    try:
        final_vtt = reconstruct_vtt(all_processed_subs)
        output_path = save_translated_text(
            final_vtt, audio_filename, source_language, target_language
        )
        logger.info(f"Translation complete. File saved to: {output_path}")
        return final_vtt, output_path
    except Exception as e:
        logger.error(f"Fatal error during file saving: {e}", exc_info=True)
        return "Failed during final file creation.", None