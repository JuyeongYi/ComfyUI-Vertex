# ComfyUI-NanoBanana 리팩토링 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 단일 Gemini 이미지 확장 → 확장 가능한 VertexAI 아키텍처로 구조 전환. 모델은 Gemini Flash Image만 유지.

**Architecture:** BaseModel → ImageModel → GeminiFlashImage 3중 모델 계층. ComfyUI 노드는 Model/Config/Action으로 분리. Action 노드가 Model 인스턴스에 위임. models/는 순수 로직, nodes/는 UI 껍데기.

**Tech Stack:** Python, google-genai SDK, ComfyUI V3 API (`comfy_api.latest`), torch, pytest

---

### Task 1: models/base.py — BaseModel + ImageModel ABC

**Files:**
- Create: `models/__init__.py`
- Create: `models/base.py`
- Create: `tests/test_models_base.py`

**Step 1: 테스트 작성**

```python
# tests/test_models_base.py
import pytest
import torch
import numpy as np
from models.base import BaseModel, ImageModel, Capability


def test_base_model_cannot_instantiate():
    with pytest.raises(TypeError):
        BaseModel()


def test_image_model_cannot_instantiate():
    with pytest.raises(TypeError):
        ImageModel()


def test_image_model_has_image_capability():
    assert Capability.IMAGE in ImageModel.capabilities


def test_tensor_to_bytes_roundtrip():
    # 작은 테스트 이미지 생성 [1, 4, 4, 3]
    tensor = torch.rand(1, 4, 4, 3)
    img_bytes = ImageModel.tensor_to_bytes(tensor)
    assert isinstance(img_bytes, bytes)
    assert len(img_bytes) > 0

    result = ImageModel.bytes_to_tensor(img_bytes)
    assert result.shape == (1, 4, 4, 3)
    # PNG 압축으로 인한 uint8 반올림 오차 허용
    np.testing.assert_allclose(
        tensor.numpy(), result.numpy(), atol=1.0 / 255 + 1e-5
    )
```

**Step 2: 테스트 실행 → 실패 확인**

```bash
cd C:/Users/Jooyo/source/ComfyUI-NanoBanana
python -m pytest tests/test_models_base.py -v
```

Expected: FAIL — `models.base` 모듈 없음

**Step 3: models/base.py 구현**

```python
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
    capabilities: set[Capability]

    @abstractmethod
    def __init__(self) -> None: ...


class ImageModel(BaseModel):
    """이미지 생성/편집 모델 추상 클래스."""

    capabilities: set[Capability] = {Capability.IMAGE}

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
```

`models/__init__.py`는 빈 파일로 생성.

**Step 4: 테스트 실행 → 통과 확인**

```bash
python -m pytest tests/test_models_base.py -v
```

Expected: PASS

**Step 5: 커밋**

```bash
git add models/__init__.py models/base.py tests/test_models_base.py
git commit -m "feat: add BaseModel + ImageModel ABC with Capability enum"
```

---

### Task 2: models/gemini_flash_image.py — GeminiFlashImage 구현

**Files:**
- Create: `models/gemini_flash_image.py`
- Modify: `models/__init__.py`

**Step 1: GeminiFlashImage 구현**

`gemini_client.py`의 로직을 ImageModel 인터페이스로 이동.

