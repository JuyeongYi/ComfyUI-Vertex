"""Gemini 3.1 Flash Image Preview 모델 구현."""

from __future__ import annotations

from typing import Any

import torch
from google.genai import types

from ..auth import get_client
from ..const import (
    MODEL_ID,
    DEFAULT_SYSTEM_PROMPT,
    AspectRatio,
    ResponseModality,
)
from .base import ImageModel


class Gemini_3_1_FlashImage(ImageModel):
    """Gemini 3.1 Flash Image Preview — 이미지 생성/편집."""

    model_id = MODEL_ID
    display_name = "Gemini 3.1 Flash Image Preview"
    label = "NanoBanana2"

    def __init__(self) -> None:
        pass

    def generate_image(
        self, prompt: str, config: dict, seed: int = 0,
    ) -> tuple[torch.Tensor | None, str]:
        gc = self._build_config(config)
        sys_prompt = self._build_system_instruction(config)
        if sys_prompt:
            gc.system_instruction = sys_prompt

        client = get_client()
        response = client.models.generate_content(
            model=self.model_id,
            contents=[prompt],
            config=gc,
        )
        return self._parse_response(response)

    def edit_image(
        self, prompt: str, images: list[torch.Tensor], config: dict, seed: int = 0,
    ) -> tuple[torch.Tensor | None, str]:
        gc = self._build_config(config)
        sys_prompt = self._build_system_instruction(config)

        parts: list[Any] = []
        for img_tensor in images:
            img_bytes = self.tensor_to_bytes(img_tensor)
            parts.append(types.Part.from_bytes(
                data=img_bytes,
                mime_type="image/png",
            ))
        parts.append(prompt)

        if sys_prompt:
            gc.system_instruction = sys_prompt

        client = get_client()
        response = client.models.generate_content(
            model=self.model_id,
            contents=parts,
            config=gc,
        )
        return self._parse_response(response)

    def _build_config(self, config: dict) -> types.GenerateContentConfig:
        modalities_str = config.get("response_modalities", ResponseModality.IMAGE_TEXT)
        if modalities_str == ResponseModality.IMAGE:
            modalities = ["IMAGE"]
        else:
            modalities = ["TEXT", "IMAGE"]

        image_config_kwargs: dict[str, Any] = {}
        aspect_ratio = config.get("aspect_ratio", AspectRatio.AUTO)
        if aspect_ratio != AspectRatio.AUTO:
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

    def _build_system_instruction(self, config: dict) -> str | None:
        sp = config.get("system_prompt", "")
        return sp if sp else DEFAULT_SYSTEM_PROMPT

    def _parse_response(self, response) -> tuple[torch.Tensor | None, str]:
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
                    tensor = self.bytes_to_tensor(part.inline_data.data)
                    image_tensors.append(tensor)

        images = torch.cat(image_tensors, dim=0) if image_tensors else None
        text = "\n".join(text_parts)
        return images, text
