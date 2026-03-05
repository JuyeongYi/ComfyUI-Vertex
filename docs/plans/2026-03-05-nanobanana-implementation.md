# ComfyUI-NanoBanana Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Gemini 3.1 Flash Image Preview를 직접 호출하는 ComfyUI 커스텀 노드 확장 구현.

**Architecture:** V3 schema (`comfy_api.latest`) 기반. auth.py로 API Key 분리, gemini_client.py로 SDK 래핑, nodes/에 3개 노드(Config, Generate, Edit). Config 노드에서 프리셋 저장/로드. Express Mode (API Key) → google-genai SDK → Gemini API 직접 호출.

**Tech Stack:** Python, google-genai SDK, python-dotenv, ComfyUI V3 API (`comfy_api.latest`), torch

---

### Task 1: 프로젝트 스캐폴딩

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `presets/.gitkeep`
- Create: `nodes/__init__.py` (빈 파일)

**Step 1: pyproject.toml 작성**

```toml
[project]
name = "comfyui-nanobanana"
version = "0.1.0"
description = "ComfyUI custom nodes for Gemini 3.1 Flash Image Preview (Nano Banana)"
license = "MIT"
dependencies = ["google-genai", "python-dotenv"]

[tool.comfy]
PublisherId = "nanobanana"
DisplayName = "NanoBanana"
Icon = ""
```

**Step 2: requirements.txt 작성**

```
google-genai
python-dotenv
```

**Step 3: .gitignore 작성**

```
__pycache__/
*.pyc
.env
presets/*.json
!presets/.gitkeep
```

**Step 4: 디렉토리 생성**

```bash
mkdir -p presets nodes
touch presets/.gitkeep nodes/__init__.py
```

**Step 5: git init & 커밋**

```bash
git init
git add pyproject.toml requirements.txt .gitignore presets/.gitkeep nodes/__init__.py
git commit -m "chore: scaffold project structure"
```

---

### Task 2: auth.py — API Key 관리

**Files:**
- Create: `auth.py`
- Create: `tests/test_auth.py`

**Step 1: 테스트 작성**

```python
# tests/test_auth.py
import os
import pytest
from unittest.mock import patch

def test_get_api_key_from_env_var():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-123"}):
        from auth import get_api_key
        assert get_api_key() == "test-key-123"

def test_get_api_key_missing_raises():
    with patch.dict(os.environ, {}, clear=True):
        from auth import get_api_key
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
            get_api_key()
```

**Step 2: 테스트 실행 → 실패 확인**

```bash
cd C:/Users/Jooyo/source/ComfyUI-NanoBanana
python -m pytest tests/test_auth.py -v
```

Expected: FAIL — `auth` 모듈 없음

**Step 3: auth.py 구현**

```python
"""API Key 관리. 향후 1Password 등 런타임 키 주입으로 교체 가능."""

import os
from pathlib import Path

from dotenv import load_dotenv

# ComfyUI 루트의 .env 로드
_COMFYUI_ROOT = Path(__file__).parent.parent.parent
load_dotenv(_COMFYUI_ROOT / ".env")


def get_api_key() -> str:
    """Gemini API Key를 반환한다.

    탐색 순서:
    1. 환경변수 GEMINI_API_KEY
    2. ComfyUI 루트 .env 파일의 GEMINI_API_KEY

    향후 이 함수만 수정하면 1Password 등 외부 소스에서 키를 가져올 수 있다.
    """
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY가 설정되지 않았습니다. "
            "ComfyUI 루트의 .env 파일에 GEMINI_API_KEY=... 를 추가하거나 "
            "환경변수로 설정하세요."
        )
    return key
```

**Step 4: 테스트 실행 → 통과 확인**

```bash
python -m pytest tests/test_auth.py -v
```

Expected: PASS

**Step 5: 커밋**

```bash
git add auth.py tests/test_auth.py
git commit -m "feat: add auth.py for API key management"
```

---

### Task 3: gemini_client.py — SDK 래퍼

**Files:**
- Create: `gemini_client.py`

**Step 1: gemini_client.py 구현**

핵심 기능:
- ComfyUI IMAGE 텐서 (`[B,H,W,C]` float32) ↔ base64 PNG 변환
- google-genai SDK 호출 래핑
- 응답에서 이미지/텍스트 파싱

