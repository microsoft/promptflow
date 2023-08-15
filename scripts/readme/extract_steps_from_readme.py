import argparse
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from ghactions_driver.readme_parse import readme_parser
from ghactions_driver.readme_step import ReadmeStepsManage


def write_readme_shell(readme_path: str, output_folder: str):
    full_text = readme_parser(readme_path)
    Path(ReadmeStepsManage.git_base_dir())
    bash_script_path = (
            Path(ReadmeStepsManage.git_base_dir()) / output_folder / "bash_script.sh"
    )
    template_env = Environment(
        loader=FileSystemLoader(
            Path(ReadmeStepsManage.git_base_dir())
            / "scripts/readme/ghactions_driver/bash_script"
        )
    )
    bash_script_template = template_env.get_template("bash_script.sh.jinja2")
    with open(bash_script_path, "w") as f:
        f.write(bash_script_template.render({"command": full_text}))


if __name__ == "__main__":
    # setup argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-f",
        "--readme-file",
        help="Input README.md example 'examples/flows/standard/basic/README.md'",
    )
    parser.add_argument(
        "-o",
        "--output-folder",
        help="Output folder for bash_script.sh example 'examples/flows/standard/basic/'",
    )
    args = parser.parse_args()
    write_readme_shell(args.readme_file, args.output_folder)
