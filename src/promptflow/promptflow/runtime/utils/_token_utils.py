import datetime
import os
import traceback

import jwt
from azure.core.credentials import AccessToken

try:
    from functools import cache  # available since 3.9
except ImportError:
    from functools import lru_cache as cache

from promptflow.utils.timer import Timer

from ..utils import logger

STORAGE_OAUTH_SCOPE = "https://storage.azure.com/.default"
MANAGEMENT_OAUTH_SCOPE = "https://management.azure.com/.default"


def token_diagnostic(token, expires_on):
    """print token info for debug

    Learn more: https://learn.microsoft.com/en-us/azure/active-directory/develop/access-tokens
    """
    try:
        expire_time = datetime.datetime.fromtimestamp(expires_on)
        decoded_token = jwt.decode(token, options={"verify_signature": False, "verify_aud": False})
        oid = decoded_token.get("oid")
        scp = decoded_token.get("scp")
        logger.info("[diagnostic] Token expire on: %s, oid: %s, scp: %s", expire_time, oid, scp)
    except Exception as ex:
        logger.warning("Hit exception when parse token: %s\nTrace: %s", ex, traceback.format_exc())


def get_echo_credential_from_token(workspace_access_token, print_diagnostic=False):
    # TODO get real token expire time from request
    expires_on = datetime.datetime.now() + datetime.timedelta(hours=1)
    expires_on = int(expires_on.timestamp())
    cred = EchoCredential(workspace_access_token, expires_on)
    if print_diagnostic:
        token_diagnostic(workspace_access_token, expires_on)
    return cred


class EchoCredential:
    """EchoCredential is a credential that returns a token without refresh it."""

    def __init__(self, token, expires_on: int) -> None:
        self.token = token
        self.expires_on = expires_on

    def get_token(self, *scopes: str, **kwargs) -> AccessToken:
        """get the token passed in init"""
        return AccessToken(self.token, self.expires_on)


@cache
def _get_default_credential():
    """get default credential for current compute, cache the result to minimize actual token request count sent"""
    if os.environ.get("IS_IN_CI_PIPELINE") == "true":
        from azure.identity import AzureCliCredential

        cred = AzureCliCredential()
    else:
        from azure.identity import DefaultAzureCredential

        cred = DefaultAzureCredential(exclude_interactive_browser_credential=True)
    return cred


def get_default_credential(diagnostic=False):
    """get default credential for current compute"""
    cred = _get_default_credential()
    if diagnostic:
        try:
            with Timer(logger, "Set token diagnostic"):
                # try get token for diagnostic
                token = cred.get_token(MANAGEMENT_OAUTH_SCOPE)
                assert token is not None
                token_diagnostic(token.token, token.expires_on)

                token = cred.get_token(STORAGE_OAUTH_SCOPE)
                assert token is not None
                token_diagnostic(token.token, token.expires_on)
        except Exception as ex:
            # ignore error, best effort
            logger.warning("[diagnostic] Failed to get token: %s", str(ex))
            pass
    return cred
