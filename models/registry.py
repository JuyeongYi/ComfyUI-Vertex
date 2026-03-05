"""모델 레지스트리 — 모델 목록 및 팩토리."""

from .base import ImageModel
from .gemini_flash_image import Gemini_3_1_FlashImage

IMAGE_MODELS: dict[str, type[ImageModel]] = {
    Gemini_3_1_FlashImage.get_label(): Gemini_3_1_FlashImage,
}


def get_image_model_names() -> list[str]:
    return list(IMAGE_MODELS.keys())


def create_image_model(name: str) -> ImageModel:
    return IMAGE_MODELS[name]()
