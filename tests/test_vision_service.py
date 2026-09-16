"""Tests du service de vision (app/services/vision_service.py, étape 8)."""
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import HTTPException

from app.services.vision_service import MAX_IMAGE_BYTES, VisionServiceError, analyze_image, validate_image



def test_validate_image_rejects_unsupported_format():
    with pytest.raises(HTTPException) as exc_info:
        validate_image("application/pdf", 1000)
    assert exc_info.value.status_code == 415


def test_validate_image_rejects_oversized_image():
    with pytest.raises(HTTPException) as exc_info:
        validate_image("image/jpeg", MAX_IMAGE_BYTES + 1)
    assert exc_info.value.status_code == 413


def test_validate_image_accepts_valid_image():
    validate_image("image/png", 1024)  # ne doit lever aucune exception


async def test_analyze_image_without_anthropic_key_raises_clear_error():
    with pytest.raises(VisionServiceError):
        await analyze_image(b"fake-bytes", "image/jpeg")


async def test_analyze_image_mode_selects_correct_instruction(monkeypatch):
    import app.core.config as cfg

    monkeypatch.setattr(cfg.settings, "anthropic_api_key", "fake-key")

    fake_response = httpx.Response(
        200,
        json={"content": [{"type": "text", "text": "Résultat simulé"}]},
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)) as mock_post:
        await analyze_image(b"fake-bytes", "image/jpeg", mode="ocr")
        sent_instruction = mock_post.call_args.kwargs["json"]["messages"][0]["content"][1]["text"]
        assert "texte" in sent_instruction.lower()


async def test_analyze_image_question_overrides_mode(monkeypatch):
    import app.core.config as cfg

    monkeypatch.setattr(cfg.settings, "anthropic_api_key", "fake-key")

    fake_response = httpx.Response(
        200,
        json={"content": [{"type": "text", "text": "Résultat simulé"}]},
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)) as mock_post:
        await analyze_image(b"fake-bytes", "image/jpeg", question="Y a-t-il un danger visible ?")
        sent_instruction = mock_post.call_args.kwargs["json"]["messages"][0]["content"][1]["text"]
        assert sent_instruction == "Y a-t-il un danger visible ?"
