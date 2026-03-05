"""NB_Generate — 텍스트 → 이미지 생성 노드."""

from __future__ import annotations

import torch
from comfy_api.latest import io, ui

from .config import NB_CONFIG
from ..gemini_client import generate_image


class NBGenerate(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="NB_Generate",
            display_name="NanoBanana Generate",
            category="NanoBanana",
            description="텍스트 프롬프트로 이미지를 생성합니다. "
                        "Gemini 3.1 Flash Image Preview를 직접 호출합니다.",
            is_output_node=True,
            inputs=[
                NB_CONFIG.Input("config", tooltip="NanoBanana Config 노드 연결"),
                io.String.Input("prompt", multiline=True, default="",
                                tooltip="이미지 생성 프롬프트"),
                io.Int.Input("seed", default=0, min=0, max=0xFFFFFFFFFFFFFFFF,
                             control_after_generate=True,
                             tooltip="시드값. 동일 시드로 재현 가능한 결과를 시도합니다"),
            ],
            outputs=[
                io.Image.Output(display_name="IMAGE"),
                io.String.Output(display_name="text"),
            ],
        )

    @classmethod
    def execute(cls, config: dict, prompt: str, seed: int) -> io.NodeOutput:
        if not prompt or not prompt.strip():
            raise ValueError("프롬프트를 입력해주세요.")

        images, text = generate_image(prompt, config, seed=seed)

        if images is None:
            images = torch.zeros((1, 512, 512, 3))
            text = text or "이미지 생성에 실패했습니다."

        return io.NodeOutput(images, text or "", ui=ui.PreviewImage(images))
