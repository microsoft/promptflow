# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from promptflow.core._errors import MissingRequiredPackage
from promptflow.exceptions import ValidationException


def _check_required_packages():
    try:
        import azure.ai.ml  # noqa: F401
        import azure.identity  # noqa: F401
    except ImportError as e:
        raise MissingRequiredPackage(
            message="Please install 'azure-identity>=1.12.0,<2.0.0' and 'azure-ai-ml' to use workspace connection."
        ) from e


def get_arm_token(credential) -> str:
    _check_required_packages()
    from azure.ai.ml._azure_environments import _get_base_url_from_metadata

    resource = _get_base_url_from_metadata()
    return get_token(credential, resource)


def get_token(credential, resource) -> str:
    _check_required_packages()
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
