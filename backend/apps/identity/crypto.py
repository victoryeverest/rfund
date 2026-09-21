"""Application-level encryption for sensitive identity numbers.

Uses a key derived from settings.SECRET_KEY + per-value salt via a
standards-based construction. Production deployments should switch to a
dedicated KMS by implementing StorageProvider/KeyProvider — documented in
docs/SECURITY.md. Values are never logged and never returned in full by
the API.
"""

from __future__ import annotations

import base64
import hashlib
import os

from django.conf import settings


def _derive(salt: bytes, length: int = 32) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", settings.SECRET_KEY.encode(), salt, 100_000, dklen=length)


def encrypt_value(plaintext: str) -> str:
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = _derive(salt)
    # ChaCha20-Poly1305 via cryptography lib if available; fallback to
    # AES-GCM style sealed box using Fernet-like HMAC construction.
    try:
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

        cipher = ChaCha20Poly1305(key)
        ct = cipher.encrypt(nonce, plaintext.encode(), b"rfund-identity")
        parts = [salt, nonce, ct]
    except ImportError:  # pragma: no cover - cryptography usually present
        # Deterministic fallback (HMAC-SHA256 stream) — still keyed & salted.
        stream = b""
        counter = 0
        while len(stream) < len(plaintext.encode()):
            stream += hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest()
            counter += 1
        data = plaintext.encode()
        ct = bytes(a ^ b for a, b in zip(data, stream))
        mac = hashlib.sha256(key + nonce + ct).digest()[:16]
        parts = [salt, nonce, ct + mac]
    return base64.urlsafe_b64encode(b"$".join(parts)).decode()


def decrypt_value(sealed: str) -> str:
    raw = base64.urlsafe_b64decode(sealed.encode())
    salt, nonce, rest = raw.split(b"$", 2)
    key = _derive(salt)
    try:
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

        cipher = ChaCha20Poly1305(key)
        return cipher.decrypt(nonce, rest, b"rfund-identity").decode()
    except ImportError:  # pragma: no cover
        ct, mac = rest[:-16], rest[-16:]
        expected = hashlib.sha256(key + nonce + ct).digest()[:16]
        if mac != expected:
            raise ValueError("Integrity check failed for encrypted value")
        stream = b""
        counter = 0
        while len(stream) < len(ct):
            stream += hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest()
            counter += 1
        return bytes(a ^ b for a, b in zip(ct, stream)).decode()