```python
"""Gemini 3.1 Flash Image Preview SDK 래퍼."""

from __future__ import annotations

import base64
from io import BytesIO
from typing import Any

import numpy as np
import torch
from PIL import Image

from google import genai
from google.genai import types

from .auth import get_api_key

MODEL_ID = "gemini-3.1-flash-image-preview"
LOCATION = "global"

DEFAULT_SYSTEM_PROMPT = (
    "You are an expert image-generation engine. You must ALWAYS produce an image.\n"
    "Interpret all user input as literal visual directives for image composition.\n"
    "If a prompt lacks specific visual details, creatively invent a concrete visual scenario.\n"
    "Prioritize generating the visual representation above any text or conversational requests."
)


def _get_client() -> genai.Client:
    """google-genai Client 생성."""
    return genai.Client(vertexai=True, api_key=get_api_key())


def _tensor_to_base64(tensor: torch.Tensor) -> str:
    """단일 이미지 텐서 [1,H,W,C] → base64 PNG 문자열."""
    arr = (tensor.squeeze(0).cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
    img = Image.fromarray(arr)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _base64_to_tensor(b64: str) -> torch.Tensor:
    """base64 PNG/JPEG 데이터 → [1,H,W,C] float32 텐서."""
    data = base64.b64decode(b64)
    img = Image.open(BytesIO(data)).convert("RGB")
    arr = np.array(img, dtype=np.float32) / 255.0
    return torch.from_numpy(arr).unsqueeze(0)


def _build_config(config: dict) -> types.GenerateContentConfig:
    """NB_CONFIG dict → GenerateContentConfig."""
    modalities_str = config.get("response_modalities", "IMAGE+TEXT")
    if modalities_str == "IMAGE":
        modalities = ["IMAGE"]
    else:
        modalities = ["TEXT", "IMAGE"]

    image_config_kwargs: dict[str, Any] = {}
    aspect_ratio = config.get("aspect_ratio", "auto")
    if aspect_ratio != "auto":
        image_config_kwargs["aspect_ratio"] = aspect_ratio
    image_size = config.get("image_size", "1K")
    if image_size:
        image_config_kwargs["image_size"] = image_size

    gc = types.GenerateContentConfig(
        response_modalities=modalities,
        image_config=types.ImageConfig(**image_config_kwargs) if image_config_kwargs else None,
    )

    thinking_level = config.get("thinking_level")
    if thinking_level:
        gc.thinking_config = types.ThinkingConfig(thinking_level=thinking_level)

    return gc


def _build_system_instruction(config: dict) -> str | None:
    """시스템 프롬프트 반환. 비어있으면 기본값 사용."""
    sp = config.get("system_prompt", "")
    return sp if sp else DEFAULT_SYSTEM_PROMPT


def _parse_response(response) -> tuple[torch.Tensor | None, str]:
    """Gemini 응답에서 이미지 텐서와 텍스트를 추출."""
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
                tensor = _base64_to_tensor(part.inline_data.data)
                image_tensors.append(tensor)

    images = torch.cat(image_tensors, dim=0) if image_tensors else None
    text = "\n".join(text_parts)
    return images, text


def generate_image(prompt: str, config: dict, seed: int = 0) -> tuple[torch.Tensor | None, str]:
    """텍스트 → 이미지 생성."""
    client = _get_client()
    gc = _build_config(config)
    sys_prompt = _build_system_instruction(config)

    contents: list[Any] = [prompt]
    if sys_prompt:
        gc.system_instruction = sys_prompt

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=contents,
        config=gc,
    )
    return _parse_response(response)


def edit_image(
    prompt: str,
    images: list[torch.Tensor],
    config: dict,
    seed: int = 0,
) -> tuple[torch.Tensor | None, str]:
    """이미지 + 텍스트 → 편집된 이미지 생성."""
    client = _get_client()
    gc = _build_config(config)
    sys_prompt = _build_system_instruction(config)

    # 이미지를 Part로 변환
    parts: list[Any] = []
    for img_tensor in images:
        b64 = _tensor_to_base64(img_tensor)
        parts.append(types.Part.from_bytes(
            data=base64.b64decode(b64),
            mime_type="image/png",
        ))
    parts.append(prompt)

    if sys_prompt:
        gc.system_instruction = sys_prompt

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=parts,
        config=gc,
    )
    return _parse_response(response)
```

**Step 2: 커밋**

```bash
git add gemini_client.py
git commit -m "feat: add gemini_client.py SDK wrapper"
```

---

### Task 4: nodes/config.py — NB_Config 노드

**Files:**
- Create: `nodes/config.py`

**Step 1: 프리셋 유틸 + Config 노드 구현**

```python
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
                               tooltip="모델 사고 수준. HIGH: 더 정확하지만 느림"),
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
                # 프리셋에 없는 필드는 현재 위젯 값으로 폴백
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
```

**Step 2: 커밋**

```bash
git add nodes/config.py
git commit -m "feat: add NB_Config node with preset save/load"
```

---

### Task 5: nodes/generate.py — NB_Generate 노드

**Files:**
- Create: `nodes/generate.py`

**Step 1: NB_Generate 구현**