```python
"""Gemini 3.1 Flash Image Preview 모델 구현."""

from __future__ import annotations

from typing import Any

import torch
from google import genai
from google.genai import types

from ..auth import get_api_key
from ..const import (
    MODEL_ID,
    DEFAULT_SYSTEM_PROMPT,
    AspectRatio,
    ResponseModality,
)
from .base import ImageModel


class GeminiFlashImage(ImageModel):
    """Gemini 3.1 Flash Image Preview — 이미지 생성/편집."""

    model_id = MODEL_ID
    display_name = "Gemini 3.1 Flash Image Preview"

    def __init__(self) -> None:
        self._client = genai.Client(api_key=get_api_key())

    def generate_image(
        self, prompt: str, config: dict, seed: int = 0,
    ) -> tuple[torch.Tensor | None, str]:
        gc = self._build_config(config)
        sys_prompt = self._build_system_instruction(config)
        if sys_prompt:
            gc.system_instruction = sys_prompt

        response = self._client.models.generate_content(
            model=self.model_id,
            contents=[prompt],
            config=gc,
        )
        return self._parse_response(response)

    def edit_image(
        self, prompt: str, images: list[torch.Tensor], config: dict, seed: int = 0,
    ) -> tuple[torch.Tensor | None, str]:
        gc = self._build_config(config)
        sys_prompt = self._build_system_instruction(config)

        parts: list[Any] = []
        for img_tensor in images:
            img_bytes = self.tensor_to_bytes(img_tensor)
            parts.append(types.Part.from_bytes(
                data=img_bytes,
                mime_type="image/png",
            ))
        parts.append(prompt)

        if sys_prompt:
            gc.system_instruction = sys_prompt

        response = self._client.models.generate_content(
            model=self.model_id,
            contents=parts,
            config=gc,
        )
        return self._parse_response(response)

    def _build_config(self, config: dict) -> types.GenerateContentConfig:
        modalities_str = config.get("response_modalities", ResponseModality.IMAGE_TEXT)
        if modalities_str == ResponseModality.IMAGE:
            modalities = ["IMAGE"]
        else:
            modalities = ["TEXT", "IMAGE"]

        image_config_kwargs: dict[str, Any] = {}
        aspect_ratio = config.get("aspect_ratio", AspectRatio.AUTO)
        if aspect_ratio != AspectRatio.AUTO:
            image_config_kwargs["aspect_ratio"] = aspect_ratio
        image_size = config.get("image_size", "1K")
        if image_size:
            image_config_kwargs["image_size"] = image_size

        gc = types.GenerateContentConfig(
            response_modalities=modalities,
            image_config=types.ImageConfig(**image_config_kwargs) if image_config_kwargs else None,
        )

        thinking_level = config.get("thinking_level")
        if thinking_level and thinking_level != "NONE":
            gc.thinking_config = types.ThinkingConfig(thinking_level=thinking_level)

        return gc

    def _build_system_instruction(self, config: dict) -> str | None:
        sp = config.get("system_prompt", "")
        return sp if sp else DEFAULT_SYSTEM_PROMPT

    def _parse_response(self, response) -> tuple[torch.Tensor | None, str]:
        image_tensors: list[torch.Tensor] = []
        text_parts: list[str] = []

        if not response.candidates:
            return None, "Gemini API returned no response candidates."

        for candidate in response.candidates:
            if candidate.finish_reason and candidate.finish_reason != types.FinishReason.STOP:
                continue
            if not candidate.content or not candidate.content.parts:
                continue
            for part in candidate.content.parts:
                if hasattr(part, "thought") and part.thought:
                    continue
                if part.text:
                    text_parts.append(part.text)
                if part.inline_data and part.inline_data.data:
                    tensor = self.bytes_to_tensor(part.inline_data.data)
                    image_tensors.append(tensor)

        images = torch.cat(image_tensors, dim=0) if image_tensors else None
        text = "\n".join(text_parts)
        return images, text
```

**Step 2: models/__init__.py — 모델 레지스트리**

```python
"""모델 패키지 — 레지스트리 제공."""

from .base import BaseModel, ImageModel, Capability
from .gemini_flash_image import GeminiFlashImage

IMAGE_MODELS: dict[str, type[ImageModel]] = {
    GeminiFlashImage.display_name: GeminiFlashImage,
}


def get_image_model_names() -> list[str]:
    return list(IMAGE_MODELS.keys())


def create_image_model(name: str) -> ImageModel:
    return IMAGE_MODELS[name]()
```

**Step 3: 커밋**

```bash
git add models/gemini_flash_image.py models/__init__.py
git commit -m "feat: add GeminiFlashImage model + registry"
```

---

### Task 3: nodes/types.py — ComfyUI 커스텀 타입

**Files:**
- Create: `nodes/types.py`

**Step 1: 커스텀 타입 정의**

```python
"""ComfyUI 커스텀 타입 정의."""

from comfy_api.latest import io

NB_IMAGE_MODEL = io.Custom("NB_IMAGE_MODEL")
NB_TEXT_MODEL = io.Custom("NB_TEXT_MODEL")  # 향후
NB_CONFIG = io.Custom("NB_CONFIG")
```

**Step 2: 커밋**

```bash
git add nodes/types.py
git commit -m "feat: add ComfyUI custom type definitions"
```

---

### Task 4: nodes/model_image.py — NB Image Model 노드

**Files:**
- Create: `nodes/model_image.py`

**Step 1: NB Image Model 노드 구현**

```python
"""NB Image Model — 이미지 모델 선택 노드."""

from __future__ import annotations

from comfy_api.latest import io

from ..models import get_image_model_names, create_image_model
from .types import NB_IMAGE_MODEL


class NBImageModel(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="NB_ImageModel",
            display_name="NanoBanana Image Model",
            category="NanoBanana",
            description="이미지 생성/편집에 사용할 모델을 선택합니다.",
            inputs=[
                io.Combo.Input(
                    "model",
                    options=get_image_model_names(),
                    tooltip="사용할 이미지 모델 선택",
                ),
            ],
            outputs=[
                NB_IMAGE_MODEL.Output(display_name="model"),
            ],
        )

    @classmethod
    def execute(cls, model: str) -> io.NodeOutput:
        model_instance = create_image_model(model)
        return io.NodeOutput(model_instance)
```

