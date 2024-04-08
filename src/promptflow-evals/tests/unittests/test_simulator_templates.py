# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# flake8: noqa: F401

import os
from unittest.mock import Mock, patch

import pytest

from promptflow.evals.synthetic.simulator import _template_dir as template_dir
from promptflow.evals.synthetic.simulator.templates._templates import SUMMARIZATION, SUMMARIZATION_PATH
from promptflow.evals.synthetic.simulator.templates.simulator_templates import SimulatorTemplates


@pytest.mark.unittest
class TestSimulator:
    def test_simulator_templates_get_param(self):
        st = SimulatorTemplates()

        params = st.get_template_parameters(SUMMARIZATION)

        assert set(params.keys()) == set(["name", "chatbot_name", "filename", "file_content"])

    def test_simulator_templates_get(self):
        st = SimulatorTemplates()
        template = st.get_template(SUMMARIZATION)

        with open(os.path.join(template_dir, SUMMARIZATION_PATH), "r") as f:
            read_template = f.read()

        assert str(template) == read_template
