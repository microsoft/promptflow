# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import datetime
import json

from promptflow._constants import CLI_PACKAGE_NAME, VERSION_UPDATE_TIME, PF_VERSION_CHECK

HINT_ACTIVITY_NAME = ["pf.flows.test", "pf.runs.create_or_update", "pfazure.flows.create_or_update",
                      "pfazure.runs.create_or_update"]


def _get_local_versions():
    # get locally installed versions
    from promptflow import __version__ as promptflow_version

    versions = {CLI_PACKAGE_NAME: {'local': promptflow_version}}
    return versions


def get_cached_latest_versions(cached_versions):
    """ Get the latest versions from a cached file"""
    import datetime

    versions = _get_local_versions()
    if VERSION_UPDATE_TIME in cached_versions:
        version_update_time = datetime.datetime.strptime(cached_versions[VERSION_UPDATE_TIME], '%Y-%m-%d %H:%M:%S.%f')
        if datetime.datetime.now() < version_update_time + datetime.timedelta(days=1):
            cache_versions = cached_versions['versions'] if 'versions' in cached_versions else {}
            if cache_versions and cache_versions[CLI_PACKAGE_NAME]['local'] == versions[CLI_PACKAGE_NAME]['local']:
                return cache_versions.copy(), True, False

    versions, success = _update_latest_from_pypi(versions)
    cached_versions['versions'] = versions
    cached_versions[VERSION_UPDATE_TIME] = str(datetime.datetime.now())
    return versions.copy(), success, True


def _update_latest_from_pypi(versions):
    success = True
    version = get_latest_version_from_pypi(CLI_PACKAGE_NAME)
    if version is None:
        success = False
    else:
        versions[CLI_PACKAGE_NAME]['pypi'] = version
    return versions, success

def get_latest_version_from_pypi(package_name):
    try:
        import requests
        pypi_url = f"https://pypi.org/pypi/{package_name}/json"
        response = requests.get(pypi_url)
        if response.status_code == 200:
            data = response.json()
            latest_version = data["info"]["version"]
            return latest_version
        else:
            return None
    except Exception as ex:  # pylint: disable=broad-except
        print(f"Failed to get the latest version from '{pypi_url}'. {str(ex)}")
        return None


def hint_for_update():
    # check for new version auto-upgrade
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
    if version_update_time is None or datetime.datetime.now() > version_update_time + datetime.timedelta(days=7):
        _, success, is_updated = get_cached_latest_versions(cached_versions)
        from packaging.version import parse
        if success:
            if parse(cached_versions['versions'][CLI_PACKAGE_NAME]['local']) < parse(cached_versions['versions'][CLI_PACKAGE_NAME]['pypi']):
                print_yellow_warning("New prompt flow version available. Running 'pip install --upgrade promptflow' "
                                     "to update.")
        else:
            print_yellow_warning("Failed to get the latest version from pypi. Need check Network connection and check "
                                 "if new prompt flow version is available manually.")
        if is_updated:
            with open(HOME_PROMPT_FLOW_DIR / PF_VERSION_CHECK, "w") as f:
                json.dump(cached_versions, f)