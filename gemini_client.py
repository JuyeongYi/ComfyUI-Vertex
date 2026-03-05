"""Gemini 3.1 Flash Image Preview SDK 래퍼."""

from __future__ import annotations

import base64
from io import BytesIO
from typing import Any

import numpy as np
import torch
from PIL import Image

from google import genai
from google.genai import types

from .auth import get_api_key

MODEL_ID = "gemini-3.1-flash-image-preview"

DEFAULT_SYSTEM_PROMPT = (
    "You are an expert image-generation engine. You must ALWAYS produce an image.\n"
    "Interpret all user input as literal visual directives for image composition.\n"
    "If a prompt lacks specific visual details, creatively invent a concrete visual scenario.\n"
    "Prioritize generating the visual representation above any text or conversational requests."
)


def _get_client() -> genai.Client:
    """google-genai Client 생성 (Express Mode)."""
    return genai.Client(api_key=get_api_key())


def _tensor_to_bytes(tensor: torch.Tensor) -> bytes:
    """단일 이미지 텐서 [1,H,W,C] → PNG bytes."""
    arr = (tensor.squeeze(0).cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
    img = Image.fromarray(arr)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _bytes_to_tensor(data: bytes) -> torch.Tensor:
    """raw bytes (PNG/JPEG) → [1,H,W,C] float32 텐서."""
    img = Image.open(BytesIO(data)).convert("RGB")
    arr = np.array(img, dtype=np.float32) / 255.0
    return torch.from_numpy(arr).unsqueeze(0)


def _build_config(config: dict) -> types.GenerateContentConfig:
    """NB_CONFIG dict → GenerateContentConfig."""
    modalities_str = config.get("response_modalities", "IMAGE+TEXT")
    if modalities_str == "IMAGE":
        modalities = ["IMAGE"]
    else:
        modalities = ["TEXT", "IMAGE"]

    image_config_kwargs: dict[str, Any] = {}
    aspect_ratio = config.get("aspect_ratio", "auto")
    if aspect_ratio != "auto":
        image_config_kwargs["aspect_ratio"] = aspect_ratio
    image_size = config.get("image_size", "1K")
    if image_size:
        image_config_kwargs["image_size"] = image_size

    gc = types.GenerateContentConfig(
        response_modalities=modalities,
        image_config=types.ImageConfig(**image_config_kwargs) if image_config_kwargs else None,
    )

    thinking_level = config.get("thinking_level")
    if thinking_level and thinking_level != "NONE":
        gc.thinking_config = types.ThinkingConfig(thinking_level=thinking_level)

    return gc


def _build_system_instruction(config: dict) -> str | None:
    """시스템 프롬프트 반환. 비어있으면 기본값 사용."""
    sp = config.get("system_prompt", "")
    return sp if sp else DEFAULT_SYSTEM_PROMPT


def _parse_response(response) -> tuple[torch.Tensor | None, str]:
    """Gemini 응답에서 이미지 텐서와 텍스트를 추출."""
    image_tensors: list[torch.Tensor] = []
    text_parts: list[str] = []

    if not response.candidates:
        return None, "Gemini API returned no response candidates."

    for candidate in response.candidates:
        if candidate.finish_reason and candidate.finish_reason != types.FinishReason.STOP:
            continue
        if not candidate.content or not candidate.content.parts:
            continue
        for part in candidate.content.parts:
            if hasattr(part, "thought") and part.thought:
                continue
            if part.text:
                text_parts.append(part.text)
            if part.inline_data and part.inline_data.data:
                tensor = _bytes_to_tensor(part.inline_data.data)
                image_tensors.append(tensor)

    images = torch.cat(image_tensors, dim=0) if image_tensors else None
    text = "\n".join(text_parts)
    return images, text


def generate_image(prompt: str, config: dict, seed: int = 0) -> tuple[torch.Tensor | None, str]:
    """텍스트 → 이미지 생성."""
    client = _get_client()
    gc = _build_config(config)
    sys_prompt = _build_system_instruction(config)

    contents: list[Any] = [prompt]
    if sys_prompt:
        gc.system_instruction = sys_prompt

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=contents,
        config=gc,
    )
    return _parse_response(response)


def edit_image(
    prompt: str,
    images: list[torch.Tensor],
    config: dict,
    seed: int = 0,
) -> tuple[torch.Tensor | None, str]:
    """이미지 + 텍스트 → 편집된 이미지 생성."""
    client = _get_client()
    gc = _build_config(config)
    sys_prompt = _build_system_instruction(config)

    # 이미지를 Part로 변환
    parts: list[Any] = []
    for img_tensor in images:
        img_bytes = _tensor_to_bytes(img_tensor)
        parts.append(types.Part.from_bytes(
            data=img_bytes,
            mime_type="image/png",
        ))
    parts.append(prompt)

    if sys_prompt:
        gc.system_instruction = sys_prompt

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=parts,
        config=gc,
    )
    return _parse_response(response)
