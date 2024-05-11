# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

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
    @staticmethod
    def get_template_category(key):
        return key.split("/")[0]

    @staticmethod
    def get_template_key(key):
        filepath = key.rsplit(".json")[0]
        parts = str(filepath).split("/")
        filename = ContentHarmTemplatesUtils.json_name_to_md_name(parts[-1])
        prefix = parts[:-1]
        prefix.append(filename)

        return "/".join(prefix)

    @staticmethod
    def json_name_to_md_name(name):
        result = name.replace("_aml", "")

        return result + ".md"


class AdversarialTemplate:
    def __init__(self, template_name, text, context_key, template_parameters=None):
        self.text = text
        self.context_key = context_key
        self.template_name = template_name
        self.template_parameters = template_parameters

    def __str__(self):
        return "{{ch_template_placeholder}}"


class AdversarialTemplateHandler:
    def __init__(self, azure_ai_project, rai_client):
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

    def get_template(self, template_name):
        if template_name in CONTENT_HARM_TEMPLATES_COLLECTION_KEY:
            return AdversarialTemplate(template_name=template_name, text=None, context_key=[], template_parameters=None)
