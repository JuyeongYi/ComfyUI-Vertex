"""모델 기본 클래스 정의."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum, auto
from io import BytesIO

import numpy as np
import torch
from PIL import Image


class Capability(StrEnum):
    IMAGE = auto()
    TEXT = auto()
    VIDEO = auto()


class BaseModel(ABC):
    """모든 모델의 최상위 추상 클래스."""

    model_id: str
    display_name: str
    label: str | None = None

    def __init__(self) -> None:
        self.capabilities: set[Capability] = set()

    @classmethod
    def get_label(cls) -> str:
        if cls.label is not None:
            return cls.label
        import re
        return re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", cls.__name__)


class ImageModel(BaseModel):
    """이미지 생성/편집 모델 추상 클래스."""

    def __init__(self) -> None:
        super().__init__()
        self.capabilities.add(Capability.IMAGE)

    @abstractmethod
    def generate_image(
        self, prompt: str, config: dict, seed: int = 0,
    ) -> tuple[torch.Tensor | None, str]: ...

    @abstractmethod
    def edit_image(
        self, prompt: str, images: list[torch.Tensor], config: dict, seed: int = 0,
    ) -> tuple[torch.Tensor | None, str]: ...

    @staticmethod
    def tensor_to_bytes(tensor: torch.Tensor) -> bytes:
        """단일 이미지 텐서 [1,H,W,C] → PNG bytes."""
        arr = (tensor.squeeze(0).cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
        img = Image.fromarray(arr)
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    @staticmethod
    def bytes_to_tensor(data: bytes) -> torch.Tensor:
        """raw bytes (PNG/JPEG) → [1,H,W,C] float32 텐서."""
        img = Image.open(BytesIO(data)).convert("RGB")
        arr = np.array(img, dtype=np.float32) / 255.0
        return torch.from_numpy(arr).unsqueeze(0)
