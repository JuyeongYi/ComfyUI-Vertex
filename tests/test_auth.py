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
