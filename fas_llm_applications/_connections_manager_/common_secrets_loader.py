import os
from dotenv import load_dotenv
from typing import Optional
from fas_llm_applications.digital_latin_project.scripts.load_env_to_shell import load_environment_variables

# # This flag ensures load_dotenv is called only once by this module's main loader
# _dotenv_loaded_flag = False

# def load_environment_variables(env_path: Optional[str] = None, override: bool = False):
#     """
#     Loads environment variables from a .env file into os.environ.
#     This function should be called once at the very beginning of your application's
#     startup when running locally.

#     Args:
#         env_path (str, optional): Explicit path to the .env file.
#                                   If None, load_dotenv will search for it
#                                   in the current directory and parent directories.
#         override (bool): If True, existing environment variables will be overwritten
#                          by values from the .env file. Default is False.
#     """
#     global _dotenv_loaded_flag

#     if not _dotenv_loaded_flag:
#         if env_path and os.path.exists(env_path):
#             load_dotenv(dotenv_path=env_path, override=override)
#         else:
#             load_dotenv(override=override) # Searches in current directory and parent directories
#         _dotenv_loaded_flag = True
#         print("Environment variables loaded.")
#     else:
#         print("Environment variables already loaded by common_secrets_loader.")

def get_env_var(var_name: str, required: bool = True, default: Optional[str] = None) -> str:
    """
    Retrieves an environment variable from os.environ.

    Args:
        var_name (str): The name of the environment variable.
        required (bool): If True, raises ValueError if the variable is not set.
                         Default is True.
        default (str, optional): A default value to return if the variable is not set
                                 and `required` is False.

    Returns:
        str: The value of the environment variable.

    Raises:
        ValueError: If `required` is True and the variable is not set.
    """ 
    try:
        if os.getenv(var_name) is None or "":
            load_environment_variables()

        value = os.getenv(var_name)
        if required and (value is None or value == ""): # Check for None or empty string     
            raise ValueError(f"Required environment variable '{var_name}' is not set or is empty.")
    except Exception as e:
        print((f"Error: {e}"))
        raise Exception(e)

    return value 

