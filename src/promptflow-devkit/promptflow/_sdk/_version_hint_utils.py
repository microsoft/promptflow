# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import datetime
import json
import logging

from promptflow._constants import (
    CLI_PACKAGE_NAME,
    CURRENT_VERSION,
    GET_PYPI_INTERVAL_DAY,
    HINT_INTERVAL_DAY,
    LAST_CHECK_TIME,
    LAST_HINT_TIME,
    LATEST_VERSION,
    PF_VERSION_CHECK,
)
from promptflow._sdk._constants import HOME_PROMPT_FLOW_DIR

HINT_ACTIVITY_NAME = [
    "pf.flows.test",
    "pf.runs.create_or_update",
    "pfazure.flows.create_or_update",
    "pfazure.runs.create_or_update",
]
logger = logging.getLogger(__name__)


def get_cached_versions():
    from promptflow._sdk._utilities.general_utils import read_write_by_user

    (HOME_PROMPT_FLOW_DIR / PF_VERSION_CHECK).touch(mode=read_write_by_user(), exist_ok=True)
    with open(HOME_PROMPT_FLOW_DIR / PF_VERSION_CHECK, "r") as f:
        try:
            cached_versions = json.load(f)
        except json.decoder.JSONDecodeError:
            cached_versions = {}
    return cached_versions


def dump_cached_versions(cached_versions):
    with open(HOME_PROMPT_FLOW_DIR / PF_VERSION_CHECK, "w") as f:
        json.dump(cached_versions, f)


def get_latest_version(package_name, installer="PIP"):
    if installer == "MSI":
        url = "https://promptflowartifact.blob.core.windows.net/msi-installer/latest_version.json"
    else:
        url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        import requests

        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            data = response.json()
            if installer == "MSI":
                latest_version = data[package_name]
            else:
                latest_version = data["info"]["version"]
            return latest_version
        else:
            return None
    except Exception as ex:  # pylint: disable=broad-except
        logger.debug(f"Failed to get the latest version from '{url}'. {str(ex)}")
        return None


def check_latest_version():
    """Get the latest versions from a cached file"""
    cached_versions = get_cached_versions()
    last_check_time = (
        datetime.datetime.strptime(cached_versions[LAST_CHECK_TIME], "%Y-%m-%d %H:%M:%S.%f")
        if LAST_CHECK_TIME in cached_versions
        else None
    )

    if last_check_time is None or (
        datetime.datetime.now() > last_check_time + datetime.timedelta(days=GET_PYPI_INTERVAL_DAY)
    ):
        # For hint, we can't know pfazure installed way for now, so we only check the latest version from pypi.
        version = get_latest_version(CLI_PACKAGE_NAME)
        if version is not None:
            cached_versions[LATEST_VERSION] = version
            cached_versions[LAST_CHECK_TIME] = str(datetime.datetime.now())
            dump_cached_versions(cached_versions)


def hint_for_update():
    """
    Check if there is a new version of prompt flow available every 7 days. IF yes, log debug info to hint
    customer to upgrade package.
    """

    cached_versions = get_cached_versions()
    last_hint_time = (
        datetime.datetime.strptime(cached_versions[LAST_HINT_TIME], "%Y-%m-%d %H:%M:%S.%f")
        if LAST_HINT_TIME in cached_versions
        else None
    )
    if last_hint_time is None or (
        datetime.datetime.now() > last_hint_time + datetime.timedelta(days=HINT_INTERVAL_DAY)
    ):
        from promptflow._sdk._utilities.general_utils import get_promptflow_devkit_version

        cached_versions[CURRENT_VERSION] = get_promptflow_devkit_version()
        if LATEST_VERSION in cached_versions:
            from packaging.version import parse

            if cached_versions[CURRENT_VERSION] is None or parse(cached_versions[CURRENT_VERSION]) < parse(
                cached_versions[LATEST_VERSION]
            ):
                cached_versions[LAST_HINT_TIME] = str(datetime.datetime.now())
                message = (
                    f"New prompt flow version available: promptflow-{cached_versions[LATEST_VERSION]}. Running "
                    f"'pf upgrade' to update CLI."
                )
                logger.debug(message)
        dump_cached_versions(cached_versions)
