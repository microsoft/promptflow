# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from promptflow._sdk._constants import CDN_LINK, JS_FILENAME


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
    metrics: Optional[Dict[str, Any]] = None
    dag: Optional[str] = None
    flow_tools_json: Optional[dict] = None


@dataclass
class RunVisualization:
    detail: List[RunDetail]
    metadata: List[RunMetadata]


@dataclass
class VisualizationRender:
    data: dict
    version: str
    js_link: Optional[str] = None

    def __post_init__(self):
        self.data = json.dumps(json.dumps(self.data))  # double json.dumps to match JS requirements
        self.js_link = CDN_LINK.format(version=self.version, filename=JS_FILENAME)
