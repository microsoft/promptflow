# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import shutil
import tempfile
import webbrowser
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from promptflow._sdk._constants import VIS_HTML_TMPL, VIS_JS_BUNDLE_FILENAME
from promptflow._sdk._utils import render_jinja_template
from promptflow.contracts._run_management import VisualizationRender


def generate_html_string(data: dict) -> str:
    visualization_render = VisualizationRender(data=data)
    return render_jinja_template(VIS_HTML_TMPL, **asdict(visualization_render))


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


def dump_js_bundle(html_path: str) -> None:
    js_bundle_src_path = Path(__file__).parent / "data" / VIS_JS_BUNDLE_FILENAME
    js_bundle_dst_path = Path(html_path).parent / VIS_JS_BUNDLE_FILENAME
    shutil.copy(js_bundle_src_path, js_bundle_dst_path)


def dump_html(html_string: str, html_path: Optional[str] = None, open_html: bool = True) -> None:
    if html_path is not None:
        with open(html_path, "w") as f:
            f.write(html_string)
    else:
        with tempfile.NamedTemporaryFile(prefix="pf-visualize-detail-", suffix=".html", delete=False) as f:
            f.write(html_string.encode("utf-8"))
            html_path = f.name

    dump_js_bundle(html_path)

    if open_html:
        try_to_open_html(html_path)