```python
"""NB_Generate — 텍스트 → 이미지 생성 노드."""

from __future__ import annotations

import torch
from comfy_api.latest import io, ui

from .config import NB_CONFIG
from ..gemini_client import generate_image


class NBGenerate(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="NB_Generate",
            display_name="NanoBanana Generate",
            category="NanoBanana",
            description="텍스트 프롬프트로 이미지를 생성합니다. "
                        "Gemini 3.1 Flash Image Preview를 직접 호출합니다.",
            is_output_node=True,
            inputs=[
                NB_CONFIG.Input("config", tooltip="NanoBanana Config 노드 연결"),
                io.String.Input("prompt", multiline=True, default="",
                                tooltip="이미지 생성 프롬프트"),
                io.Int.Input("seed", default=0, min=0, max=0xFFFFFFFFFFFFFFFF,
                             control_after_generate=True,
                             tooltip="시드값. 동일 시드로 재현 가능한 결과를 시도합니다"),
            ],
            outputs=[
                io.Image.Output(display_name="IMAGE"),
                io.String.Output(display_name="text"),
            ],
        )

    @classmethod
    def execute(cls, config: dict, prompt: str, seed: int) -> io.NodeOutput:
        if not prompt or not prompt.strip():
            raise ValueError("프롬프트를 입력해주세요.")

        images, text = generate_image(prompt, config, seed=seed)

        if images is None:
            images = torch.zeros((1, 512, 512, 3))
            text = text or "이미지 생성에 실패했습니다."

        return io.NodeOutput(images, text or "", ui=ui.PreviewImage(images))
```

**Step 2: 커밋**

```bash
git add nodes/generate.py
git commit -m "feat: add NB_Generate node"
```

---

### Task 6: nodes/edit.py — NB_Edit 노드

**Files:**
- Create: `nodes/edit.py`

**Step 1: NB_Edit 구현 (Autogrow 이미지 입력)**

```python
"""NB_Edit — 이미지 편집 노드. Autogrow로 최대 14장 이미지 입력."""

from __future__ import annotations

import torch
from comfy_api.latest import io, ui

from .config import NB_CONFIG
from ..gemini_client import edit_image


class NBEdit(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="NB_Edit",
            display_name="NanoBanana Edit",
            category="NanoBanana",
            description="이미지를 텍스트 지시로 편집합니다. "
                        "최대 14장의 이미지를 순서대로 입력할 수 있습니다. "
                        "Gemini 3.1 Flash Image Preview를 직접 호출합니다.",
            is_output_node=True,
            inputs=[
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
    def execute(cls, config: dict, prompt: str, images: io.Autogrow.Type,
                seed: int) -> io.NodeOutput:
        if not prompt or not prompt.strip():
            raise ValueError("편집 프롬프트를 입력해주세요.")

        # Autogrow dict → 이미지 텐서 리스트 (순서 유지)
        image_list: list[torch.Tensor] = []
        for v in images.values():
            if v is not None and isinstance(v, torch.Tensor):
                image_list.append(v)

        if not image_list:
            raise ValueError("편집할 이미지를 1장 이상 연결해주세요.")

        result_images, text = edit_image(prompt, image_list, config, seed=seed)

        if result_images is None:
            result_images = torch.zeros((1, 512, 512, 3))
            text = text or "이미지 편집에 실패했습니다."

        return io.NodeOutput(result_images, text or "", ui=ui.PreviewImage(result_images))
```

**Step 2: 커밋**

```bash
git add nodes/edit.py
git commit -m "feat: add NB_Edit node with Autogrow image inputs"
```

---

### Task 7: nodes/__init__.py + __init__.py — 엔트리포인트 조립

**Files:**
- Modify: `nodes/__init__.py`
- Create: `__init__.py` (루트)

**Step 1: nodes/__init__.py 재내보내기**

```python
"""nodes 서브패키지 — 노드 클래스 재내보내기."""

from .config import NBConfig, NB_CONFIG
from .generate import NBGenerate
from .edit import NBEdit

__all__ = [
    "NBConfig",
    "NBGenerate",
    "NBEdit",
    "NB_CONFIG",
]
```

**Step 2: 루트 __init__.py (ComfyExtension 엔트리포인트)**

```python
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
```

**Step 3: 커밋**

```bash
git add nodes/__init__.py __init__.py
git commit -m "feat: wire up ComfyExtension entrypoint"
```

---

### Task 8: 통합 테스트 — ComfyUI에서 실행 확인

**Step 1: 심볼릭 링크 생성 (ComfyUI custom_nodes에 연결)**

```bash
# Windows — 관리자 권한 필요
mklink /D "C:\Users\Jooyo\source\ComfyUI\custom_nodes\ComfyUI-NanoBanana" "C:\Users\Jooyo\source\ComfyUI-NanoBanana"
```

**Step 2: 의존성 설치**

```bash
pip install google-genai python-dotenv
```

**Step 3: .env 설정**

ComfyUI 루트 `.env`에 추가:
```
GEMINI_API_KEY=your_actual_api_key_here
```

**Step 4: ComfyUI 실행 → 노드 확인**

1. ComfyUI 시작
2. 노드 검색에서 "NanoBanana" 검색
3. 3개 노드 확인: Config, Generate, Edit
4. Config → Generate 연결 → 프롬프트 입력 → 실행 → 이미지 생성 확인
5. Config → Edit 연결 → 이미지 입력 + 편집 프롬프트 → 실행 → 편집 확인

**Step 5: 최종 커밋**

```bash
git add -A
git commit -m "feat: complete NanoBanana v0.1.0 — Gemini 3.1 Flash Image nodes"
```
