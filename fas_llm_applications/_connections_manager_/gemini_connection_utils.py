import sys
from promptflow.client import PFClient
from promptflow.connections import CustomConnection


def ensure_promptflow_gemini_connection(
    api_key: str,
    base_url: str,
    pf_client: PFClient,
    connection_name: str = "gemini_connection", # Default connection name for this HUIT setup
) -> CustomConnection:
    """
    Ensures a Promptflow CustomConnection exists for the HUIT AI Services Gemini API Gateway.
    If the connection does not exist, it creates it. If it exists, it updates it.

    Args:
        api_key (str): The API key obtained from the Harvard API Portal (for x-api-key header).
        base_url (str): The base URL for the HUIT AI Services Gemini API (e.g., https://go.apis.huit.harvard.edu/ais-google-gemini).
        conn_name (str, optional): The desired name for the Promptflow CustomConnection. Defaults to "gemini_connection".

    Returns:
        CustomConnection: The created or updated Promptflow CustomConnection object.
    """
    if not api_key or not base_url:
        raise ValueError("Gemini credentials are required to create Promptflow connection.", file=sys.stderr)

    # Create the connection object with desired properties
    connection = CustomConnection(
        name=connection_name,
        secrets={"api_key": api_key},
        configs={"base_url": base_url},
        description=f"HUIT AI Services Gemini API Connection via {base_url}"
    )

    try:
        existing_connection = pf_client.connections.get(name=connection_name)
        # if (existing_connection.secrets.get("api_key") == connection.secrets["api_key"] and
        #     existing_connection.configs.get("base_url") == connection.configs["base_url"]):
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
            raise RuntimeError(f"Failed to manage Promptflow connection '{connection_name}': {e}", file=sys.stderr)

    print(f"Connection '{connection_name}' successful.", file=sys.stdin)

