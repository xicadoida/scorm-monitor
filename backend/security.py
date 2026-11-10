import hashlib
import hmac
import secrets


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        100000
    ).hex()

    return f"{salt}${password_hash}"


def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash:
        return False

    try:
        salt, password_hash = stored_hash.split("$", 1)
        if not salt or not password_hash:
            return False

        new_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            100000
        ).hex()
    except (AttributeError, TypeError, ValueError):
        # Um registro legado ou corrompido jamais pode transformar uma
        # credencial invalida em erro 500 no endpoint de login.
        return False

    return hmac.compare_digest(new_hash, password_hash)
