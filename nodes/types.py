"""ComfyUI 커스텀 타입 정의."""

from comfy_api.latest import io

VERTEX_IMAGE_MODEL = io.Custom("VERTEX_IMAGE_MODEL")
VERTEX_TEXT_MODEL = io.Custom("VERTEX_TEXT_MODEL")  # 향후
VERTEX_CONFIG = io.Custom("VERTEX_CONFIG")
