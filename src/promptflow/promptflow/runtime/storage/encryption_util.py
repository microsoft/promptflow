from pathlib import Path
from cryptography.fernet import Fernet
import base64

ENCRYPTED_FILE_SUFFIX = ".encrypted"


def _get_encryption_key(file_path):
    """get encryption key from file name. only mean for testing purpose."""
    p = Path(file_path)
    byte_key = p.name.encode("utf-8")
    if len(byte_key) < 32:
        byte_key = byte_key + (b"0" * (32 - len(byte_key)))
    byte_key = byte_key[:32]
    key = base64.urlsafe_b64encode(byte_key)
    return key


def _save_to_encrypted_file(file_path, content: str, encryption_key):
    """save to encrypted file."""
    f = Fernet(encryption_key)
    token = f.encrypt(content.encode("utf-8"))
    with open(file_path, "wb") as f:
        f.write(token)


def _load_from_encrypted_file(file_path, encryption_key):
    """load from encrypted file."""
    with open(file_path, "rb") as f:
        token = f.read()
    f = Fernet(encryption_key)
    return f.decrypt(token).decode("utf-8")


def encrypt_file(file_path: str):
    """encrypt file with default encryption key to file "file_path.encrypted"."""
    file_path = str(file_path)
    encrypted_file = file_path + ENCRYPTED_FILE_SUFFIX
    encryption_key = _get_encryption_key(encrypted_file)
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    _save_to_encrypted_file(encrypted_file, content, encryption_key)
    return encrypted_file


def decrypt_file(file_path: str) -> str:
    """decrypt file with default encryption key."""

    encryption_key = _get_encryption_key(file_path)
    content = _load_from_encrypted_file(file_path, encryption_key)
    return content


if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=str, required=True, help="file to encrypt")
    args = parser.parse_args()
    encrypt_file(file_path=args.file)
    os.remove(args.file)
