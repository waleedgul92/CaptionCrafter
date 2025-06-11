from google import genai

import logging
import os
from transcribe import save_translated_text
from dotenv import load_dotenv

from google.genai import types
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


load_dotenv("./keys.env")
google_api_key = os.getenv("GOOGLE_API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_gemini_model1():
    """
    Loads and configures the Gemini model from google-generativeai.
    """

    try:
        # It's recommended to set your API key as an environment variable
        genai.configure(api_key=google_api_key)
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.error("GOOGLE_API_KEY environment variable not set.")
            return None
        genai.configure(api_key=api_key)
        logger.info("Loading Gemini model...")
        client = genai.Client()



        
    
        logger.info("Gemini model loaded successfully.")
        return model
    except Exception as e:
        logger.error(f"Error loading Gemini model: {e}")
        return None




def translate_text1( text, target_language="english", source_language="japanese", audio_filename=None):
    """
    Translates the given text to the target language using the loaded Gemini model.
    """

    try:
        logger.info(f"Translating text to {target_language} from {source_language}... ")
        logger.info(f"Text to translate: {text[:100]}...")

        prompt = f"""
        You are a professional audiovisual subtitle translator with expertise in Japanese media localization.

        You are given a subtitle file containing timestamps and dialogue lines in {source_language}.

        Your task is to translate **only the text portions** into fluent, natural-sounding {target_language}, while following professional subtitle standards.

        Instructions:
        1. **Do not modify** the timestamps.
        2. **Do not change** the file format, spacing, or line breaks.
        3. **Preserve all subtitle blocks**, even if the text is only punctuation (e.g., "...") or interjections (e.g., "Ah!").
        4. **Do not skip any subtitle block**, even if you believe it has little content. Every timestamped entry must remain present in the output.
        5. Maintain **italics tags** (e.g., <i>...</i>) to indicate internal thoughts or non-spoken dialogue. If the original text represents a character's internal monologue or thought, wrap the translated line in <i>...</i> if not already marked.
        6. **Translate for meaning, tone, and emotion**, not word-for-word. Match the emotional intensity and character voice.
        7. Use **natural phrasing** suitable for subtitle viewing: concise, fluent, colloquial if needed, and culturally appropriate.
        8. Preserve the **original subtitle order**.
        9. **Do not add or remove** lines, comments, or any metadata.
        10. **Do not translate** names of people or places unless commonly known in the target language. If uncertain, retain the original.
        11. Translate interjections or sound effects (e.g., "Ah!", "Hmm") only if they have a widely accepted equivalent; otherwise, leave unchanged.
        12. Ensure **questions retain** the interrogative form.
        13. Translate **idiomatic expressions and slang** into their natural equivalents in the target language.
        14. Adapt **cultural references** for the {target_language} audience.
        15. Maintain **consistent translation** of recurring names, titles (e.g., “Master Strategist”, “Mother”), and terminology throughout.
        16. If you're unsure whether a line is internal thought or spoken aloud, infer from context or conservatively use <i>...</i> for introspective lines.

        Output the translated subtitle file with all timestamps and line breaks exactly as provided.
        Do not skip any blocks.
        Do not include any commentary or additional formatting outside the subtitles.


        Input:
        {text}
        """
        from google import genai
        from google.genai import types

        client = genai.Client()

        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            ),
        )

        translated_content=response.text

        
        # output_path = save_translated_text(
        #     translated_content, 
        #     audio_filename=audio_filename, 
        #     source_language=source_language, 
        #     target_language=target_language
        # )
        
        return translated_content,None
        
    except Exception as e:
        logger.error(f"Error during translation: {e}")
        return "Translation failed due to an error.", None


text=""
input_file = "../tests/japanese/video 1/transcript_Episode 21-jp_ja.vtt"
target_language = "english"
source_language = "japanese"
with open(input_file, "r", encoding="utf-8") as f:
    text = f.read()
# llm = load_gemini_model1()/
translated_text , output_path= translate_text1(text, target_language,source_language)
print(translated_text   )
# save_translated_text(translated_text, audio_filename=None, source_language=source_language, target_language=target_language)