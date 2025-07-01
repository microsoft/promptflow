"""
This script is designed to load environment variables from the project's root '.env' file
and print them to standard output as 'export' commands suitable for shell execution.

It is primarily intended to be sourced by a shell (e.g., in a devcontainer's `onCreateCommand`
or a pre-start script) to inject environment variables into the shell session
without directly modifying the Python script's `os.environ`.

The script performs the following actions:
1. Calculates the path to the solution's root directory and the '.env' file within it.
2. Adds the parent directory of `fas_llm_applications` to `sys.path` for module discoverability.
3. Checks for the existence of the '.env' file and exits with an error if not found.
4. Loads the key-value pairs from the '.env' file.
5. Iterates through the loaded variables and prints an 'export VAR_NAME="VALUE"' command for each.
   Values are quoted to handle spaces and special characters correctly in the shell.
6. All informational and debug messages are directed to standard error (stderr)
   to keep standard output (stdout) clean for the 'export' commands.
"""
import sys
import os
from dotenv import dotenv_values

def load_environment_variables():
    fas_llm_applications_parent_dir= os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
    sys.path.insert(0, fas_llm_applications_parent_dir)
    solution_root_for_env = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    dotenv_path = os.path.join(solution_root_for_env, ".env")

    if not os.path.exists(dotenv_path):
        print(f"ERROR (load_env_to_shell.py): .env file not found at {dotenv_path}", file=sys.stderr) # Print to stderr
        sys.exit(1)

    # Load values from .env without affecting current Python process's os.environ
    # We want to print them for the *shell*, not load them here.
    config = dotenv_values(dotenv_path=dotenv_path)


    if not config:
        print(f"WARNING: No environment variables found in .env file at {dotenv_path}", file=sys.stderr)
        sys.exit(0) # Exit gracefully if no vars are found, but don't error out the shell

    # Iterate through the loaded config and print export commands
    for key, value in config.items():
        if value is not None:
            # Quote values to handle spaces or special characters
            print(f'export {key}="{value}"')

    print(f"Finished exporting environment variables.", file=sys.stderr)

load_environment_variables()