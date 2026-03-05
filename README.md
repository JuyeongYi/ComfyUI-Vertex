# ComfyUI-Vertex

Gemini 3.1 Flash Image Preview 모델을 활용한 ComfyUI 이미지 생성/편집 커스텀 노드 확장.

## 설치

### 방법 1: Clone

```bash
cd ComfyUI/custom_nodes
git clone <repository-url> ComfyUI-Vertex
pip install -r ComfyUI-Vertex/requirements.txt
```

### 방법 2: Symlink

```bash
# Windows (관리자 권한)
mklink /D "ComfyUI\custom_nodes\ComfyUI-Vertex" "원본경로\ComfyUI-Vertex"

# Linux / macOS
ln -s /원본경로/ComfyUI-Vertex ComfyUI/custom_nodes/ComfyUI-Vertex
```

### 의존성

- `google-genai`
- `python-dotenv`

## API Key 설정

ComfyUI 루트 디렉토리에 `.env` 파일을 생성하고 Gemini API Key를 설정한다.

```
GEMINI_API_KEY=your_api_key_here
```

또는 환경변수로 직접 설정해도 된다.

API Key는 [Google AI Studio](https://aistudio.google.com/apikey)에서 발급받을 수 있다.

## 노드 설명

모든 노드는 ComfyUI의 **Vertex/Image** 카테고리에 위치한다.

### Vertex Image Model

이미지 생성/편집에 사용할 모델을 선택한다.

| 구분 | 내용 |
|------|------|
| **입력** | `model` - 모델 선택 (콤보박스) |
| **출력** | `model` - 모델 인스턴스 (VERTEX_IMAGE_MODEL) |

현재 지원 모델: **Gemini 3.1 Flash Image Preview** (`gemini-3.1-flash-image-preview`)

### Vertex Image Config

이미지 생성/편집 설정을 구성한다. 프리셋 저장/로드를 지원한다.

| 구분 | 내용 |
|------|------|
| **입력** | `aspect_ratio` - 출력 비율 (auto, 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9) |
| | `image_size` - 출력 해상도 (1K / 2K / 4K) |
| | `response_modalities` - 응답 형식 (IMAGE+TEXT: 이미지+텍스트 / IMAGE: 이미지만) |
| | `thinking_level` - 모델 사고 수준 (MINIMAL: 빠름 / HIGH: 정확하지만 느림) |
| | `system_prompt` - 시스템 프롬프트 (비워두면 기본 이미지 생성 프롬프트 사용) [고급] |
| | `preset_name` - 저장된 프리셋 로드 선택 |
| | `save_as` - 이름 입력 시 현재 설정을 프리셋으로 저장 |
| **출력** | `config` - 설정 딕셔너리 (VERTEX_CONFIG) |

### Vertex Image Generate

텍스트 프롬프트로 이미지를 생성한다.

| 구분 | 내용 |
|------|------|
| **입력** | `model` - Vertex Image Model 노드 연결 |
| | `config` - Vertex Image Config 노드 연결 |
| | `prompt` - 이미지 생성 프롬프트 (텍스트) |
| | `seed` - 시드값 |
| **출력** | `IMAGE` - 생성된 이미지 |
| | `text` - 모델 응답 텍스트 (response_modalities가 IMAGE+TEXT일 때) |

### Vertex Image Edit

기존 이미지를 텍스트 지시로 편집한다. 최대 14장의 이미지를 입력할 수 있다.

| 구분 | 내용 |
|------|------|
| **입력** | `model` - Vertex Image Model 노드 연결 |
| | `config` - Vertex Image Config 노드 연결 |
| | `prompt` - 편집 지시 프롬프트 (텍스트) |
| | `images` - 편집할 이미지 (1~14장, 자동 확장) |
| | `seed` - 시드값 |
| **출력** | `IMAGE` - 편집된 이미지 |
| | `text` - 모델 응답 텍스트 |

## 기본 워크플로우

### 이미지 생성

```
[Vertex Image Model] --model--> [Vertex Image Generate]
[Vertex Image Config] --config--> [Vertex Image Generate]
                                  prompt: "a cat sitting on a cloud"
```

### 이미지 편집

```
[Vertex Image Model] --model--> [Vertex Image Edit]
[Vertex Image Config] --config--> [Vertex Image Edit]
[Load Image / 다른 노드] --image--> [Vertex Image Edit]
                                    prompt: "change the background to sunset"
```

Generate의 출력 이미지를 Edit의 입력으로 연결하여 생성 후 편집하는 파이프라인도 구성할 수 있다.

## 프리셋 기능

자주 사용하는 설정 조합을 프리셋으로 저장하고 재사용할 수 있다.

### 저장

Vertex Image Config 노드에서 원하는 설정값을 지정한 뒤, `save_as` 필드에 프리셋 이름을 입력하고 실행하면 `presets/` 디렉토리에 JSON 파일로 저장된다.

### 로드

`preset_name` 콤보박스에서 저장된 프리셋을 선택하면 해당 설정이 적용된다. `(none)` 선택 시 위젯에 직접 입력한 값이 사용된다.

### 프리셋 파일 형식

```json
{
  "aspect_ratio": "16:9",
  "image_size": "1K",
  "response_modalities": "IMAGE",
  "thinking_level": "HIGH",
  "system_prompt": "커스텀 시스템 프롬프트"
}
```
