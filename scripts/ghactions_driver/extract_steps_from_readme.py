import io
from pathlib import Path
import pypandoc
import panflute
import re
from .readme_step import ReadmeStepsManage, ReadmeSteps


def strip_comments(code):
    code = str(code)
    code = re.sub(r"(?m)^ *#.*\n?", "", code)
    text = "\n".join([ll.rstrip() for ll in code.splitlines() if ll.strip()])
    # replacements
    text = text.replace("<your_api_key>", "${{ secrets.AOAI_API_KEY }}")
    text = text.replace("<your_api_base>", "${{ secrets.AOAI_API_ENDPOINT }}")
    text = text.replace(
        "<your_subscription_id>", "${{ secrets.TEST_WORKSPACE_SUB_ID }}"
    )
    text = text.replace("<your_resource_group_id>", "${{ secrets.TEST_WORKSPACE_RG }}")
    text = text.replace("<your_workspace_name>", "${{ secrets.TEST_WORKSPACE_NAME }}")
    ReadmeSteps.bash(text)
    return text


def action(elem, doc):
    if isinstance(elem, panflute.CodeBlock):
        print(strip_comments(elem.text))


def readme_parser(filename: str):
    data = pypandoc.convert_file(filename, "json")
    f = io.StringIO(data)
    doc = panflute.load(f)
    panflute.run_filter(action, doc=doc)


def write_readme_workflow(readme_path):
    relative_path = Path(readme_path).relative_to(
        Path(ReadmeStepsManage.git_base_dir())
    )
    workflow_path = relative_path.as_posix()
    relative_name_path = Path(readme_path).relative_to(
        Path(ReadmeStepsManage.git_base_dir()) / "examples"
    )
    workflow_name = relative_name_path.as_posix().replace("/", "_")

    ReadmeSteps.setup_target(
        workflow_path,
        "Readme.md",
        "basic_workflow_replace.yml.jinja2",
        f"{workflow_name}.yml",
    )
    ReadmeSteps.install_dependencies()
    ReadmeSteps.install_dev_dependencies()
    ReadmeSteps.azure_login()
    ReadmeSteps.create_env()
    ReadmeSteps.create_run_yaml()

    readme_parser(str(readme_path / "Readme.md"))
    ReadmeStepsManage.write_workflow(workflow_name, "auto_generated_steps")
    ReadmeSteps.cleanup()
