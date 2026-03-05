"""NB_Config — 설정 + 프리셋 관리 노드."""

from __future__ import annotations

import json
from pathlib import Path

from comfy_api.latest import io

_PRESETS_DIR = Path(__file__).parent.parent / "presets"

NB_CONFIG = io.Custom("NB_CONFIG")

ASPECT_RATIOS = ["auto", "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]
IMAGE_SIZES = ["1K", "2K", "4K"]
RESPONSE_MODALITIES = ["IMAGE+TEXT", "IMAGE"]
THINKING_LEVELS = ["MINIMAL", "HIGH"]


def _list_presets() -> list[str]:
    _PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(p.stem for p in _PRESETS_DIR.glob("*.json"))


def _load_preset(name: str) -> dict:
    path = _PRESETS_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _save_preset(name: str, data: dict) -> None:
    _PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    path = _PRESETS_DIR / f"{name}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class NBConfig(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        presets = _list_presets()
        preset_options = ["(none)"] + presets
        return io.Schema(
            node_id="NB_Config",
            display_name="NanoBanana Config",
            category="NanoBanana",
            description="Gemini 3.1 Flash Image 설정. 프리셋 저장/로드 지원. "
                        "API Key는 ComfyUI 루트 .env 파일의 GEMINI_API_KEY로 관리됩니다.",
            inputs=[
                io.Combo.Input("aspect_ratio", options=ASPECT_RATIOS, default="auto",
                               tooltip="출력 이미지 비율. auto: 입력 이미지 비율 따름 또는 기본값"),
                io.Combo.Input("image_size", options=IMAGE_SIZES, default="1K",
                               tooltip="출력 해상도. 1K / 2K / 4K"),
                io.Combo.Input("response_modalities", options=RESPONSE_MODALITIES, default="IMAGE+TEXT",
                               tooltip="IMAGE: 이미지만 / IMAGE+TEXT: 이미지+텍스트 설명 함께 출력"),
                io.Combo.Input("thinking_level", options=THINKING_LEVELS, default="MINIMAL",
                               tooltip="모델 사고 수준. MINIMAL: 빠름 / HIGH: 더 정확하지만 느림"),
                io.String.Input("system_prompt", multiline=True, default="", optional=True,
                                tooltip="시스템 프롬프트. 비워두면 기본 이미지 생성 프롬프트 사용",
                                advanced=True),
                io.Combo.Input("preset_name", options=preset_options, default="(none)",
                               tooltip="저장된 프리셋 로드. (none)이면 현재 위젯 값 사용"),
                io.String.Input("save_as", default="", optional=True,
                                tooltip="이름 입력 시 현재 설정을 프리셋으로 저장"),
            ],
            outputs=[
                NB_CONFIG.Output(display_name="config"),
            ],
        )

    @classmethod
    def execute(cls, aspect_ratio, image_size, response_modalities,
                thinking_level, system_prompt="", preset_name="(none)", save_as="") -> io.NodeOutput:
        # 프리셋 로드
        if preset_name and preset_name != "(none)":
            try:
                config = _load_preset(preset_name)
                config.setdefault("aspect_ratio", aspect_ratio)
                config.setdefault("image_size", image_size)
                config.setdefault("response_modalities", response_modalities)
                config.setdefault("thinking_level", thinking_level)
                config.setdefault("system_prompt", system_prompt)
            except FileNotFoundError:
                print(f"[NanoBanana] 프리셋 '{preset_name}'을 찾을 수 없습니다. 위젯 값을 사용합니다.")
                config = {}
        else:
            config = {}

        if not config:
            config = {
                "aspect_ratio": aspect_ratio,
                "image_size": image_size,
                "response_modalities": response_modalities,
                "thinking_level": thinking_level,
                "system_prompt": system_prompt,
            }

        # 프리셋 저장
        if save_as and save_as.strip():
            _save_preset(save_as.strip(), config)
            print(f"[NanoBanana] 프리셋 '{save_as.strip()}' 저장 완료")

        return io.NodeOutput(config)
