"""pytest 설정 — ComfyUI 익스텐션 루트 __init__.py의 relative import 문제 해결."""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

# ComfyUI 루트를 sys.path에 추가
_COMFYUI_ROOT = Path(__file__).resolve().parent.parent / "ComfyUI"
if _COMFYUI_ROOT.exists() and str(_COMFYUI_ROOT) not in sys.path:
    sys.path.insert(0, str(_COMFYUI_ROOT))

# 루트 __init__.py가 relative import를 사용하므로,
# pytest가 패키지로 import하기 전에 더미 모듈로 등록
_ROOT_PKG = "__init__"
if _ROOT_PKG not in sys.modules:
    sys.modules[_ROOT_PKG] = types.ModuleType(_ROOT_PKG)
