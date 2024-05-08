# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import tempfile
import webbrowser
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from promptflow._sdk._constants import VIS_HTML_TMPL
from promptflow._sdk._utilities.general_utils import render_jinja_template
from promptflow.contracts._run_management import VisualizationRender


def generate_html_string(data: dict) -> str:
    visualization_render = VisualizationRender(data=data)
    return render_jinja_template(VIS_HTML_TMPL, **asdict(visualization_render))


def generate_trace_ui_html_string(trace_ui_url: str) -> str:
    # this HTML will automatically redirect to the trace UI page when opened
    return f'<!DOCTYPE html><html><head><meta http-equiv="refresh" content="0; URL=\'{trace_ui_url}\'" /></head><body></body></html>'  # noqa: E501


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