**Step 2: 커밋**

```bash
git add nodes/model_image.py
git commit -m "feat: add NB Image Model node"
```

---

### Task 5: nodes/config.py — Config 노드 리팩토링

**Files:**
- Modify: `nodes/config.py`

**Step 1: NB_CONFIG를 types.py에서 import하도록 변경**

`nodes/config.py`에서:
- `NB_CONFIG = io.Custom("NB_CONFIG")` 삭제
- `from .types import NB_CONFIG` 추가
- `from ..const import ...` import 경로 유지 (이미 적용됨)

```python
"""NB_Config — 설정 + 프리셋 관리 노드."""

from __future__ import annotations

import json
from pathlib import Path

from comfy_api.latest import io

from ..const import AspectRatio, ImageSize, ResponseModality, ThinkingLevel
from .types import NB_CONFIG

_PRESETS_DIR = Path(__file__).parent.parent / "presets"


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
            description="Action 노드의 범용 설정. 프리셋 저장/로드 지원.",
            inputs=[
                io.Combo.Input("aspect_ratio", options=list(AspectRatio), default=AspectRatio.AUTO,
                               tooltip="출력 이미지 비율. auto: 입력 이미지 비율 따름 또는 기본값"),
                io.Combo.Input("image_size", options=list(ImageSize), default=ImageSize.K1,
                               tooltip="출력 해상도. 1K / 2K / 4K"),
                io.Combo.Input("response_modalities", options=list(ResponseModality), default=ResponseModality.IMAGE_TEXT,
                               tooltip="IMAGE: 이미지만 / IMAGE+TEXT: 이미지+텍스트 설명 함께 출력"),
                io.Combo.Input("thinking_level", options=list(ThinkingLevel), default=ThinkingLevel.MINIMAL,
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

        if save_as and save_as.strip():
            _save_preset(save_as.strip(), config)
            print(f"[NanoBanana] 프리셋 '{save_as.strip()}' 저장 완료")

        return io.NodeOutput(config)
```

**Step 2: 커밋**

```bash
git add nodes/config.py
git commit -m "refactor: config node uses types.py for NB_CONFIG"
```

---

### Task 6: nodes/generate.py — Image Generate 액션 노드 리팩토링

**Files:**
- Modify: `nodes/generate.py`

**Step 1: NB_IMAGE_MODEL 입력 + 모델에 위임하도록 변경**

```python
"""NB Image Generate — 텍스트 → 이미지 생성 액션 노드."""

from __future__ import annotations

import torch
from comfy_api.latest import io, ui

from ..models.base import ImageModel
from .types import NB_IMAGE_MODEL, NB_CONFIG


class NBImageGenerate(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="NB_ImageGenerate",
            display_name="NanoBanana Image Generate",
            category="NanoBanana",
            description="텍스트 프롬프트로 이미지를 생성합니다. "
                        "Model 노드에서 선택한 모델을 사용합니다.",
            is_output_node=True,
            inputs=[
                NB_IMAGE_MODEL.Input("model", tooltip="NanoBanana Image Model 노드 연결"),
                NB_CONFIG.Input("config", tooltip="NanoBanana Config 노드 연결"),
                io.String.Input("prompt", multiline=True, default="",
                                tooltip="이미지 생성 프롬프트"),
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
    def execute(cls, model: ImageModel, config: dict, prompt: str, seed: int) -> io.NodeOutput:
        if not prompt or not prompt.strip():
            raise ValueError("프롬프트를 입력해주세요.")

        images, text = model.generate_image(prompt, config, seed=seed)

        if images is None:
            images = torch.zeros((1, 512, 512, 3))
            text = text or "이미지 생성에 실패했습니다."

        return io.NodeOutput(images, text or "", ui=ui.PreviewImage(images))
```

**Step 2: 커밋**

```bash
git add nodes/generate.py
git commit -m "refactor: NB_ImageGenerate accepts model + delegates to ImageModel"
```

---

### Task 7: nodes/edit.py — Image Edit 액션 노드 리팩토링

**Files:**
- Modify: `nodes/edit.py`

**Step 1: NB_IMAGE_MODEL 입력 + 모델에 위임하도록 변경**

