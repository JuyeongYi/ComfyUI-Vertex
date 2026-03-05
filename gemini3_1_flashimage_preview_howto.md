# Gemini 3.1 Flash Image Preview - 사용법 가이드

> **출처**: Google Cloud Vertex AI Model Garden
> **모델 ID**: `gemini-3.1-flash-image-preview`
> **릴리스**: 2026-02-26 (Preview)
> **설명**: Text + Image Generation

---

## 모델 개요

Gemini 3.1 Flash Image는 고품질 이미지 생성 및 편집을 주류화한 모델이다.
Gemini 3 모델은 reasoning model로, 응답 전에 사고 과정을 거쳐 향상된 정확도와 이미지 품질을 제공한다.

### 주요 특징

- 향상된 이미지 품질 및 시각적 이해
- 다국어 긴 텍스트 렌더링 개선
- 향상된 사실성 (factuality)
- **512 (0.25MP) ~ 4K (16MP)** 해상도 이미지 생성 가능

---

## 모델 상세

| 속성 | 설명 |
|------|------|
| Model name | `gemini-3.1-flash-image-preview` |
| 지원 데이터 타입 | Input: text, text + images / Output: images, images + text |
| Token 제한 | Input: 128k / Output: 32k |
| Input 이미지 제한 | 최대 14개 입력 이미지를 1개 출력 이미지로 결합 가능 |

---

## 지원 기능

- Image Generation
- Multi-turn Image Editing (대화형 이미지 편집)
- Interleaved text and image generation (텍스트/이미지 교차 생성)
- Configurable Aspect Ratios (1:8 ~ 8:1)
- 512, 1K, 2K, 4K 해상도
- Grounding with Google Search (비용 발생)
- Batch Prediction
- Dynamic Shared Quotas
- Provisioned Throughput
- Global endpoint only

### 미지원 기능

- Tuning
- Configurable thinking levels
- Regional endpoints
- Context Caching

---

## 관련 모델

| 모델 | Input | Output | 단계 | 설명 |
|------|-------|--------|------|------|
| Gemini 3.1 Flash Image (Nano Banana Pro) | Text; Text + images | Images; Text + images | GA | 범용 멀티모달 모델, 빠른 창의적 이미지 생성/편집 |

---

## 사전 준비

