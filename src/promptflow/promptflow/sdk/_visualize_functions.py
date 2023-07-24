# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import tempfile
import webbrowser
from pathlib import Path
from typing import Optional

import yaml

from promptflow.sdk._constants import VisualizeDetailConstants


def generate_html_string(yaml_string) -> str:
    data = yaml.safe_load(yaml_string)
    json_string = json.dumps(json.dumps(data))  # double json.dumps to match JS requirements
    # read HTML template
    with open(VisualizeDetailConstants.HTML_TEMPLATE, "r") as f:
        html_template = f.read()
    # replace and dump
    html_string = html_template.replace(VisualizeDetailConstants.DATA_PLACEHOLDER, json_string)
    html_string = html_string.replace(VisualizeDetailConstants.CDN_PLACEHOLDER, VisualizeDetailConstants.CDN_LINK)
    return html_string


def try_to_open_html(html_path: str) -> None:
    print(f"The HTML file is generated at {str(Path(html_path).resolve().absolute())!r}.")
    print("Trying to view the result in a web browser...")
    web_browser_opened = False
    web_browser_opened = webbrowser.open(f"file://{html_path}")
    if not web_browser_opened:
        print(
            f"Failed to visualize from the web browser, the HTML file locates at {html_path!r}.\n"
            "You can manually open it with your web browser, or try SDK to visualize it."
        )
    else:
        print("Successfully visualized from the web browser.")


def dump_html(html_string: str, html_path: Optional[str] = None, open_html: bool = True) -> None:
    if html_path is not None:
        with open(html_path, "w") as f:
            f.write(html_string)
    else:
        with tempfile.NamedTemporaryFile(prefix="pf-visualize-detail-", suffix=".html", delete=False) as f:
            f.write(html_string.encode("utf-8"))
            html_path = f.name

    if open_html:
        try_to_open_html(html_path)
