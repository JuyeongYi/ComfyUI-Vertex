# 아키텍처 설계 문서

## 디렉토리 구조

```
ComfyUI-Vertex/
├── __init__.py              # ComfyExtension 진입점 (comfy_entrypoint)
├── auth.py                  # API 키 관리 + genai.Client 싱글턴
├── const.py                 # 상수 및 StrEnum 정의
├── conftest.py              # pytest 설정 (루트 __init__.py 우회)
├── pyproject.toml           # 프로젝트 메타데이터 + [tool.comfy] 설정
├── models/
│   ├── __init__.py          # base 클래스 재내보내기
│   ├── base.py              # BaseModel → ImageModel 추상 계층
│   ├── registry.py          # 모델 레지스트리 (eager import, 팩토리)
│   └── gemini_flash_image.py # Gemini 3.1 Flash Image 구현체
├── nodes/
│   ├── __init__.py          # 노드 클래스 재내보내기
│   ├── types.py             # io.Custom 타입 정의 (VERTEX_IMAGE_MODEL, VERTEX_CONFIG)
│   ├── model_image.py       # 모델 선택 노드
│   ├── config.py            # 설정 + 프리셋 노드
│   ├── generate.py          # 이미지 생성 액션 노드
│   └── edit.py              # 이미지 편집 액션 노드
├── presets/                 # JSON 프리셋 저장 디렉토리
├── tests/
│   ├── test_auth.py
│   └── test_models_base.py
└── scripts/
    └── test_generate.py
```

## 모델 계층 설계

### 상속 구조

```
BaseModel (ABC)
  └── ImageModel (ABC)
        └── Gemini_3_1_FlashImage (구현체)
```

**BaseModel**은 모든 모델의 최상위 추상 클래스다. `model_id`, `display_name`, `label` 클래스 변수와 `get_label()` 클래스 메서드를 정의한다. `__init__()`에서 `self.capabilities: set[Capability] = set()`으로 빈 인스턴스 변수를 초기화한다.

**ImageModel**은 이미지 모달리티 전용 중간 클래스다. `__init__()`에서 `super().__init__()` 호출 후 `self.capabilities.add(Capability.IMAGE)`로 capability를 누적한다. `generate_image()`와 `edit_image()` 두 개의 추상 메서드를 선언한다. 또한 ComfyUI 텐서(`[1,H,W,C]` float32)와 PNG bytes 간 변환을 담당하는 `tensor_to_bytes()`/`bytes_to_tensor()` 정적 메서드를 제공한다.

### Capability enum

```python
class Capability(StrEnum):
    IMAGE = auto()
    TEXT = auto()
    VIDEO = auto()
```

모델이 지원하는 모달리티를 선언적으로 표현한다. 현재 `IMAGE`만 사용되며, `TEXT`와 `VIDEO`는 향후 확장을 위한 예약값이다.

### 다중상속 확장 가능성

`BaseModel` 아래에 `ImageModel`, `TextModel`, `VideoModel` 등을 병렬로 정의할 수 있다. 하나의 구현체가 여러 모달리티를 동시에 지원해야 하는 경우 다중상속으로 조합할 수 있는 구조다.

```python
class MultiModal(ImageModel, TextModel):
    def __init__(self):
        super().__init__()  # MRO로 각 부모의 __init__() 순회
        # self.capabilities = {Capability.IMAGE, Capability.TEXT} 자동 누적
```

`capabilities`가 인스턴스 변수이고 각 중간 클래스의 `__init__()`에서 `add()`하므로, 다중상속 시 MRO 체인을 따라 자동으로 합집합이 된다. 별도 설정이 필요 없다.

## 모델 레지스트리

`models/registry.py`가 레지스트리 역할을 한다. `models/__init__.py`는 base 클래스만 재내보내기한다.

```python
# models/registry.py
from .base import ImageModel
from .gemini_flash_image import Gemini_3_1_FlashImage

IMAGE_MODELS: dict[str, type[ImageModel]] = {
    Gemini_3_1_FlashImage.get_label(): Gemini_3_1_FlashImage,
}
```

