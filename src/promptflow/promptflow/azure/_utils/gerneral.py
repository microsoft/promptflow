# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import jwt
from promptflow.exceptions import ValidationException


def is_arm_id(obj) -> bool:
    return isinstance(obj, str) and obj.startswith("azureml://")


def get_token(credential, resource) -> str:
    from azure.ai.ml._azure_environments import _resource_to_scopes

    azure_ml_scopes = _resource_to_scopes(resource)
    token = credential.get_token(*azure_ml_scopes).token
    # validate token has aml audience
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


def get_aml_token(credential) -> str:
    from azure.ai.ml._azure_environments import _get_aml_resource_id_from_metadata

    resource = _get_aml_resource_id_from_metadata()
    return get_token(credential, resource)


def get_arm_token(credential) -> str:
    from azure.ai.ml._azure_environments import _get_base_url_from_metadata

    resource = _get_base_url_from_metadata()
    return get_token(credential, resource)


def get_authorization(credential=None) -> str:
    token = get_arm_token(credential=credential)
    return "Bearer " + token


def get_user_alias_from_credential(credential):
    token = get_arm_token(credential=credential)
    decode_json = jwt.decode(token, options={"verify_signature": False, "verify_aud": False})
    try:
        email = decode_json.get("upn", decode_json.get("email", None))
        return email.split("@")[0]
    except Exception:
        # use oid when failed to get upn, e.g. service principal
        return decode_json["oid"]
