import pytest

import json

from pathlib import Path

from promptflow.storage.sqlite_client import SqliteClient
from promptflow.runtime.storage.entities import SecretRecords
from promptflow.runtime.storage.encryption_util import encrypt_file, decrypt_file

from .._utils import get_config_file

DB_FOLDER_PATH = Path(__file__).parent / ".sqlitedb"
DB_NAME = "promptflow.db"

secrets = {
    "bing-api-key": "123",
    "openai-api-key": "abc",
}


secret_records = [SecretRecords(RowKey=key, secret=value) for key, value in secrets.items()]


@pytest.mark.unittest
def test_secret():
    sqlite_client = SqliteClient(DB_FOLDER_PATH, DB_NAME, SecretRecords, in_memory=True)

    for r in secret_records:
        sqlite_client.upsert(r)

    for key, value in secrets.items():
        assert sqlite_client.get(key).secret == value


@pytest.mark.unittest
def test_encrypted_secret():
    file = get_config_file("connection/test_connection.json")
    with open(file, "r", encoding="utf-8") as fp:
        origin = json.load(fp)
    enc_f = encrypt_file(file)
    content = decrypt_file(enc_f)
    processed = json.loads(content)

    assert origin == processed
