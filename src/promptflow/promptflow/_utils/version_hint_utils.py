# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import datetime
import json
import sys
import contextlib

from promptflow._utils.logger_utils import LoggerFactory
from promptflow._constants import (LAST_HINT_TIME, LAST_CHECK_TIME, PF_VERSION_CHECK, CLI_PACKAGE_NAME,
                                   HINT_INTERVAL_DAY, GET_PYPI_INTERVAL_DAY, LATEST_VERSION, CURRENT_VERSION)
from promptflow._sdk._constants import HOME_PROMPT_FLOW_DIR


if sys.platform.startswith("win"):
    import msvcrt
else:
    import fcntl

HINT_ACTIVITY_NAME = ["pf.flows.test", "pf.runs.create_or_update", "pfazure.flows.create_or_update",
                      "pfazure.runs.create_or_update"]
logger = LoggerFactory.get_logger(__name__)


@contextlib.contextmanager
def acquire_lock(filename):
    if not sys.platform.startswith("win"):
        with open(filename, "a+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            yield f
            fcntl.flock(f, fcntl.LOCK_UN)
            f.close()
    else:  # Windows
        with open(filename, "w") as f:
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
            yield f
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            f.close()


def get_cached_versions():
    from promptflow._sdk._utils import read_write_by_user
    lock_path = HOME_PROMPT_FLOW_DIR / (PF_VERSION_CHECK + '.lock')
    with acquire_lock(lock_path):
        (HOME_PROMPT_FLOW_DIR / PF_VERSION_CHECK).touch(mode=read_write_by_user(), exist_ok=True)
        with open(HOME_PROMPT_FLOW_DIR / PF_VERSION_CHECK, "r") as f:
            try:
                cached_versions = json.load(f)
            except json.decoder.JSONDecodeError:
                cached_versions = {}
        return cached_versions


def dump_cached_versions(cached_versions):
    lock_path = HOME_PROMPT_FLOW_DIR / (PF_VERSION_CHECK + '.lock')
    with acquire_lock(lock_path):
        with open(HOME_PROMPT_FLOW_DIR / PF_VERSION_CHECK, "w") as f:
            json.dump(cached_versions, f)


def get_latest_version_from_pypi(package_name):
    pypi_url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        import requests
        response = requests.get(pypi_url, timeout=3)
        if response.status_code == 200:
            data = response.json()
            latest_version = data["info"]["version"]
            return latest_version
        else:
            return None
    except Exception as ex:  # pylint: disable=broad-except
        logger.debug(f"Failed to get the latest version from '{pypi_url}'. {str(ex)}")
        return None


def check_latest_version():
    """ Get the latest versions from a cached file"""
    cached_versions = get_cached_versions()
    last_check_time = datetime.datetime.strptime(cached_versions[LAST_CHECK_TIME], '%Y-%m-%d %H:%M:%S.%f') \
        if LAST_CHECK_TIME in cached_versions else None

    if last_check_time is None or (datetime.datetime.now() >
                                   last_check_time + datetime.timedelta(days=GET_PYPI_INTERVAL_DAY)):
        version = get_latest_version_from_pypi(CLI_PACKAGE_NAME)
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
    last_hint_time = datetime.datetime.strptime(
        cached_versions[LAST_HINT_TIME],
        '%Y-%m-%d %H:%M:%S.%f'
    ) if LAST_HINT_TIME in cached_versions else None
    if last_hint_time is None or (datetime.datetime.now() >
                                  last_hint_time + datetime.timedelta(days=HINT_INTERVAL_DAY)):
        from promptflow import __version__ as local_version
        cached_versions[CURRENT_VERSION] = local_version
        if LATEST_VERSION in cached_versions:
            from packaging.version import parse
            if parse(cached_versions[CURRENT_VERSION]) < parse(cached_versions[LATEST_VERSION]):
                cached_versions[LAST_HINT_TIME] = str(datetime.datetime.now())
                message = (f"New prompt flow version available: promptflow-{cached_versions[LATEST_VERSION]}. Running "
                           f"'pip install --upgrade promptflow' to update.")
                logger.debug(message)
            else:
                logger.debug(
                    "Failed to get the latest version from pypi. Need check Network connection and check "
                    "if new prompt flow version is available manually.")
        dump_cached_versions(cached_versions)
