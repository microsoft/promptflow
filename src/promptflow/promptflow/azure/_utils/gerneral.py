# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import jwt
from promptflow.exceptions import ValidationException


def is_arm_id(obj) -> bool:
    return isinstance(obj, str) and obj.startswith("azureml://")


def get_token_by_credential(credential):
    from azure.ai.ml._azure_environments import _get_aml_resource_id_from_metadata
    from azure.ai.ml._azure_environments import _resource_to_scopes

    # these code copied from _set_headers_with_user_aml_token function of azure.ai.ml.operations._job_operations
    aml_resource_id = _get_aml_resource_id_from_metadata()
    azure_ml_scopes = _resource_to_scopes(aml_resource_id)
    arm_token = credential.get_token(*azure_ml_scopes).token
    # validate token has aml audience
    decoded_token = jwt.decode(
        arm_token,
        options={"verify_signature": False, "verify_aud": False},
    )
    if decoded_token.get("aud") != aml_resource_id:
        msg = """AAD token with aml scope could not be fetched using the credentials being used.
        Please validate if token with {0} scope can be fetched using credentials provided to MLClient.
        Token with {0} scope can be fetched using credentials.get_token({0})
        """
        raise ValidationException(
            message=msg.format(*azure_ml_scopes),
        )

    return arm_token


def get_token_by_login():
    from azureml.core.authentication import InteractiveLoginAuthentication

    auth = InteractiveLoginAuthentication()
    arm_token = auth._get_arm_token()
    return arm_token


def get_arm_token(credential=None):
    if credential:
        return get_token_by_credential(credential=credential)

    return get_token_by_login()


def get_authorization(credential=None):
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
