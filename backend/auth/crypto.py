"""Ed25519 challenge-response cryptography for Ginie authentication.

Functions:
  generate_challenge()   — Create a random 32-byte hex challenge, store in Redis (5-min TTL).
  verify_signature()     — Verify an Ed25519 signature against a challenge + public key.
  compute_fingerprint()  — Derive Canton-standard fingerprint from a public key.
"""

import os
import json
import structlog
import redis as redis_lib
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
import base64

from config import get_settings

logger = structlog.get_logger()

CHALLENGE_TTL_SECONDS = 300  # 5 minutes


def _get_redis():
    settings = get_settings()
    return redis_lib.from_url(settings.redis_url, decode_responses=True)


def generate_challenge() -> dict:
    """Generate a random 32-byte hex challenge and store in Redis with TTL.

    Returns:
        {"challenge": "hex_string", "expires_in": 300}
    """
    challenge = os.urandom(32).hex()

    try:
        r = _get_redis()
        r.set(f"auth:challenge:{challenge}", "pending", ex=CHALLENGE_TTL_SECONDS)
    except Exception as e:
        logger.warning("Redis unavailable for challenge storage", error=str(e))
        # Fall back to in-memory (less secure, but functional for dev)
        _challenge_store[challenge] = True

    return {"challenge": challenge, "expires_in": CHALLENGE_TTL_SECONDS}


def verify_signature(challenge: str, signature_b64: str, public_key_b64: str) -> bool:
    """Verify an Ed25519 signature of the challenge using the provided public key.

    Args:
        challenge: The hex challenge string that was signed.
        signature_b64: Base64-encoded Ed25519 signature.
        public_key_b64: Base64-encoded Ed25519 public key (32 bytes).

    Returns:
        True if signature is valid, False otherwise.
    """
    # Verify challenge exists and hasn't expired
    challenge_valid = False
    try:
        r = _get_redis()
        stored = r.get(f"auth:challenge:{challenge}")
        if stored:
            challenge_valid = True
            # Consume the challenge (one-time use)
            r.delete(f"auth:challenge:{challenge}")
    except Exception:
        # Check in-memory fallback
        if challenge in _challenge_store:
            challenge_valid = True
            del _challenge_store[challenge]

    if not challenge_valid:
        logger.warning("Challenge not found or expired", challenge=challenge[:16])
        return False

    try:
        public_key_bytes = base64.b64decode(public_key_b64)
        signature_bytes = base64.b64decode(signature_b64)

        if len(public_key_bytes) != 32:
            logger.warning("Invalid public key length", length=len(public_key_bytes))
            return False

        verify_key = VerifyKey(public_key_bytes)
        # Ed25519 signs the raw challenge bytes (UTF-8 encoded)
        verify_key.verify(challenge.encode("utf-8"), signature_bytes)
        return True

    except BadSignatureError:
        logger.warning("Ed25519 signature verification failed")
        return False
    except Exception as e:
        logger.error("Signature verification error", error=str(e))
        return False


def compute_fingerprint(public_key_b64: str) -> str:
    """Compute Canton-standard fingerprint from a base64-encoded public key.

    Canton fingerprint format: "1220" + hex(public_key)

    Args:
        public_key_b64: Base64-encoded Ed25519 public key.

    Returns:
        Fingerprint string like "1220abcdef..."
    """
    public_key_bytes = base64.b64decode(public_key_b64)
    return "1220" + public_key_bytes.hex()


# In-memory fallback for challenges when Redis is unavailable
_challenge_store: dict[str, bool] = {}
