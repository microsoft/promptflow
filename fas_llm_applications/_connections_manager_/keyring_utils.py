# --- Keyring Backend Configuration ---
# Configures the 'keyring' library to use the 'keyrings.cryptfile' backend.
# This ensures sensitive connection parameters (like API keys or passwords)
# for the connection objects created later are stored securely in an
# encrypted, password-protected file on the local file system. This method
# provides a portable and secure way to manage secrets without relying on
# system-specific keyring services.
# keyring.set_keyring(keyrings.cryptfile.cryptfile.CryptFileKeyring())
# -----------------------------------
import os
import keyring
import keyrings.cryptfile.cryptfile
import sys


def verify_keyring():
    """
    Verifies that the configured keyring backend (keyrings.cryptfile)
    is properly initialized and accessible. This check is crucial
    before creating shared connections that depend on securely
    retrieving credentials from the keyring.
    """

    print("Verifying Keyring Set Up", file=sys.stderr)

    # Checks PYTHON_KEYRING_BACKEND environment variable
    python_keyring_backend_env = os.environ.get("PYTHON_KEYRING_BACKEND")
    expected_backend_path = "keyrings.cryptfile.cryptfile.CryptFileKeyring"

    # Verify Keyring back end path
    if python_keyring_backend_env != expected_backend_path:
        raise ValueError(f"WARNING: PYTHON_KEYRING_BACKEND is not set to the recommended path. Expected: {expected_backend_path}. Found: {python_keyring_backend_env}")

    # Get the master password from the environment variable
    master_password = os.environ.get("KEYRING_CRYPTFILE_PASSWORD")
    if not master_password:
        raise ValueError("KEYRING_CRYPTFILE_PASSWORD environment variable not set or is empty.")

    # Create the CryptFileKeyring instance and assign the master password directly
    # This prevents the interactive prompt.
    kr = keyrings.cryptfile.cryptfile.CryptFileKeyring()
    kr.keyring_key = master_password

    # Set this instance as the default keyring backend for this process
    keyring.set_keyring(kr)

    # Tests keyring is set
    active_keyring = keyring.get_keyring()
    if active_keyring != kr:
        raise ValueError("Error: Active keyring backend found is not set to the recommended value. Found: {active_keyring}")

    # Test storing and retrieving a password
    service_name = "my_promptflow_app"
    username = "aws_user"
    password = "super_secret_aws_key"

    try:
        keyring.set_password(service_name, username, password)
        retrieved_password = keyring.get_password(service_name, username)

        if retrieved_password != password:
            print("Error: Retrieved password does not match original!", file=sys.stderr)
            sys.exit(1)
        else:
            print("Keyring verification successful!", file=sys.stderr)

    except Exception as e:
        print(f"ERROR: Keyring test failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    # Ensure .env is loaded for independent testing
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.abspath(os.path.join(script_dir, "../digital_latin_project/.env"))

    # Add fas_llm_applications parent dir to sys.path if not already there for common_secrets_loader
    fas_llm_applications_parent_dir = os.path.abspath(os.path.join(script_dir, "../../.."))
    if fas_llm_applications_parent_dir not in sys.path:
        sys.path.insert(0, fas_llm_applications_parent_dir)

    try:
        from fas_llm_applications._connections_manager_.common_secrets_loader import load_environment_variables
        load_environment_variables(env_path=dotenv_path, override=True)
    except Exception as e:
        print(f"ERROR: Could not load .env for independent test: {e}", file=sys.stderr)
        sys.exit(1)

    verify_keyring()
