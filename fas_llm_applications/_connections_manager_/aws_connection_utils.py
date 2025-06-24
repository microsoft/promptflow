import sys
from promptflow.client import PFClient
from promptflow.connections import CustomConnection


def ensure_promptflow_aws_connection(
    access_key: str,
    secret_key: str,
    region: str,
    pf_client: PFClient,
    connection_name: str = "bedrock_connection",
    service_name: str = "bedrock-runtime",
) -> CustomConnection:
    """
    Ensures a Promptflow CustomConnection for AWS exists and is up-to-date.
    Returns the connection object.

    Args:
        access_key (str): The AWS access key ID for authentication.
        secret_key (str): The AWS secret access key for authentication.
        region (str): The AWS region where the AWS service is located (i.e. 'us-east-1).
        connection_name (str, optional): The desired name for the Promptflow CustomConnection. Defaults to "bedrock_connection".
        service_name (str, optional): The AWS service name this connection is primarily for. Defaults to "bedrock-runtime".
    
    Returns:
        CustomConnection: The created or updated Promptflow CustomConnection object.
    """
    if not access_key or not secret_key:
        raise ValueError("AWS credentials are required to create Promptflow connection.", file=sys.stderr)

    # Create the connection object with desired properties
    connection = CustomConnection(
        name=connection_name,
        secrets={
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key
        },
        configs={
            "region_name": region,
            "service_name": service_name
        }
    )

    try:
        existing_connection = pf_client.connections.get(name=connection_name)
        if existing_connection.secrets == connection.secrets and existing_connection.configs == connection.configs:
            return existing_connection
        else:
            updated_connection = pf_client.connections.create_or_update(connection)
            return updated_connection
    except Exception as e:
        if type(e).__name__ == 'ConnectionNotFoundError':
            created_connection = pf_client.connections.create_or_update(connection)
            return created_connection
    except Exception as e:
            raise RuntimeError(f"Failed to manage Promptflow connection '{connection_name}': {e}")
        
    print(f"Connection '{connection_name}' successful.", file=sys.stdout)
        