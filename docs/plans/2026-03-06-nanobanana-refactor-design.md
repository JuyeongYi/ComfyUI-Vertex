# ComfyUI-NanoBanana 리팩토링 설계

> **목표:** 단일 Gemini 이미지 생성 확장 → VertexAI 범용 확장으로 구조 전환.
> 현재 스코프: 구조만 전환. 모델은 Gemini Flash Image 하나만 유지.

---

## 아키텍처 개요

### 두 계층의 분리

**내부 파이썬 계층 (models/)** — 순수 로직. ComfyUI를 모름.

```
BaseModel (ABC)
├── model_id: str
├── capabilities: set[Capability]
│
├── ImageModel(BaseModel) — ABC
│   ├── generate_image(prompt, config, seed) → (Tensor | None, str)
│   └── edit_image(prompt, images, config, seed) → (Tensor | None, str)
│
├── TextModel(BaseModel)       ← 향후
├── VideoModel(BaseModel)      ← 향후
└── DeployedModel(BaseModel)   ← 향후
```

**ComfyUI 노드 계층 (nodes/)** — UI 껍데기. 모델 인스턴스를 생성/전달.

- Model 노드: 모델 선택 + 모델별 설정 → Model 객체 출력
- Config 노드: Action 관련 범용 설정 (aspect_ratio, image_size 등)
- Action 노드: Model + Config 입력 → `model.method()` 호출로 위임

노드는 `io.ComfyNode`만 상속. 모델 클래스와 상속 관계 없음.

### 노드 흐름

```
[NB Image Model]  ──→  [NB Image Generate]  ──→  IMAGE, text
   (모델 선택)          [NB Image Edit]      ──→  IMAGE, text
                             ↑
[NB Config]  ────────────────┘
   (범용 설정 + 프리셋)
```

---

## 인증

- API Key (Express Mode): `genai.Client(api_key=...)` — 현재 구현
- OAuth2: 향후 추가. `auth.py`에서 `get_client()` 확장

---

## ComfyUI 커스텀 타입

`nodes/types.py`에 정의. 순환 import 방지.

```python
NB_IMAGE_MODEL = io.Custom("NB_IMAGE_MODEL")
NB_TEXT_MODEL  = io.Custom("NB_TEXT_MODEL")   # 향후
NB_CONFIG      = io.Custom("NB_CONFIG")
```

같은 모델이 여러 타입의 Model 노드에 등장 가능 (예: Gemini Flash가 Image Model에도, Text Model에도).
ComfyUI 타입 시스템이 연결 제한을 강제하고, 내부적으로는 같은 모델 클래스.

---

## 파일 구조

```
__init__.py                     # ComfyExtension 엔트리포인트
auth.py                         # API Key (+ 향후 OAuth2)
const.py                        # StrEnum 상수 (AspectRatio, ImageSize 등)

models/
  __init__.py
  base.py                       # BaseModel(ABC), ImageModel(ABC), Capability enum
  gemini_flash_image.py         # GeminiFlashImage(ImageModel) — 현재 gemini_client.py 로직 이동

nodes/
  __init__.py                   # 노드 재내보내기
  types.py                      # NB_IMAGE_MODEL, NB_CONFIG 등 커스텀 타입
  model_image.py                # NB Image Model 노드
  config.py                     # NB Config 노드 (범용 설정 + 프리셋)
  generate.py                   # NB Image Generate 액션 노드
  edit.py                       # NB Image Edit 액션 노드

tests/
  test_auth.py                  # 기존 유지
presets/                        # 프리셋 JSON 저장소
```

### 삭제 대상
- `gemini_client.py` → `models/gemini_flash_image.py`로 이동

---

## Config 노드 설정 항목

Action 관련 범용 설정:

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| aspect_ratio | AspectRatio | auto | 출력 이미지 비율 |
| image_size | ImageSize | 1K | 출력 해상도 |
| response_modalities | ResponseModality | IMAGE+TEXT | 응답 형식 |
| thinking_level | ThinkingLevel | MINIMAL | 모델 사고 수준 |
| system_prompt | str | "" | 시스템 프롬프트 (빈값이면 기본값) |
| preset_name | Combo | (none) | 프리셋 로드 |
| save_as | str | "" | 프리셋 저장 |

모델별 설정 (모델 선택, 인증 등)은 Model 노드가 담당.
Action에 무관한 Config 항목은 모델이 무시.

---

## Model 노드 역할

- 모델 드롭다운 선택 (현재: Gemini 3.1 Flash Image Preview만)
- 모델 인스턴스 생성 → NB_IMAGE_MODEL 타입으로 출력
- 향후 모델별 고유 설정이 있으면 여기에 추가

---

## Action 노드 역할

- Model + Config + prompt (+ images) 입력
- `execute` 내부에서 `model.generate_image(...)` 또는 `model.edit_image(...)` 호출
- 결과 처리: None → fallback 빈 이미지, PreviewImage UI 출력
