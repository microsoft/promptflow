# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import jwt


def is_arm_id(obj) -> bool:
    return isinstance(obj, str) and obj.startswith("azureml://")


def get_user_alias_from_credential(credential):
    token = credential.get_token("https://management.azure.com/.default").token
    decode_json = jwt.decode(token, options={"verify_signature": False, "verify_aud": False})
    try:
        email = decode_json.get("upn", decode_json.get("email", None))
        return email.split("@")[0]
    except Exception:
        # use oid when failed to get upn, e.g. service principal
        return decode_json["oid"]
