# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os
import re

from promptflow._constants import PF_NO_INTERACTIVE_LOGIN
from promptflow._sdk._constants import AZURE_WORKSPACE_REGEX_FORMAT
from promptflow._utils.user_agent_utils import ClientUserAgentUtil
from promptflow.core._errors import MalformedConnectionProviderConfig, MissingRequiredPackage
from promptflow.exceptions import ValidationException


def check_required_packages():
    try:
        import azure.ai.ml  # noqa: F401
        import azure.identity  # noqa: F401
    except ImportError as e:
        raise MissingRequiredPackage(
            message="Please install 'azure-identity>=1.12.0,<2.0.0' and 'azure-ai-ml' to use workspace connection."
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


def extract_workspace(provider_config) -> tuple:
    match = re.match(AZURE_WORKSPACE_REGEX_FORMAT, provider_config)
    if not match or len(match.groups()) != 5:
        raise MalformedConnectionProviderConfig(provider_config=provider_config)
    subscription_id = match.group(1)
    resource_group = match.group(3)
    workspace_name = match.group(5)
    return subscription_id, resource_group, workspace_name


def is_github_codespaces():
    """Check if the current environment is GitHub Codespaces."""
    # Ref:
    # https://docs.github.com/en/codespaces/developing-in-a-codespace/default-environment-variables-for-your-codespace
    return os.environ.get("CODESPACES", None) == "true"


def interactive_credential_disabled():
    """Check if interactive login is disabled."""
    return os.environ.get(PF_NO_INTERACTIVE_LOGIN, "false").lower() == "true"


def is_from_cli():
    """Check if the current execution is from promptflow-cli."""
    return "promptflow-cli" in ClientUserAgentUtil.get_user_agent()
