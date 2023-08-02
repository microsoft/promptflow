import argparse
import os
import shutil
from pathlib import Path
from typing import Union

import keyring

from promptflow.sdk._constants import LOCAL_MGMT_DB_PATH


def set_encryption_key(encryption_key: Union[str, bytes]):
    if isinstance(encryption_key, bytes):
        encryption_key = encryption_key.decode("utf-8")
    keyring.set_password("promptflow", "encryption_key", encryption_key)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=str, required=True, help="db file to migrate")
    parser.add_argument("--encryption-key", type=str, help="encryption key used for the db")
    parser.add_argument(
        "--encryption-key-file",
        type=str,
        help="encryption key used for the db in file, won't take effect if encryption-key is provided",
    )
    parser.add_argument("--ignore-errors", action="store_true", help="whether to ignore errors")
    parser.add_argument("--clean", action="store_true", help="whether to delete the db file after migration")
    args = parser.parse_args()

    if not args.encryption_key and args.encryption_key_file:
        if not os.path.isfile(args.encryption_key_file):
            raise FileNotFoundError(f"encryption key file {args.encryption_key_file} not found.")
        with open(args.encryption_key_file, "r") as f:
            args.encryption_key = f.read()

    if not args.encryption_key:
        raise ValueError("either encryption-key or encryption-key-file should be provided")

    if os.path.isfile(args.file):
        Path(LOCAL_MGMT_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(args.file, LOCAL_MGMT_DB_PATH)
        set_encryption_key(args.encryption_key)
        if args.clean:
            os.remove(args.file)
    elif args.ignore_errors:
        pass
    else:
        raise FileNotFoundError(f"db file {args.file} not found.")
