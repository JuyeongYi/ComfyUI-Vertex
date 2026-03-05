"""NanoBanana 상수 정의."""

from enum import StrEnum


class AspectRatio(StrEnum):
    AUTO = "auto"
    R_1_1 = "1:1"
    R_2_3 = "2:3"
    R_3_2 = "3:2"
    R_3_4 = "3:4"
    R_4_3 = "4:3"
    R_4_5 = "4:5"
    R_5_4 = "5:4"
    R_9_16 = "9:16"
    R_16_9 = "16:9"
    R_21_9 = "21:9"


class ImageSize(StrEnum):
    K1 = "1K"
    K2 = "2K"
    K4 = "4K"


class ResponseModality(StrEnum):
    IMAGE_TEXT = "IMAGE+TEXT"
    IMAGE = "IMAGE"


class ThinkingLevel(StrEnum):
    MINIMAL = "MINIMAL"
    HIGH = "HIGH"


MODEL_ID = "gemini-3.1-flash-image-preview"

DEFAULT_SYSTEM_PROMPT = (
    "You are an expert image-generation engine. You must ALWAYS produce an image.\n"
    "Interpret all user input as literal visual directives for image composition.\n"
    "If a prompt lacks specific visual details, creatively invent a concrete visual scenario.\n"
    "Prioritize generating the visual representation above any text or conversational requests."
)
