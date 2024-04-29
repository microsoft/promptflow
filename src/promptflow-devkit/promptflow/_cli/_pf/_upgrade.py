import os

from promptflow._cli._params import add_param_yes, base_params
from promptflow._cli._pf._service import stop_service
from promptflow._cli._utils import activate_action, get_cli_sdk_logger
from promptflow._utils.utils import prompt_y_n
from promptflow.exceptions import UserErrorException

logger = get_cli_sdk_logger()

UPGRADE_MSG = "Not able to upgrade automatically"


def add_upgrade_parser(subparsers):
    """Add upgrade parser to the pf subparsers."""
    epilog = """
    Examples:

    # Upgrade prompt flow without prompt and run non-interactively:
    pf upgrade --yes
    """  # noqa: E501
    add_params = [
        add_param_yes,
    ] + base_params
    activate_action(
        name="upgrade",
        description="Upgrade prompt flow CLI.",
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Upgrade prompt flow CLI.",
        action_param_name="action",
    )


def upgrade_version(args):
    import platform
    import subprocess
    import sys

    from packaging.version import parse

    from promptflow._constants import _ENV_PF_INSTALLER, CLI_PACKAGE_NAME
    from promptflow._sdk._utilities.general_utils import get_promptflow_sdk_version
    from promptflow._sdk._version_hint_utils import get_latest_version

    installer = os.getenv(_ENV_PF_INSTALLER) or ""
    installer = installer.upper()
    print(f"installer: {installer}")
    latest_version = get_latest_version(CLI_PACKAGE_NAME, installer=installer)
    local_version = get_promptflow_sdk_version()
    if not latest_version:
        logger.warning("Failed to get the latest prompt flow version.")
        return
    elif local_version and parse(latest_version) <= parse(local_version):
        logger.warning("You already have the latest prompt flow version: %s", local_version)
        return

    yes = args.yes
    exit_code = 0
    latest_version_msg = (
        "Upgrading prompt flow CLI version to {}.".format(latest_version)
        if yes
        else "Latest version available is {}.".format(latest_version)
    )
    logger.warning("Your current prompt flow CLI version is %s. %s", local_version, latest_version_msg)
    if not yes:
        logger.warning("Please check the release notes first")
        if not sys.stdin.isatty():
            logger.debug("No tty available.")
            raise UserErrorException("No tty available. Please run command with --yes.")
        confirmation = prompt_y_n("Do you want to continue?", default="y")

        if not confirmation:
            logger.debug("Upgrade stopped by user")
            return
    # try to stop the service before upgrade
    stop_service()

    if installer == "MSI":
        _upgrade_on_windows(yes)
    elif installer == "PIP":
        pip_args = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "promptflow[azure,executable,azureml-serving,executor-service]",
            "-vv",
            "--disable-pip-version-check",
            "--no-cache-dir",
        ]
        logger.debug("Update prompt flow with '%s'", " ".join(pip_args))
        exit_code = subprocess.call(pip_args, shell=platform.system() == "Windows")
    elif installer == "SCRIPT":
        command = "curl https://promptflowartifact.blob.core.windows.net/linux-install-scripts/install | bash"
        logger.warning(f"{UPGRADE_MSG}, you can try to run {command} in your terminal directly to upgrade package.")
        return
    else:
        logger.warning(UPGRADE_MSG)
        return

    if exit_code:
        err_msg = "CLI upgrade failed."
        logger.warning(err_msg)
        sys.exit(exit_code)

    import importlib
    import json

    importlib.reload(subprocess)
    importlib.reload(json)

    version_result = subprocess.check_output(["pf", "version"], shell=platform.system() == "Windows")
    # Remove ANSI codes which control color and format of text in the console output.
    version_result = version_result.decode().replace("\x1b[0m", "").strip()
    version_json = json.loads(version_result)
    new_version = version_json["promptflow"]

    if new_version == local_version:
        err_msg = f"CLI upgrade to version {latest_version} failed or aborted."
        logger.warning(err_msg)
        sys.exit(1)

    logger.warning("Upgrade finished.")


def _upgrade_on_windows(yes):
    """Download MSI to a temp folder and install it with msiexec.exe.
    Directly installing from URL may be blocked by policy: https://github.com/Azure/azure-cli/issues/19171
    This also gives the user a chance to manually install the MSI in case of msiexec.exe failure.
    """
    import subprocess
    import sys
    import tempfile

    msi_url = "https://aka.ms/installpromptflowwindowsx64"
    logger.warning("Updating prompt flow CLI with MSI from %s", msi_url)

    # Save MSI to ~\AppData\Local\Temp\promptflow-msi, clean up the folder first
    msi_dir = os.path.join(tempfile.gettempdir(), "promptflow-msi")
    try:
        import shutil

        shutil.rmtree(msi_dir)
    except FileNotFoundError:
        # The folder has already been deleted. No further retry is needed.
        # errno: 2, winerror: 3, strerror: 'The system cannot find the path specified'
        pass
    except OSError as err:
        logger.warning("Failed to delete '%s': %s. You may try to delete it manually.", msi_dir, err)

    os.makedirs(msi_dir, exist_ok=True)
    msi_path = _download_from_url(msi_url, msi_dir)
    if yes:
        subprocess.Popen(["msiexec.exe", "/i", msi_path, "/qn"])
    else:
        subprocess.call(["msiexec.exe", "/i", msi_path])
    logger.warning("Installation started. Please complete the upgrade in the opened window.")
    sys.exit(0)


def _download_from_url(url, target_dir):
    import requests

    r = requests.get(url, stream=True)
    if r.status_code != 200:
        raise UserErrorException("Request to {} failed with {}".format(url, r.status_code))

    # r.url is the real path of the msi, like
    # 'https://promptflowartifact.blob.core.windows.net/msi-installer/promptflow.msi'
    file_name = r.url.rsplit("/")[-1]
    msi_path = os.path.join(target_dir, file_name)
    logger.warning("Downloading MSI to %s", msi_path)

    with open(msi_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024):
            f.write(chunk)

    return msi_path
