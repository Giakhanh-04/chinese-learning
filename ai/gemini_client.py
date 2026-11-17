import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


_client = None


def get_gemini_client():

    global _client

    if _client is not None:
        return _client

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError("Chưa cấu hình GEMINI_API_KEY")

    _client = genai.Client(api_key=api_key)

    return _client


def ask_gemini(question):

    try:

        client = get_gemini_client()

        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=question
        )

        return response.text

    except Exception as e:

        print("========== GEMINI ERROR ==========")
        print(type(e).__name__)
        print(str(e))
        print("===================================")

        return "⚠️ Không thể kết nối với AI. Vui lòng thử lại sau."