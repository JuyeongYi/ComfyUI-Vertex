"""API Key 및 클라이언트 관리."""

import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

# ComfyUI 루트의 .env 로드
_COMFYUI_ROOT = Path(__file__).parent.parent.parent
load_dotenv(_COMFYUI_ROOT / ".env")


def get_api_key() -> str:
    """Gemini API Key를 반환한다.

    탐색 순서:
    1. 환경변수 GEMINI_API_KEY
    2. ComfyUI 루트 .env 파일의 GEMINI_API_KEY

    향후 이 함수만 수정하면 1Password 등 외부 소스에서 키를 가져올 수 있다.
    """
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY가 설정되지 않았습니다. "
            "ComfyUI 루트의 .env 파일에 GEMINI_API_KEY=... 를 추가하거나 "
            "환경변수로 설정하세요."
        )
    return key


_client: genai.Client | None = None


def get_client() -> genai.Client:
    """genai.Client 싱글턴 반환."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=get_api_key())
    return _client
