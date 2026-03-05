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
