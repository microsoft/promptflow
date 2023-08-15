# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
from dataclasses import dataclass
from typing import Dict, List, Optional

from promptflow._sdk._constants import (
    CDN_LINK,
    CSS_FILENAME,
    JS_FILENAME,
    VISUALIZE_VERSION,
)


@dataclass
class RunDetail:
    flow_runs: List[dict]
    node_runs: List[dict]


@dataclass
class RunMetadata:
    name: str
    display_name: str
    tags: Optional[List[Dict[str, str]]]
    lineage: Optional[str]


@dataclass
class RunVisualization:
    detail: List[RunDetail]
    metadata: List[RunMetadata]


@dataclass
class VisualizationRender:
    data: dict
    js_link: Optional[str] = None
    css_link: Optional[str] = None

    def __post_init__(self):
        self.data = json.dumps(
            json.dumps(self.data)
        )  # double json.dumps to match JS requirements
        self.js_link = CDN_LINK.format(version=VISUALIZE_VERSION, filename=JS_FILENAME)
        self.css_link = CDN_LINK.format(
            version=VISUALIZE_VERSION, filename=CSS_FILENAME
        )
