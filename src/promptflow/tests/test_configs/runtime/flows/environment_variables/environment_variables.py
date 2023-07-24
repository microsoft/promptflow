# flake8: noqa
import os
from promptflow import tool, flow

@tool
def get_environment_variables(env_key: str = "HOME"):
    if not env_key:
        raise ValueError("env_key is empty")
    
    env_value = os.environ.get(env_key)
    if not env_value:
        raise ValueError("env_key is not set in environment")
    return {
        "env_value": env_value
    }

@flow()
def environment_variables_flow(env_key: str = 'HOME'):
     get_env = get_environment_variables(env_key)
     return get_env

# python -m promptflow.scripts.dump_flow --path .\environment_variables.py --mode payload --target .