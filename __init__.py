"""ComfyUI-Vertex: VertexAI 커스텀 노드 확장."""

from comfy_api.latest import ComfyExtension, io
from typing_extensions import override

from .nodes import VertexImageModel, VertexConfig, VertexImageGenerate, VertexImageEdit

_NODES = [
    VertexImageModel,
    VertexConfig,
    VertexImageGenerate,
    VertexImageEdit,
]


class VertexExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return _NODES


async def comfy_entrypoint() -> VertexExtension:
    return VertexExtension()
