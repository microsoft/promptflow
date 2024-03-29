from promptflow._sdk._load_functions import load_yaml
from promptflow._sdk._pf_client import PFClient
from ghactions_driver.readme_step import ReadmeStepsManage
from pathlib import Path
import os
import subprocess
import sys


def install(filename):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", filename])


def main(input_glob_flow_dag):
    # check if flow.dag.yaml contains schema field.

    error = False
    globs = set()
    pf_client = PFClient()

    for p in input_glob_flow_dag:
        globs = globs | set(Path(ReadmeStepsManage.git_base_dir()).glob(p))
    flow_dag_items = sorted([i for i in globs])

    for file in flow_dag_items:
        data = load_yaml(file)
        if "$schema" not in data.keys():
            print(f"{file} does not contain $schema field.")
            error = True
        if error is False:
            new_links = []
            if (Path(file).parent / "requirements.txt").exists():
                # remove all promptflow lines in requirements.txt
                # and save time, or else it will check all dependencies of promptflow time by time
                with open(Path(file).parent / "requirements.txt", "r") as f:
                    lines = f.readlines()
                with open(Path(file).parent / "requirements.txt", "w") as f:
                    for line in lines:
                        if "promptflow" not in line:
                            f.write(line)

                install(Path(file).parent / "requirements.txt")

            if "flow-with-symlinks" in str(file):
                saved_path = os.getcwd()
                os.chdir(str(file.parent))
                source_folder = Path("../web-classification")
                for file_name in os.listdir(source_folder):
                    if not Path(file_name).exists():
                        os.symlink(
                            source_folder / file_name,
                            file_name
                        )
                        new_links.append(file_name)
            validation_result = pf_client.flows.validate(
                flow=file,
            )
            if "flow-with-symlinks" in str(file):
                for link in new_links:
                    os.remove(link)
                os.chdir(saved_path)
            print(f"VALIDATE {file}: \n" + repr(validation_result))
            if not validation_result.passed:
                print(f"{file} is not valid.")
                error = True
            if len(validation_result._warnings) > 0:
                print(f"{file} has warnings.")
                error = True

    if error:
        raise Exception("Some flow.dag.yaml validation failed.")
    else:
        print("All flow.dag.yaml validation completed.")


if __name__ == "__main__":
    input_glob_flow_dag = [
        "examples/**/flow.dag.yaml",
    ]
    main(input_glob_flow_dag)
