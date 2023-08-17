import io
import re
from pathlib import Path

import panflute
import pypandoc

from .readme_step import ReadmeStepsManage


def strip_comments(code):
    code = str(code)
    code = re.sub(r"(?m)^ *#.*\n?", "", code)  # remove comments
    splits = [ll.rstrip() for ll in code.splitlines() if ll.strip()]  # remove empty
    splits_no_interactive = [
        split
        for split in splits
        if "interactive" not in split
        and "pf flow serve" not in split
        and "pf connection delete" not in split
    ]  # remove --interactive and pf flow serve and pf export docker
    text = "\n".join([ll.rstrip() for ll in splits_no_interactive])
    # replacements
    text = text.replace("<your_api_key>", "$aoai_api_key")
    text = text.replace("<your_api_base>", "$aoai_api_endpoint")
    text = text.replace("<your_subscription_id>", "$test_workspace_sub_id")
    text = text.replace("<your_resource_group_name>", "$test_workspace_rg")
    text = text.replace("<your_workspace_name>", "$test_workspace_name")
    return text


def prepare(doc):
    doc.full_text = ""


def action(elem, doc):
    if isinstance(elem, panflute.CodeBlock) and "bash" in elem.classes:
        doc.full_text = "\n".join([doc.full_text, strip_comments(elem.text)])


def readme_parser(filename: str):
    real_filename = Path(ReadmeStepsManage.git_base_dir()) / filename
    data = pypandoc.convert_file(str(real_filename), "json")
    f = io.StringIO(data)
    doc = panflute.load(f)
    panflute.run_filter(action, prepare, doc=doc)
    return doc.full_text
