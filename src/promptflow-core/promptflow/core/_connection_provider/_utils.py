# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os

from promptflow._constants import PF_NO_INTERACTIVE_LOGIN
from promptflow._utils.user_agent_utils import ClientUserAgentUtil
from promptflow.core._errors import MissingRequiredPackage
from promptflow.exceptions import ValidationException


def check_required_packages():
    try:
        import azure.ai.ml  # noqa: F401
        import azure.identity  # noqa: F401
    except ImportError as e:
        raise MissingRequiredPackage(
            message="Please install 'promptflow-core[azureml-serving]' to use Azure related features."
        ) from e


def get_arm_token(credential) -> str:
    check_required_packages()
    from azure.ai.ml._azure_environments import _get_base_url_from_metadata

    resource = _get_base_url_from_metadata()
    return get_token(credential, resource)


def get_token(credential, resource) -> str:
    check_required_packages()
    from azure.ai.ml._azure_environments import _resource_to_scopes

    azure_ml_scopes = _resource_to_scopes(resource)
    token = credential.get_token(*azure_ml_scopes).token
    # validate token has aml audience
    import jwt  # Included by azure-identity

    decoded_token = jwt.decode(
        token,
        options={"verify_signature": False, "verify_aud": False},
    )
    if decoded_token.get("aud") != resource:
        msg = """AAD token with aml scope could not be fetched using the credentials being used.
            Please validate if token with {0} scope can be fetched using credentials provided to PFClient.
            Token with {0} scope can be fetched using credentials.get_token({0})
            """
        raise ValidationException(
            message=msg.format(*azure_ml_scopes),
        )

    return token


def is_github_codespaces():
    """Check if the current environment is GitHub Codespaces."""
    # Ref:
    # https://docs.github.com/en/codespaces/developing-in-a-codespace/default-environment-variables-for-your-codespace
    return os.environ.get("CODESPACES", None) == "true"


def interactive_credential_enabled():
    """Check if interactive login is enabled."""
    return os.environ.get(PF_NO_INTERACTIVE_LOGIN, "true").lower() == "false"


def is_from_cli():
    """Check if the current execution is from promptflow-cli."""
    return "promptflow-cli" in ClientUserAgentUtil.get_user_agent()
