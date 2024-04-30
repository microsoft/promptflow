import argparse
from utils.secret_manager import get_secret_client, upload_secret


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--secret_name",
        type=str,
        required=True,
    )
    parser.add_argument(
        "--secret_value",
        type=str,
        required=True,
    )
    args = parser.parse_args()

    secret_client = get_secret_client()

    upload_secret(secret_client, args.secret_name, args.secret_value)
