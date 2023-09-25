# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from promptflow._sdk._constants import VIS_LIB_CDN_LINK_TMPL


@dataclass
class RunDetail:
    flow_runs: List[dict]
    node_runs: List[dict]


@dataclass
class RunMetadata:
    name: str
    display_name: str
    create_time: str
    tags: Optional[List[Dict[str, str]]]
    lineage: Optional[str]
    metrics: Optional[Dict[str, Any]]
    dag: Optional[str]
    flow_tools_json: Optional[dict]


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
        self.js_link = VIS_LIB_CDN_LINK_TMPL.format(version=self.version)
