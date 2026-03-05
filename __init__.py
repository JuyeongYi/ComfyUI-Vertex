"""ComfyUI-NanoBanana: Gemini 3.1 Flash Image Preview 커스텀 노드."""

from comfy_api.latest import ComfyExtension, io
from typing_extensions import override

from .nodes import NBConfig, NBGenerate, NBEdit

_NODES = [
    NBConfig,
    NBGenerate,
    NBEdit,
]


class NanoBananaExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return _NODES


async def comfy_entrypoint() -> NanoBananaExtension:
    return NanoBananaExtension()
