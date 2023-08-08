import argparse
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from ghactions_driver.readme_step import ReadmeStepsManage, ReadmeSteps
from ghactions_driver.extract_steps_from_readme import write_readme_workflow


def main(args):
    globs = [sorted(Path(ReadmeStepsManage.git_base_dir()).glob(p)) for p in args.input_glob]
    readme_items = sorted([j for i in globs for j in i])

    for readme in readme_items:
        workflow_name = readme.parent.relative_to(ReadmeStepsManage.git_base_dir())
        pipeline_name = "auto_generated_steps"
        # Deal with readme
        write_readme_workflow(workflow_name.resolve(), pipeline_name)
        ReadmeSteps.cleanup()


if __name__ == "__main__":
    # setup argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-g", "--input-glob", nargs="+", help="Input Readme.md glob example 'examples/flows/**/Readme.md'"
    )
    args = parser.parse_args()

    # call main
    main(args)
