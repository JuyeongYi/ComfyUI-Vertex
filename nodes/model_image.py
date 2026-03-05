"""Vertex Image Model — 이미지 모델 선택 노드."""

from __future__ import annotations

from comfy_api.latest import io

from ..models import get_image_model_names, create_image_model
from .types import VERTEX_IMAGE_MODEL


class VertexImageModel(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Vertex_ImageModel",
            display_name="Vertex Image Model",
            category="Vertex/Image",
            description="이미지 생성/편집에 사용할 모델을 선택합니다.",
            inputs=[
                io.Combo.Input(
                    "model",
                    options=get_image_model_names(),
                    tooltip="사용할 이미지 모델 선택",
                ),
            ],
            outputs=[
                VERTEX_IMAGE_MODEL.Output(display_name="model"),
            ],
        )

    @classmethod
    def execute(cls, model: str) -> io.NodeOutput:
        model_instance = create_image_model(model)
        return io.NodeOutput(model_instance)
