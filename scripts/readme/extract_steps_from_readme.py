import argparse
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from ghactions_driver.readme_parse import readme_parser
from ghactions_driver.readme_step import ReadmeStepsManage


def comment_pytest(full_text: str):
    # separate full_text into lines, group them by start with pytest or not
    full_text_lines = full_text.split("\n")
    full_text_pytest = []
    full_text_no_pytest = []
    for line in full_text_lines:
        if line.strip().startswith("python -m unittest"):
            full_text_pytest.append(line)
        else:
            full_text_no_pytest.append(line)
    return "\n".join(full_text_no_pytest), "\n".join(full_text_pytest)


def write_readme_shell(readme_path: str, output_folder: str):
    full_text = readme_parser(readme_path)
    full_text, full_text_pytest = comment_pytest(full_text)
    Path(ReadmeStepsManage.git_base_dir())
    bash_script_path = (
        Path(ReadmeStepsManage.git_base_dir()) / output_folder / "bash_script.sh"
    )
    bash_script_backup = (
        Path(ReadmeStepsManage.git_base_dir()) / output_folder / "bash_script_pytest.sh"
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
    if full_text_pytest != "":
        with open(bash_script_backup, "w") as f:
            f.write(bash_script_template.render({"command": full_text_pytest}))


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
