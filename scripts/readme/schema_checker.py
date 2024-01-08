from functools import reduce
from promptflow._sdk._load_functions import load_yaml
from ghactions_driver.readme_step import ReadmeStepsManage
from pathlib import Path


def main(input_glob_flow_dag):
    # check if flow.dag.yaml contains schema field.
    def set_add(p, q):
        return p | q

    error = False
    globs = reduce(set_add, [set(Path(ReadmeStepsManage.git_base_dir()).glob(p)) for p in input_glob_flow_dag], set())
    flow_dag_items = sorted([i for i in globs])

    for file in flow_dag_items:
        data = load_yaml(file)
        if "$schema" not in data.keys():
            print(f"{file} does not contain $schema field.")
            error = True

    if error:
        raise Exception("Some flow.dag.yaml doesn't contain $schema field.")
    else:
        print("All flow.dag.yaml contain $schema field.")


if __name__ == "__main__":
    input_glob_flow_dag = [
        "examples/**/flow.dag.yaml",
    ]
    main(input_glob_flow_dag)
