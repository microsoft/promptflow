# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import httpx
import datetime
import json

from promptflow._constants import (VERSION_UPDATE_TIME, PF_VERSION_CHECK, CLI_PACKAGE_NAME, HINT_FREQUENCY_DAY,
                                   GET_PYPI_FREQUENCY_DAY)

HINT_ACTIVITY_NAME = ["pf.flows.test", "pf.runs.create_or_update", "pfazure.flows.create_or_update",
                      "pfazure.runs.create_or_update"]


def get_local_versions():
    # get locally installed versions
    from promptflow import __version__ as promptflow_version

    versions = {'local': promptflow_version}
    return versions


async def get_cached_latest_versions(cached_versions):
    """ Get the latest versions from a cached file"""
    versions = get_local_versions()
    if VERSION_UPDATE_TIME in cached_versions:
        version_update_time = datetime.datetime.strptime(cached_versions[VERSION_UPDATE_TIME], '%Y-%m-%d %H:%M:%S.%f')
        if ('versions' in cached_versions and 'pypi' in cached_versions['versions'] and
                datetime.datetime.now() < version_update_time + datetime.timedelta(days=GET_PYPI_FREQUENCY_DAY)):
            cache_versions = cached_versions['versions'] if 'versions' in cached_versions else {}
            if cache_versions and cache_versions['local'] == versions['local']:
                return cache_versions.copy(), True, False

    versions, success = await update_latest_from_pypi(versions)
    cached_versions['versions'] = versions
    cached_versions[VERSION_UPDATE_TIME] = str(datetime.datetime.now())
    return versions.copy(), success, True


async def update_latest_from_pypi(versions):
    success = True
    version = await get_latest_version_from_pypi(CLI_PACKAGE_NAME)
    if version is None:
        success = False
    else:
        versions['pypi'] = version
    return versions, success


async def get_latest_version_from_pypi(package_name):
    pypi_url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(pypi_url)
            if response.status_code == 200:
                data = response.json()
                latest_version = data["info"]["version"]
                return latest_version
            else:
                return None
    except Exception as ex:  # pylint: disable=broad-except
        print(f"Failed to get the latest version from '{pypi_url}'. {str(ex)}")
        return None


async def hint_for_update():
    """
    Check if there is a new version of prompt flow available every 7 days. IF yes, print a warning message to hint
    customer to upgrade package.
    """

    from promptflow._sdk._constants import HOME_PROMPT_FLOW_DIR
    from promptflow._sdk._utils import read_write_by_user, print_yellow_warning

    (HOME_PROMPT_FLOW_DIR / PF_VERSION_CHECK).touch(mode=read_write_by_user(), exist_ok=True)
    with open(HOME_PROMPT_FLOW_DIR / PF_VERSION_CHECK, "r") as f:
        try:
            cached_versions = json.load(f)
        except json.decoder.JSONDecodeError:
            cached_versions = {}

    version_update_time = datetime.datetime.strptime(
        cached_versions[VERSION_UPDATE_TIME],
        '%Y-%m-%d %H:%M:%S.%f'
    ) if VERSION_UPDATE_TIME in cached_versions else None
    if (version_update_time is None or datetime.datetime.now() > version_update_time +
            datetime.timedelta(days=HINT_FREQUENCY_DAY)):
        _, success, is_updated = await get_cached_latest_versions(cached_versions)

        if success:
            from packaging.version import parse
            if parse(cached_versions['versions']['local']) < parse(cached_versions['versions']['pypi']):
                print_yellow_warning("New prompt flow version available: "
                                     "promptflow-{cached_versions['versions']['pypi']} . "
                                     "Running 'pip install --upgrade promptflow' to update.")
        else:
            print_yellow_warning("Failed to get the latest version from pypi. Need check Network connection and check "
                                 "if new prompt flow version is available manually.")
        if is_updated:
            with open(HOME_PROMPT_FLOW_DIR / PF_VERSION_CHECK, "w") as f:
                json.dump(cached_versions, f)
