import subprocess
import os
import json


def setup_promptflow(requirement_path) -> None:
    if os.path.exists(requirement_path):
        print("- Setting up the promptflow requirements")
        cmds = ["pip", "install", "-q", "-r", requirement_path]
        subprocess.run(cmds)
    else:
        print("- Setting up the promptflow")
        cmds = ["pip", "install", "promptflow", "-q"]
        subprocess.run(cmds)

        print("- Setting up the promptflow-tools")
        cmds = ["pip", "install", "promptflow-tools", "-q"]
        subprocess.run(cmds)


def create_connection(directory_path) -> None:
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            file_path = os.path.join(root, file)
            subprocess.run(["pf", "connection", "create", "--file", file_path])


def set_environment_variable(file_path) -> None:
    with open(file_path, "r") as file:
        json_data = json.load(file)
    environment_variables = list(json_data.keys())
    for environment_variable in environment_variables:
        # Check if the required environment variable is set
        if not os.environ.get(environment_variable):
            print(f"{environment_variable} is not set.")
            user_input = input(f"Please enter the value for {environment_variable}: ")
            # Set the environment variable
            os.environ[environment_variable] = user_input


if __name__ == "__main__":
    setup_promptflow("./flow/requirements.txt")
    create_connection("./connections")
    set_environment_variable("./settings.json")
    # Execute 'pf flow serve' command
    subprocess.run(["pf", "flow", "serve", "--source", "flow", "--host", "0.0.0.0"])
