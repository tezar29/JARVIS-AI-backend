"""Tests unitaires du chiffrement AES-256-GCM (app/core/crypto.py, étape 7)."""
import pytest

from app.core.crypto import decrypt, encrypt


def test_encrypt_decrypt_roundtrip():
    secret = "ya29.a0AfH6SMBxxx_fake_google_refresh_token_xxx"
    blob = encrypt(secret)

    assert blob != secret
    assert secret not in blob
    assert decrypt(blob) == secret


def test_encrypt_is_non_deterministic():
    """Le nonce aléatoire doit produire un blob différent à chaque appel,
    même pour un texte identique — propriété de sécurité importante
    (évite qu'un attaquant repère des tokens identiques en base)."""
    secret = "same-secret-both-times"
    assert encrypt(secret) != encrypt(secret)


def test_decrypt_rejects_tampered_blob():
    blob = encrypt("un secret")
    tampered = blob[:-4] + ("A" if blob[-4] != "A" else "B") + blob[-3:]

    with pytest.raises(Exception):
        decrypt(tampered)