1. **Vertex AI API 활성화**
2. Google Cloud 설정 완료 ([Get set up on Google Cloud](https://cloud.google.com/vertex-ai/generative-ai/docs/start/cloud-environment))

---

## 사용법 1: Vertex AI Studio (콘솔)

Vertex AI Studio의 채팅형 프롬프트 편집기에서 사용 가능.
1. **Open Vertex AI Studio** 클릭
2. 프롬프트 작성 후 **Submit** 클릭
3. Gemini 3.1 Flash Image Preview가 생성한 출력 확인

---

## 사용법 2: curl (REST API)

### 환경 변수 설정

```bash
MODEL_ID="gemini-3.1-flash-image-preview"
PROJECT_ID="YOUR_PROJECT_ID"
```

### 요청 전송

```bash
curl \
-X POST \
-H "Authorization: Bearer $(gcloud auth application-default print-access-token)" \
-H "Content-Type: application/json" \
https://aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/global/publishers/google/models/${MODEL_ID}:generateContent -d \
'{
  "contents": {
    "role": "user",
    "parts": {
        "text": "Generate a hyper-realistic infographic of a gourmet cheeseburger, deconstructed to show the texture of the toasted brioche bun, the seared crust of the patty, and the glistening melt of the cheese."
    }
  },
  "generation_config": {
      "response_modalities": ["TEXT", "IMAGE"]
  }
}'
```

### Express Mode (API Key 사용)

```bash
MODEL_ID="gemini-3.1-flash-image-preview"
API_KEY="YOUR_API_KEY"
```

동일한 curl 명령어에서 인증 방식만 API Key로 변경하여 사용.

---

## 사용법 3: Python (Google Gen AI SDK)

### 설치

```bash
pip3 install --upgrade --user google-genai
```

### 단일 이미지 생성 (Single-turn)

```python
from IPython.display import Image, Markdown, display
from google import genai
from google.genai import types
import os

PROJECT_ID = "YOUR_PROJECT_ID"
LOCATION = "global"

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

MODEL_ID = "gemini-3.1-flash-image-preview"

prompt = """
Generate a hyper-realistic infographic of a gourmet cheeseburger,
deconstructed to show the texture of the toasted brioche bun,
the seared crust of the patty, and the glistening melt of the cheese.
"""

response = client.models.generate_content(
    model=MODEL_ID,
    contents=prompt,
    config=types.GenerateContentConfig(
        response_modalities=['IMAGE', 'TEXT'],
        image_config=types.ImageConfig(
            aspect_ratio="16:9",
            image_size="2K",
        ),
    ),
)

# 에러 체크
if response.candidates[0].finish_reason != types.FinishReason.STOP:
    reason = response.candidates[0].finish_reason
    raise ValueError(f"Prompt Content Error: {reason}")

# 결과 표시
for part in response.candidates[0].content.parts:
    if part.thought:
        continue  # thinking 출력 건너뛰기
    if part.inline_data:
        display(Image(data=part.inline_data.data, width=1000))
```

### 대화형 이미지 편집 (Multi-turn Chat)

```python
from IPython.display import Image, Markdown, display
from google import genai
from google.genai import types
import os

PROJECT_ID = "YOUR_PROJECT_ID"
LOCATION = "global"

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

MODEL_ID = "gemini-3.1-flash-image-preview"

# 채팅 세션 생성
chat = client.chats.create(
    model=MODEL_ID,
    config=types.GenerateContentConfig(
        response_modalities=['TEXT', 'IMAGE'],
    )
)

# 1차: 이미지 생성
message = "Create an image of a clear perfume bottle sitting on a vanity."
response = chat.send_message(message)

for part in response.candidates[0].content.parts:
    if part.text:
        display(Markdown(part.text))
    if part.inline_data:
        display(Image(data=part.inline_data.data, width=500))

# 2차: 이미지 편집 (이전 대화 컨텍스트 유지)
message = "Make the perfume bottle purple and add a vase of hydrangeas next to the bottle."
response = chat.send_message(message)

for part in response.candidates[0].content.parts:
    if part.text:
        display(Markdown(part.text))
    if part.inline_data:
        display(Image(data=part.inline_data.data, width=500))
```

### Express Mode (API Key 사용)

```python
from google import genai
from google.genai import types

# API Key로 인증
client = genai.Client(vertexai=True, api_key="YOUR_API_KEY")

# 이후 사용법은 위와 동일
```

---

## 핵심 설정 옵션

### GenerateContentConfig

| 파라미터 | 설명 | 예시 |
|----------|------|------|
| `response_modalities` | 응답 형식 지정 | `['IMAGE', 'TEXT']` 또는 `['TEXT', 'IMAGE']` |
| `image_config.aspect_ratio` | 이미지 비율 (1:8 ~ 8:1) | `"16:9"`, `"1:1"`, `"4:3"` |
| `image_config.image_size` | 이미지 해상도 | `"512"`, `"1K"`, `"2K"`, `"4K"` |

### API Endpoint

```
https://aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/global/publishers/google/models/{MODEL_ID}:generateContent
```

- **Location**: `global` (글로벌 엔드포인트만 지원)

---

## 참조 링크

- [Gemini API reference](https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/gemini)
- [Gemini SDK reference](https://googleapis.github.io/python-genai/)
- [Generate and edit images with Gemini](https://cloud.google.com/vertex-ai/generative-ai/docs/image/generate-edit-images)
- [Google Gen AI SDK quickstart](https://cloud.google.com/vertex-ai/generative-ai/docs/sdks/overview)
