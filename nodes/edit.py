"""Vertex Image Edit — 이미지 편집 액션 노드. Autogrow로 최대 14장 이미지 입력."""

from __future__ import annotations

import asyncio

import torch
from comfy_api.latest import io, ui

from ..models.base import ImageModel
from .types import VERTEX_IMAGE_MODEL, VERTEX_CONFIG


class VertexImageEdit(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Vertex_ImageEdit",
            display_name="Vertex Image Edit",
            category="Vertex/Image",
            description="이미지를 텍스트 지시로 편집합니다. "
                        "최대 14장의 이미지를 순서대로 입력할 수 있습니다.",
            is_output_node=True,
            inputs=[
                VERTEX_IMAGE_MODEL.Input("model", tooltip="Vertex Image Model 노드 연결"),
                VERTEX_CONFIG.Input("config", tooltip="Vertex Config 노드 연결"),
                io.String.Input("prompt", multiline=True, default="",
                                tooltip="편집 지시 프롬프트"),
                io.Autogrow.Input(
                    "images",
                    template=io.Autogrow.TemplatePrefix(
                        io.Image.Input("image"),
                        prefix="image",
                        min=1,
                        max=14,
                    ),
                ),
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
    async def execute(cls, model: ImageModel, config: dict, prompt: str,
                      images: io.Autogrow.Type, seed: int) -> io.NodeOutput:
        if not prompt or not prompt.strip():
            raise ValueError("편집 프롬프트를 입력해주세요.")

        image_list: list[torch.Tensor] = []
        for v in images.values():
            if v is not None and isinstance(v, torch.Tensor):
                image_list.append(v)

        if not image_list:
            raise ValueError("편집할 이미지를 1장 이상 연결해주세요.")

        loop = asyncio.get_event_loop()
        result_images, text = await loop.run_in_executor(
            None, lambda: model.edit_image(prompt, image_list, config, seed=seed)
        )

        if result_images is None:
            result_images = torch.zeros((1, 512, 512, 3))
            text = text or "이미지 편집에 실패했습니다."

        return io.NodeOutput(result_images, text or "", ui=ui.PreviewImage(result_images))
