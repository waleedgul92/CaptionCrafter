import logging
import time
from transcribe import save_translated_text # Assuming this is in transcribe.py
from model import load_gemini_model       # Assuming this is in model.py

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# --- Helper Functions ---
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


# --- Main Translation Function (with Chunking & Retries) ---
def translate_text(llm, text, target_language="english", source_language="japanese", audio_filename=None, chunk_size=50, max_retries=3):
    """
    Translates VTT content robustly by processing it in smaller chunks
    and retrying failed chunks. The function signature is compatible
    with existing applications.
    """
    if not llm:
        logger.error("Translation model is not available.")
        return "Translation model is not available.", None

    if not text:
        logger.error("No text provided for translation.")
        return "No text provided for translation.", None

    try:
        original_subtitles = parse_vtt(text)
        if not original_subtitles:
            logger.error("No valid subtitle blocks found in the input text.")
            return "No valid subtitles found.", None
    except Exception as e:
        logger.error(f"Failed to parse VTT file: {e}")
        return f"Failed to parse VTT file: {e}", None

    llm_with_temp = llm.with_config(configurable={'temperature': 0.1})
    separator = "\n<--->\n"
    all_processed_subs = []

    logger.info(f"Starting translation of {len(original_subtitles)} blocks in chunks of {chunk_size}...")

    for i in range(0, len(original_subtitles), chunk_size):
        current_chunk_number = i // chunk_size + 1
        chunk_of_subs = original_subtitles[i:i + chunk_size]
        
        texts_to_translate = [sub['text'] for sub in chunk_of_subs]
        num_blocks_in_chunk = len(texts_to_translate)
        joined_text_for_prompt = separator.join(texts_to_translate)

        prompt = f"""
        You are a machine translation service. Your only function is to translate {source_language} text to {target_language}.
        Follow these rules exactly:
        1. The input contains multiple text blocks separated by '{separator}'.
        2. Translate each text block individually.
        3. Your output MUST contain the exact same number of blocks as the input, separated by the same '{separator}'.
        4. NEVER merge blocks. NEVER omit blocks.
        5. If an input block is just punctuation (e.g., "..."), return it exactly as is.
        6. Preserve HTML tags like <i>...</i>.

        INPUT TEXT:
        {joined_text_for_prompt}

        OUTPUT TEXT:
        """
        
        # --- Retry Logic ---
        translation_succeeded = False
        for attempt in range(max_retries + 1):
            if attempt > 0:
                logger.warning(f"Retrying translation for chunk {current_chunk_number} (Attempt {attempt + 1}/{max_retries + 1})...")
                time.sleep(2)
            
            logger.info(f"Translating chunk {current_chunk_number}, attempt {attempt + 1}...")

            try:
                response = llm_with_temp.invoke(prompt)
                translated_blob = response.content
                
                if not translated_blob:
                    logger.error(f"API call for chunk {current_chunk_number} returned empty content (possible safety block). This cannot be retried.")
                    translation_succeeded = False
                    break 

                translated_texts = translated_blob.split(separator)

                if len(translated_texts) != len(chunk_of_subs):
                    logger.warning(f"Attempt {attempt + 1} failed: Mismatched line count (got {len(translated_texts)}, expected {len(chunk_of_subs)}).")
                    continue

                logger.info(f"Chunk {current_chunk_number} translated successfully on attempt {attempt + 1}.")
                for j, sub in enumerate(chunk_of_subs):
                    sub['text'] = translated_texts[j].strip()
                
                all_processed_subs.extend(chunk_of_subs)
                translation_succeeded = True
                break

            except Exception as e:
                logger.error(f"A critical error occurred on attempt {attempt + 1} for chunk {current_chunk_number}: {e}")
        
        if not translation_succeeded:
            logger.error(f"Chunk {current_chunk_number} failed after all attempts. Reverting to original text.")
            all_processed_subs.extend(chunk_of_subs)
            
        time.sleep(1)

    logger.info(f"All chunks processed. Final list contains {len(all_processed_subs)} blocks.")
    
    try:
        final_vtt = reconstruct_vtt(all_processed_subs)
        
        logger.info("Saving translated file...")
        output_path = save_translated_text(
            final_vtt,
            audio_filename=audio_filename,
            source_language=source_language,
            target_language=target_language
        )
        logger.info(f"Translation and reconstruction completed successfully. File saved to: {output_path}")
        return final_vtt, output_path
    except Exception as e:
        logger.error(f"A fatal error occurred during final file reconstruction or saving: {e}", exc_info=True)
        return "Failed during final file creation.", None
