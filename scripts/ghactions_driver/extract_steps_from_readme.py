import argparse
import io
import re
from pathlib import Path

import panflute
import pypandoc
from jinja2 import Environment, FileSystemLoader

from readme_step import ReadmeStepsManage

full_text = ""


def strip_comments(code):
    code = str(code)
    code = re.sub(r"(?m)^ *#.*\n?", "", code)  # remove comments
    splits = [ll.rstrip() for ll in code.splitlines() if ll.strip()]  # remove empty
    splits_no_interactive = [
        split
        for split in splits
        if "interactive" not in split and "pf flow serve" not in split
    ]  # remove --interactive and pf flow serve and pf export docker
    text = "\n".join([ll.rstrip() for ll in splits_no_interactive])
    # replacements
    text = text.replace("<your_api_key>", "$aoai_api_key")
    text = text.replace("<your_api_base>", "$aoai_api_endpoint")
    text = text.replace("<your_subscription_id>", "$test_workspace_sub_id")
    text = text.replace("<your_resource_group_id>", "$test_workspace_rg")
    text = text.replace("<your_workspace_name>", "$test_workspace_name")
    return text


def action(elem, doc):
    global full_text
    if isinstance(elem, panflute.CodeBlock) and "bash" in elem.classes:
        full_text = "\n".join([full_text, strip_comments(elem.text)])


def readme_parser(filename: str):
    real_filename = Path(ReadmeStepsManage.git_base_dir()) / filename
    data = pypandoc.convert_file(str(real_filename), "json")
    f = io.StringIO(data)
    doc = panflute.load(f)
    panflute.run_filter(action, doc=doc)


def write_readme_shell(readme_path: str, output_folder: str):
    readme_parser(readme_path)
    Path(ReadmeStepsManage.git_base_dir())
    bash_script_path = (
        Path(ReadmeStepsManage.git_base_dir()) / output_folder / "bash_script.sh"
    )
    template_env = Environment(
        loader=FileSystemLoader(
            Path(ReadmeStepsManage.git_base_dir())
            / "scripts/ghactions_driver/bash_script"
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
