from promptflow.tools.template_rendering import render_template_jinja2
from promptflow.tools.common import PromptResult
from unittest.mock import patch

import uuid


class TestTemplateRendering:
    def test_render_template_jinja2(self):
        template = """
        {{flow_input}}
        {{prompt_result}}
        {{node_input}}
        """
        prompt_result = PromptResult("#System:\n")
        prompt_result.set_escape_string("#fake_uuid:\n")
        prompt_result.set_escape_mapping({"System": "fake_uuid"})

        expected = PromptResult("""
        #Assistant:\n
        #System:\n
        #User:\n
        """)
        expected.set_escape_string("""
        #fake_uuid_1:\n
        #fake_uuid:\n
        #User:\n
        """)
        expected.set_escape_mapping({"System": "fake_uuid", "Assistant": "fake_uuid_1"})

        with patch.object(uuid, 'uuid4', side_effect=['fake_uuid_1', 'fake_uuid_2']):
            actual = render_template_jinja2(
                template,
                flow_input="#Assistant:\n",
                prompt_result=prompt_result,
                node_input="#User:\n",
                _inputs_to_escape=["flow_input"],
            )
            assert actual == expected
            assert actual.get_escape_mapping() == expected.get_escape_mapping()
            assert actual.get_escape_string() == expected.get_escape_string()
