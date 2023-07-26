import argparse
from utils.secret_manager import (
    get_secret_client,
    init_used_secret_names,
    validate_secret_name,
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tenant_id",
        type=str,
        required=True,
        help="The tenant id of the service principal",
    )
    parser.add_argument(
        "--client_id",
        type=str,
        required=True,
        help="The client id of the service principal",
    )
    parser.add_argument(
        "--client_secret",
        type=str,
        required=True,
        help="The client secret of the service principal",
    )
    parser.add_argument(
        "--secret_name",
        type=str,
        required=True,
    )
    args = parser.parse_args()

    secret_client = get_secret_client(
        args.tenant_id, args.client_id, args.client_secret
    )
    init_used_secret_names(secret_client)
    validate_secret_name(args.secret_name)

    print(f"Secret name {args.secret_name} is valid.")
