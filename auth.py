"""API Key 관리. 향후 1Password 등 런타임 키 주입으로 교체 가능."""

import os
from pathlib import Path

from dotenv import load_dotenv

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
