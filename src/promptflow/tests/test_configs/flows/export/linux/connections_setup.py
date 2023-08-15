import argparse
import base64
import hashlib
import os
import shutil
from pathlib import Path

import keyring

from promptflow._sdk._constants import LOCAL_MGMT_DB_PATH


def update_migration_secret(migration_secret: str):
    keyring.set_password(
        "promptflow",
        "encryption_key",
        base64.urlsafe_b64encode(
            hashlib.sha256(migration_secret.encode("utf-8")).digest()
        ).decode("utf-8"),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=str, required=True, help="db file to migrate")
    parser.add_argument(
        "--migration-secret", type=str, help="migration secret used for the db"
    )
    parser.add_argument(
        "--migration-secret-file",
        type=str,
        help="migration secret used for the db in file, won't take effect if migration-secret is provided",
    )
    parser.add_argument(
        "--ignore-errors", action="store_true", help="whether to ignore errors"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="whether to delete the db file after migration",
    )
    args = parser.parse_args()

    if not args.migration_secret and args.migration_secret_file:
        if not os.path.isfile(args.migration_secret_file):
            raise FileNotFoundError(
                f"migration secret file {args.migration_secret_file} not found."
            )
        with open(args.migration_secret_file, "r") as f:
            args.migration_secret = f.read()

    if not args.migration_secret:
        raise ValueError(
            "either migration-secret or migration-secret-file should be provided"
        )

    if os.path.isfile(args.file):
        Path(LOCAL_MGMT_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(args.file, LOCAL_MGMT_DB_PATH)
        update_migration_secret(args.migration_secret)
        if args.clean:
            os.remove(args.file)
    elif args.ignore_errors:
        pass
    else:
        raise FileNotFoundError(f"db file {args.file} not found.")
