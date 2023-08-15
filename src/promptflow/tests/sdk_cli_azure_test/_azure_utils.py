from azure.identity import AzureCliCredential, DefaultAzureCredential


def get_cred():
    """get credential for azure storage"""
    # resolve requests
    try:
        credential = AzureCliCredential()
        token = credential.get_token("https://management.azure.com/.default")
    except Exception:
        credential = DefaultAzureCredential()
        # ensure we can get token
        token = credential.get_token("https://management.azure.com/.default")

    assert token is not None
    return credential