Eager import를 사용하며, 새 모델 추가 시 이 파일에 import와 딕셔너리 항목을 추가하면 된다. 노드에서는 `models.registry`를 직접 import한다.

### Label 기반 콤보박스 키

레지스트리 딕셔너리의 키는 `get_label()` 반환값이다. ComfyUI 노드의 콤보박스에 표시되는 이름이 곧 레지스트리 조회 키가 된다.

**`get_label()` 동작 규칙:**
- `label` 클래스 변수가 명시적으로 설정된 경우: 해당 값을 그대로 반환한다. (예: `Gemini_3_1_FlashImage.label = "NanoBanana2"` → `"NanoBanana2"`)
- `label`이 `None`인 경우: 클래스명을 CamelCase 경계에서 분리하여 공백으로 연결한다. (예: `GeminiFlashImage` → `"Gemini Flash Image"`)

### 팩토리 함수

- `get_image_model_names()`: 등록된 모든 이미지 모델의 label 리스트 반환 (콤보박스 옵션용).
- `create_image_model(name)`: label로 모델 클래스를 조회하여 인스턴스를 생성 반환.

## 노드 분리 패턴

노드 설계는 **Model / Config / Action** 세 역할로 분리되어 있다.

### 역할 분리

| 역할 | 노드 | 책임 |
|------|------|------|
| **Model** | `VertexImageModel` | 모델 선택. 콤보박스에서 label을 선택하면 `create_image_model()`로 인스턴스를 생성하여 출력한다. |
| **Config** | `VertexConfig` | 파라미터 조합 (aspect_ratio, image_size, response_modalities, thinking_level, system_prompt). 프리셋 저장/로드도 이 노드에서 처리한다. |
| **Action** | `VertexImageGenerate`, `VertexImageEdit` | 실제 API 호출 및 결과 텐서 반환. Model과 Config를 입력으로 받아 실행한다. |

### Custom 타입으로 연결

```python
VERTEX_IMAGE_MODEL = io.Custom("VERTEX_IMAGE_MODEL")
VERTEX_CONFIG = io.Custom("VERTEX_CONFIG")
```

`io.Custom` 타입을 정의하여 노드 간 연결을 타입 안전하게 제한한다. ComfyUI 워크플로 에디터에서 `VERTEX_IMAGE_MODEL` 출력 포트는 같은 타입의 입력 포트에만 연결할 수 있다. 이를 통해:

1. Model 노드의 출력이 Action 노드의 model 입력에만 연결되도록 강제한다.
2. Config 노드의 출력이 Action 노드의 config 입력에만 연결되도록 강제한다.
3. `VERTEX_TEXT_MODEL`이 미리 예약되어 있어, 텍스트 모델 노드 추가 시 이미지 모델과 혼용되지 않도록 분리할 수 있다.

### Action 노드의 공통 패턴

두 Action 노드(`VertexImageGenerate`, `VertexImageEdit`)는 동일한 구조를 따른다:

1. 입력 검증 (프롬프트 비어있는지, 이미지 존재 여부 등)
2. `model.generate_image()` 또는 `model.edit_image()` 호출
3. 실패 시 512x512 검정 텐서 + 에러 메시지 반환 (예외 대신 graceful 처리)
4. `io.NodeOutput`으로 IMAGE 텐서 + text 문자열 + `ui.PreviewImage` 반환

`VertexImageEdit`는 `io.Autogrow`를 사용하여 1~14장의 이미지를 동적으로 입력받을 수 있다.

## 싱글턴 패턴

`auth.py`에서 `genai.Client`를 모듈 수준 싱글턴으로 관리한다.

```python
_client: genai.Client | None = None

def get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=get_api_key())
    return _client
```

