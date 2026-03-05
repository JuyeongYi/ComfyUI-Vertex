"""모델 패키지 — 레지스트리 제공."""

from .base import BaseModel, ImageModel, Capability


def _get_image_models() -> dict[str, type[ImageModel]]:
    from .gemini_flash_image import Gemini_3_1_FlashImage
    return {
        Gemini_3_1_FlashImage.get_label(): Gemini_3_1_FlashImage,
    }


def get_image_model_names() -> list[str]:
    return list(_get_image_models().keys())


def create_image_model(name: str) -> ImageModel:
    return _get_image_models()[name]()
