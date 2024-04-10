# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import jwt

from promptflow.core._connection_provider._utils import get_arm_token, get_token


def is_arm_id(obj) -> bool:
    return isinstance(obj, str) and obj.startswith("azureml://")


# Add for backward compitability
get_token = get_token
get_arm_token = get_arm_token


def get_aml_token(credential) -> str:
    from azure.ai.ml._azure_environments import _get_aml_resource_id_from_metadata

    resource = _get_aml_resource_id_from_metadata()
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


def set_event_loop_policy():
    import asyncio
    import platform

    if platform.system().lower() == "windows":
        # Reference: https://stackoverflow.com/questions/45600579/asyncio-event-loop-is-closed-when-getting-loop
        # On Windows seems to be a problem with EventLoopPolicy, use this snippet to work around it
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
