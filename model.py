
import os
import logging
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain_community.llms import HuggingFaceHub
# from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


load_dotenv("keys.env")
google_api_key = os.getenv("GOOGLE_API_KEY")

if not google_api_key:
    logger.warning("GOOGLE_API_KEY not found in environment variables.")

def load_gemini_model():
    if not google_api_key:
        logger.error("Cannot load Gemini: GOOGLE_API_KEY is missing.")
        return None
    try:
        logger.info("Loading Gemini model...")
        # Using ChatGoogleGenerativeAI for chat-optimized models like gemini-pro
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-preview-05-20", google_api_key=google_api_key  )
        logger.info("Gemini model loaded successfully.")
        return llm
    except Exception as e:
        logger.error(f"Failed to load Gemini model: {e}", exc_info=True)
        return None
    


