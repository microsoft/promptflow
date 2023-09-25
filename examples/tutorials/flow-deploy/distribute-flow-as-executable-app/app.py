import os
import sys

from promptflow._cli._pf._connection import create_connection
from streamlit.web import cli as stcli
from streamlit.runtime import exists

from main import start

def is_yaml_file(file_path):
    _, file_extension = os.path.splitext(file_path)
    return file_extension.lower() in ('.yaml', '.yml')

def create_connections(directory_path) -> None:
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            file_path = os.path.join(root, file)
            if is_yaml_file(file_path):
                create_connection(file_path)


if __name__ == "__main__":
    create_connections(os.path.join(os.path.dirname(__file__), "connections"))
    if exists():
        start()
    else:
        main_script = os.path.join(os.path.dirname(__file__), "main.py")
        sys.argv = ["streamlit", "run", main_script, "--global.developmentMode=false"]
        stcli.main(prog_name="streamlit")