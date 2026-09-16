"""Chiffrement des données sensibles au repos (AES-256-GCM).

Utilisé pour stocker les tokens OAuth (Google) en base sans jamais les
garder en clair — même en cas de fuite de la base de données, les
tokens restent inexploitables sans la clé de chiffrement (qui, elle,
ne vit que dans les variables d'environnement du serveur, jamais en base).

Séparé de `SECRET_KEY` (qui signe les JWT) : deux clés pour deux usages
différents, pour qu'une rotation de l'une n'invalide pas l'autre.
"""
import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


class EncryptionNotConfigured(Exception):
    """Levée si ENCRYPTION_KEY n'est pas renseigné — on refuse de
    stocker un secret en clair plutôt que de dégrader silencieusement."""


def _get_key() -> bytes:
    if not settings.encryption_key:
        raise EncryptionNotConfigured(
            "ENCRYPTION_KEY manquant : nécessaire pour chiffrer les tokens d'intégration. "
            "Génère-en un avec `openssl rand -hex 32`."
        )
    key = bytes.fromhex(settings.encryption_key)
    if len(key) != 32:
        raise EncryptionNotConfigured("ENCRYPTION_KEY doit faire exactement 32 octets (64 caractères hex) pour AES-256.")
    return key


def encrypt(plaintext: str) -> str:
    """Chiffre une chaîne et renvoie un blob base64 (nonce + ciphertext)
    prêt à être stocké en base."""
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96 bits, recommandé pour GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), associated_data=None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode()


def decrypt(blob: str) -> str:
    key = _get_key()
    aesgcm = AESGCM(key)
    raw = base64.urlsafe_b64decode(blob.encode())
    nonce, ciphertext = raw[:12], raw[12:]
    return aesgcm.decrypt(nonce, ciphertext, associated_data=None).decode()
