import json
from pathlib import Path
from promptflow.storage.sqlite_client import SqliteClient
from promptflow.runtime.storage.entities import SecretRecords

db_folder = Path(__file__).parent.absolute() / "../src/promptflow-sdk/promptflow/service/data"
db_name = 'promptflow.db'


def setup_secret_records():
    sqlite_client = SqliteClient(db_folder, db_name, SecretRecords)

    s_file = db_folder / "secrets.json"
    if s_file.exists():
        with open(s_file, "r", encoding='utf-8') as f:
            secrets = json.load(f)

    secret_records = [SecretRecords(RowKey=key, secret=value) for key, value in secrets.items()]
    for r in secret_records:
        sqlite_client.upsert(r)


if __name__ == "__main__":
    setup_secret_records()