```python
"""NB Image Edit — 이미지 편집 액션 노드. Autogrow로 최대 14장 이미지 입력."""

from __future__ import annotations

import torch
from comfy_api.latest import io, ui

from ..models.base import ImageModel
from .types import NB_IMAGE_MODEL, NB_CONFIG


class NBImageEdit(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="NB_ImageEdit",
            display_name="NanoBanana Image Edit",
            category="NanoBanana",
            description="이미지를 텍스트 지시로 편집합니다. "
                        "최대 14장의 이미지를 순서대로 입력할 수 있습니다.",
            is_output_node=True,
            inputs=[
                NB_IMAGE_MODEL.Input("model", tooltip="NanoBanana Image Model 노드 연결"),
                NB_CONFIG.Input("config", tooltip="NanoBanana Config 노드 연결"),
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
    def execute(cls, model: ImageModel, config: dict, prompt: str,
                images: io.Autogrow.Type, seed: int) -> io.NodeOutput:
        if not prompt or not prompt.strip():
            raise ValueError("편집 프롬프트를 입력해주세요.")

        image_list: list[torch.Tensor] = []
        for v in images.values():
            if v is not None and isinstance(v, torch.Tensor):
                image_list.append(v)

        if not image_list:
            raise ValueError("편집할 이미지를 1장 이상 연결해주세요.")

        result_images, text = model.edit_image(prompt, image_list, config, seed=seed)

        if result_images is None:
            result_images = torch.zeros((1, 512, 512, 3))
            text = text or "이미지 편집에 실패했습니다."

        return io.NodeOutput(result_images, text or "", ui=ui.PreviewImage(result_images))
```

**Step 2: 커밋**

```bash
git add nodes/edit.py
git commit -m "refactor: NB_ImageEdit accepts model + delegates to ImageModel"
```

---

### Task 8: 엔트리포인트 조립 + gemini_client.py 삭제

**Files:**
- Modify: `nodes/__init__.py`
- Modify: `__init__.py`
- Delete: `gemini_client.py`

**Step 1: nodes/__init__.py 업데이트**

```python
"""nodes 서브패키지 — 노드 클래스 재내보내기."""

from .types import NB_IMAGE_MODEL, NB_CONFIG
from .model_image import NBImageModel
from .config import NBConfig
from .generate import NBImageGenerate
from .edit import NBImageEdit

__all__ = [
    "NB_IMAGE_MODEL",
    "NB_CONFIG",
    "NBImageModel",
    "NBConfig",
    "NBImageGenerate",
    "NBImageEdit",
]
```

**Step 2: 루트 __init__.py 업데이트**

```python
"""ComfyUI-NanoBanana: VertexAI 커스텀 노드 확장."""

from comfy_api.latest import ComfyExtension, io
from typing_extensions import override

from .nodes import NBImageModel, NBConfig, NBImageGenerate, NBImageEdit

_NODES = [
    NBImageModel,
    NBConfig,
    NBImageGenerate,
    NBImageEdit,
]


class NanoBananaExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return _NODES


async def comfy_entrypoint() -> NanoBananaExtension:
    return NanoBananaExtension()
```

**Step 3: gemini_client.py 삭제**

```bash
git rm gemini_client.py
```

**Step 4: 커밋**

```bash
git add nodes/__init__.py __init__.py
git commit -m "refactor: rewire entrypoints + remove gemini_client.py"
```

---

### Task 9: 통합 테스트 — import + ComfyUI 로드 확인

**Step 1: __pycache__ 정리**

```bash
find C:/Users/Jooyo/source/ComfyUI-NanoBanana -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
find C:/Users/Jooyo/source/ComfyUI/custom_nodes/ComfyUI-NanoBanana -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
```

**Step 2: 모듈 import 테스트**

```bash
cd C:/Users/Jooyo/source/ComfyUI
.venv/Scripts/python -c "
import sys
sys.path.insert(0, '.')
sys.path.insert(0, 'custom_nodes')
import importlib
mod = importlib.import_module('ComfyUI-NanoBanana')
print(f'Entrypoint: {mod.comfy_entrypoint}')
print(f'Nodes: {[n.__name__ for n in mod._NODES]}')
"
```

Expected:
```
Entrypoint: <function comfy_entrypoint at ...>
Nodes: ['NBImageModel', 'NBConfig', 'NBImageGenerate', 'NBImageEdit']
```

**Step 3: 기존 테스트 실행**

```bash
cd C:/Users/Jooyo/source/ComfyUI-NanoBanana
python -m pytest tests/ -v
```

Expected: 전체 PASS

**Step 4: 최종 커밋**

```bash
git add -A
git commit -m "refactor: complete NanoBanana architecture refactor — extensible VertexAI structure"
```
