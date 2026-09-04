from cryptography.fernet import Fernet, InvalidToken
from app.core.config import settings


def _fernet() -> Fernet:
    return Fernet(settings.camera_credential_key.encode("ascii"))


def encrypt_secret(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("No se pudo descifrar una credencial de cámara") from exc


def mask_rtsp_url(url: str | None) -> str | None:
    if not url:
        return None
    # Nunca devolver userinfo ni query strings potencialmente sensibles.
    try:
        from urllib.parse import urlsplit, urlunsplit
        parts = urlsplit(url)
        host = parts.hostname or "camera"
        port = f":{parts.port}" if parts.port else ""
        return urlunsplit((parts.scheme, f"{host}{port}", parts.path or "/", "", ""))
    except Exception:
        return "rtsp://***"
