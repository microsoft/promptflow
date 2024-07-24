# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Any, Dict, Optional

from ._rai_client import RAIClient

CONTENT_HARM_TEMPLATES_COLLECTION_KEY = set(
    [
        "adv_qa",
        "adv_conversation",
        "adv_summarization",
        "adv_search",
        "adv_rewrite",
        "adv_content_gen_ungrounded",
        "adv_content_gen_grounded",
    ]
)


class ContentHarmTemplatesUtils:
    """Content harm templates utility functions."""
    @staticmethod
    def get_template_category(key: str) -> str:
        """Parse category from template key

        :param key: The template key
        :type key: str
        :return: The category
        :rtype: str
        """
        return key.split("/")[0]

    # Bug 3353405: Need to add docstring
    @staticmethod
    def get_template_key(key: str) -> str:  # pylint: disable=missing-function-docstring
        filepath = key.rsplit(".json")[0]
        parts = str(filepath).split("/")
        filename = ContentHarmTemplatesUtils.json_name_to_md_name(parts[-1])
        prefix = parts[:-1]
        prefix.append(filename)

        return "/".join(prefix)

    @staticmethod
    def json_name_to_md_name(name) -> str:
        """Convert JSON filename to Markdown filename

        :param name: The JSON filename
        :type name: str
        :return: The Markdown filename
        :rtype: str
        """
        result = name.replace("_aml", "")

        return result + ".md"


class AdversarialTemplate:
    """Template for adversarial scenarios.

    :param template_name: The name of the template.
    :type template_name: str
    :param text: The template text.
    :type text: str
    :param context_key: The context key.
    :param template_parameters: The template parameters.
    """
    def __init__(self, template_name, text, context_key, template_parameters=None) -> None:
        self.text = text
        self.context_key = context_key
        self.template_name = template_name
        self.template_parameters = template_parameters

    def __str__(self):
        return "{{ch_template_placeholder}}"


class AdversarialTemplateHandler:
    """
    Adversarial template handler constructor.

    :param azure_ai_project: The Azure AI project.
    :type azure_ai_project: Dict[str, Any]
    :param rai_client: The RAI client.
    :type rai_client: ~promptflow.evals.synthetic._model_tools.RAIClient
    """
    def __init__(self, azure_ai_project: Dict[str, Any], rai_client: RAIClient) -> None:
        self.cached_templates_source = {}
        # self.template_env = JinjaEnvironment(loader=JinjaFileSystemLoader(searchpath=template_dir))
        self.azure_ai_project = azure_ai_project
        self.categorized_ch_parameters = None
        self.rai_client = rai_client

    async def _get_content_harm_template_collections(self, collection_key):

        if self.categorized_ch_parameters is None:
            categorized_parameters = {}
            util = ContentHarmTemplatesUtils

            parameters = await self.rai_client.get_contentharm_parameters()

            for k in parameters.keys():
                template_key = util.get_template_key(k)
                categorized_parameters[template_key] = {
                    "parameters": parameters[k],
                    "category": util.get_template_category(k),
                    "parameters_key": k,
                }
            self.categorized_ch_parameters = categorized_parameters

        template_category = collection_key.split("adv_")[-1]

        plist = self.categorized_ch_parameters
        ch_templates = []
        for key, value in plist.items():
            if value["category"] == template_category:
                params = value["parameters"]
                for p in params:
                    p.update({"ch_template_placeholder": "{{ch_template_placeholder}}"})

                template = AdversarialTemplate(template_name=key, text=None, context_key=[], template_parameters=params)

                ch_templates.append(template)
        return ch_templates

    def get_template(self, template_name: str) -> Optional[AdversarialTemplate]:
        """Generate content harm template.

        :param template_name: The name of the template.
        :type template_name: str
        :return: The generated content harm template.
        :rtype: Optional[~promptflow.evals.synthetic._model_tools.AdversarialTemplate]
        """
        if template_name in CONTENT_HARM_TEMPLATES_COLLECTION_KEY:
            return AdversarialTemplate(template_name=template_name, text=None, context_key=[], template_parameters=None)
        return None
