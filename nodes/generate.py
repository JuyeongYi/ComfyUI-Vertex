"""Vertex Image Generate — 텍스트 → 이미지 생성 액션 노드."""

from __future__ import annotations

import asyncio

import torch
from comfy_api.latest import io, ui

from ..models.base import ImageModel
from .types import VERTEX_IMAGE_MODEL, VERTEX_CONFIG


class VertexImageGenerate(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Vertex_ImageGenerate",
            display_name="Vertex Image Generate",
            category="Vertex/Image",
            description="텍스트 프롬프트로 이미지를 생성합니다. "
                        "Model 노드에서 선택한 모델을 사용합니다.",
            is_output_node=True,
            inputs=[
                VERTEX_IMAGE_MODEL.Input("model", tooltip="Vertex Image Model 노드 연결"),
                VERTEX_CONFIG.Input("config", tooltip="Vertex Config 노드 연결"),
                io.String.Input("prompt", multiline=True, default="",
                                tooltip="이미지 생성 프롬프트"),
                io.Int.Input("seed", default=0, min=0, max=0xFFFFFFFFFFFFFFFF,
                             control_after_generate=True,
                             tooltip="시드값"),
            ],
            outputs=[
                io.Image.Output(display_name="IMAGE"),
                io.String.Output(display_name="text"),
            ],
        )

    @classmethod
    async def execute(cls, model: ImageModel, config: dict, prompt: str, seed: int) -> io.NodeOutput:
        if not prompt or not prompt.strip():
            raise ValueError("프롬프트를 입력해주세요.")

        loop = asyncio.get_event_loop()
        images, text = await loop.run_in_executor(
            None, lambda: model.generate_image(prompt, config, seed=seed)
        )

        if images is None:
            images = torch.zeros((1, 512, 512, 3))
            text = text or "이미지 생성에 실패했습니다."

        return io.NodeOutput(images, text or "", ui=ui.PreviewImage(images))
