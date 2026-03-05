"""Gemini 3.1 Flash Image Preview 직접 호출 테스트 스크립트.

Usage:
    cd C:/Users/Jooyo/source/ComfyUI
    .venv/Scripts/python custom_nodes/ComfyUI-NanoBanana/scripts/test_generate.py "a cat astronaut floating in space"
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# CWD 기준으로 .env 로드 (cd ComfyUI 에서 실행 전제)
from dotenv import load_dotenv
load_dotenv(Path.cwd() / ".env")

from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import os

MODEL_ID = "gemini-3.1-flash-image-preview"

SYSTEM_PROMPT = (
    "You are an expert image-generation engine. You must ALWAYS produce an image.\n"
    "Interpret all user input as literal visual directives for image composition.\n"
    "If a prompt lacks specific visual details, creatively invent a concrete visual scenario.\n"
    "Prioritize generating the visual representation above any text or conversational requests."
)


def main():
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "A serene Japanese garden with cherry blossoms, koi pond, and a small wooden bridge at sunset"

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("GEMINI_API_KEY가 설정되지 않았습니다.")
        sys.exit(1)

    print(f"Prompt: {prompt}")
    print(f"Model: {MODEL_ID}")
    print("Generating...")

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_modalities=["TEXT", "IMAGE"],
            image_config=types.ImageConfig(image_size="1K"),
        ),
    )

    if not response.candidates:
        print("응답 없음.")
        sys.exit(1)

    candidate = response.candidates[0]
    if candidate.finish_reason != types.FinishReason.STOP:
        print(f"생성 실패: {candidate.finish_reason}")
        sys.exit(1)

    output_dir = _PROJECT_ROOT / "scripts" / "output"
    output_dir.mkdir(exist_ok=True)

    for part in candidate.content.parts:
        if hasattr(part, "thought") and part.thought:
            continue
        if part.text:
            print(f"\nText: {part.text}")
        if part.inline_data and part.inline_data.data:
            img = Image.open(BytesIO(part.inline_data.data))
            out_path = output_dir / "test_output.png"
            img.save(out_path)
            print(f"\nImage saved: {out_path} ({img.width}x{img.height})")


if __name__ == "__main__":
    main()
