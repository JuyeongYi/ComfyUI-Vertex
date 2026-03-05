# ComfyUI-NanoBanana 노드 설계

## 목적

Gemini 3.1 Flash Image Preview 모델을 ComfyUI에서 직접 사용할 수 있는 커스텀 노드 확장.
ComfyUI 기본 Nano Banana 노드 대비 사용성 향상이 핵심 목표.

## 차별점

- ComfyUI 프록시/구독 불필요 — Google API Key로 직접 호출
- Config 노드 + 프리셋 저장/로드
- Autogrow 이미지 입력으로 편집 시 이미지 순서 명시적 제어
- auth.py 분리 — 향후 1Password 등 런타임 키 주입 대비

## 프로젝트 구조

```
ComfyUI-NanoBanana/
├── __init__.py              # ComfyExtension 엔트리포인트
├── auth.py                  # API Key 취득 (별도 분리)
├── gemini_client.py         # google-genai SDK 래퍼
├── nodes/
│   ├── __init__.py          # 노드 클래스 재내보내기
│   ├── config.py            # NB_Config
│   ├── generate.py          # NB_Generate
│   └── edit.py              # NB_Edit
├── presets/                  # 프리셋 JSON 저장 디렉토리
│   └── .gitkeep
├── requirements.txt
└── pyproject.toml
```

## 노드 설계

### NB_Config

설정 + 프리셋 관리 노드.

**입력:**
- `aspect_ratio` (COMBO: auto, 1:1, 16:9, 9:16, 4:3, 3:4, 2:3, 3:2, 4:5, 5:4, 21:9)
- `image_size` (COMBO: 512, 1K, 2K, 4K)
- `response_modalities` (COMBO: IMAGE+TEXT, IMAGE)
- `thinking_level` (COMBO: MINIMAL, HIGH)
- `system_prompt` (STRING, multiline, optional, advanced)
- `preset_name` (COMBO: 프리셋 목록 동적 로드)
- `save_as` (STRING, optional) — 입력 시 현재 설정을 JSON으로 저장

**출력:**
- `NB_CONFIG` (커스텀 타입, dict)

**동작:**
- preset_name 선택 시 해당 프리셋 값 로드
- save_as에 이름 입력하면 현재 설정을 `presets/{name}.json`으로 저장
- API Key는 노드에 노출하지 않음 (메타데이터 저장 방지)

### NB_Generate

텍스트 → 이미지 생성.

**입력:**
- `config` (NB_CONFIG)
- `prompt` (STRING, multiline)
- `seed` (INT)

**출력:**
- `IMAGE` — 생성된 이미지 (여러 장이면 배치)
- `STRING` — Gemini 텍스트 응답

### NB_Edit

이미지 편집. Autogrow로 다중 이미지 입력.

**입력:**
- `config` (NB_CONFIG)
- `prompt` (STRING, multiline) — 편집 지시
- `images` (Autogrow, IMAGE, min=1, max=14)
- `seed` (INT)

**출력:**
- `IMAGE` — 편집된 이미지 (여러 장이면 배치)
- `STRING` — Gemini 텍스트 응답

## auth.py

```python
def get_api_key() -> str:
    """API Key 취득. 현재: .env / 환경변수. 향후: 1Password CLI."""
```

- `.env` 파일에서 `GEMINI_API_KEY` 로드 (python-dotenv)
- 환경변수 `GEMINI_API_KEY` 폴백
- 키 없으면 명확한 에러 메시지

## gemini_client.py

google-genai SDK를 래핑하여 노드에서 사용.

- `generate_image(prompt, config) -> (images, text)`
- `edit_image(prompt, images, config) -> (images, text)`
- 이미지 변환: ComfyUI IMAGE 텐서 ↔ Gemini inline_data (base64)

## 데이터 흐름

```
[NB_Config] ──NB_CONFIG──→ [NB_Generate] ──IMAGE──→ [NB_Edit] ──IMAGE──→ ...
                    │                        └─STRING    │         └─STRING
                    └──NB_CONFIG─────────────────────────┘
```

## 의존성

- google-genai
- python-dotenv
- torch (ComfyUI 제공)

## API 호출 방식

Express Mode (API Key) — google-genai SDK 사용:
```python
client = genai.Client(vertexai=True, api_key=api_key)
response = client.models.generate_content(
    model="gemini-3.1-flash-image-preview",
    contents=...,
    config=types.GenerateContentConfig(
        response_modalities=['IMAGE', 'TEXT'],
        image_config=types.ImageConfig(aspect_ratio=..., image_size=...),
    ),
)
```

Location은 `global` (글로벌 엔드포인트만 지원).
