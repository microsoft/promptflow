from promptflow.tools.template_rendering import render_template_jinja2
from promptflow.tools.common import PromptResult
from unittest.mock import patch

import uuid


class TestTemplateRendering:
    def test_render_template_jinja2(self):
        template = """
        {{flow_input}}
        {{prompt_result_1}}
        {{prompt_result_2}}
        {{node_input}}
        """
        prompt_result_1 = PromptResult("#System:\n")
        prompt_result_1.set_escape_string("#fake_uuid_1:\n")
        prompt_result_1.set_escape_mapping({"fake_uuid_1": "System"})

        prompt_result_2 = PromptResult("#System:\n")
        prompt_result_2.set_escape_string("#fake_uuid_2:\n")
        prompt_result_2.set_escape_mapping({"fake_uuid_2": "System"})

        expected = PromptResult("""
        #Assistant:\n
        #System:\n
        #System:\n
        #User:\n
        """)
        expected.set_escape_string("""
        #fake_uuid:\n
        #fake_uuid_1:\n
        #fake_uuid_2:\n
        #User:\n
        """)
        expected.set_escape_mapping({"fake_uuid_1": "System", "fake_uuid_2": "System", "fake_uuid": "Assistant"})

        with patch.object(uuid, 'uuid4', return_value='fake_uuid'):
            actual = render_template_jinja2(
                template,
                flow_input="#Assistant:\n",
                prompt_result_1=prompt_result_1,
                prompt_result_2=prompt_result_2,
                node_input="#User:\n",
                _inputs_to_escape=["flow_input"],
            )
            assert actual == expected
            assert actual.get_escape_mapping() == expected.get_escape_mapping()
            assert actual.get_escape_string() == expected.get_escape_string()