특징:
- **Lazy 초기화**: 최초 호출 시에만 클라이언트를 생성한다. import 시점에 API 키가 없어도 에러가 발생하지 않는다.
- **API 키 탐색 순서**: 환경변수 `GEMINI_API_KEY` → ComfyUI 루트의 `.env` 파일. `dotenv`로 `.env`를 모듈 로드 시 자동 로딩한다.
- **확장 지점**: `get_api_key()` 함수만 수정하면 1Password, Vault 등 외부 키 소스를 연동할 수 있다 (코드 주석에 명시).
- **ComfyUI 루트 경로 결정**: `Path(__file__).parent.parent.parent`로 계산한다. 이는 이 패키지가 `custom_nodes/` 하위에 설치되는 것을 전제한다.

## 테스트 전략

### conftest.py의 루트 __init__.py 우회

```python
_ROOT_PKG = "__init__"
if _ROOT_PKG not in sys.modules:
    sys.modules[_ROOT_PKG] = types.ModuleType(_ROOT_PKG)
```

루트 `__init__.py`가 `from .nodes import ...` 형태의 relative import를 사용하기 때문에, pytest가 이 파일을 단독 모듈로 import하면 `ImportError`가 발생한다. conftest.py에서 더미 모듈을 `sys.modules`에 등록하여 이 문제를 우회한다.

### ComfyUI venv 의존

```python
_COMFYUI_ROOT = Path(__file__).resolve().parent.parent / "ComfyUI"
if _COMFYUI_ROOT.exists() and str(_COMFYUI_ROOT) not in sys.path:
    sys.path.insert(0, str(_COMFYUI_ROOT))
```

`comfy_api.latest`는 ComfyUI 본체에 포함된 패키지이므로, 테스트 실행 시 ComfyUI 루트를 `sys.path`에 추가해야 한다. 이는 테스트가 ComfyUI venv 환경 또는 ComfyUI 소스가 인접 디렉토리에 존재하는 환경에서만 정상 동작함을 의미한다.

### pyproject.toml 테스트 설정

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

`pythonpath = ["."]`로 프로젝트 루트를 Python 경로에 포함하여, `from models import ...` 등 패키지 내부 import가 동작하도록 한다.

## 확장 포인트

### 새 모델 추가 방법

1. `models/` 디렉토리에 새 모듈 생성 (예: `models/gemini_pro.py`).
2. `ImageModel`을 상속하고 `model_id`, `display_name` 설정, `generate_image()`/`edit_image()` 구현. `__init__()`에서 `super().__init__()` 호출.
3. `models/registry.py`에 import 및 딕셔너리 항목 추가.

```python
# models/registry.py
from .gemini_pro import GeminiPro  # 추가

IMAGE_MODELS: dict[str, type[ImageModel]] = {
    Gemini_3_1_FlashImage.get_label(): Gemini_3_1_FlashImage,
    GeminiPro.get_label(): GeminiPro,  # 추가
}
```

노드 코드 수정은 필요 없다. 레지스트리에 등록만 하면 콤보박스에 자동 노출된다.

### 새 모달리티 추가 방법

텍스트 생성 모달리티를 추가하는 경우를 예로 든다.

1. `models/base.py`에 `TextModel(BaseModel)` 추상 클래스 추가. `__init__()`에서 `super().__init__()` 후 `self.capabilities.add(Capability.TEXT)`. `generate_text()` 등 추상 메서드 정의.
2. `models/registry.py`에 `TEXT_MODELS` 딕셔너리 및 `get_text_model_names()`, `create_text_model()` 팩토리 함수 추가.
3. `nodes/types.py`에 이미 예약된 `VERTEX_TEXT_MODEL`을 활용.
4. `nodes/` 디렉토리에 `model_text.py` (모델 선택), `text_generate.py` (액션) 등 신규 노드 추가.
5. `__init__.py`의 `_NODES` 리스트에 새 노드 클래스 추가.

기존 이미지 관련 코드는 전혀 수정하지 않아도 된다. Model/Config/Action 분리와 Custom 타입 시스템이 모달리티 간 격리를 보장한다.
