# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from jinja2 import Environment as JinjaEnvironment
from jinja2 import FileSystemLoader as JinjaFileSystemLoader
from jinja2 import meta as JinjaMeta

from promptflow.evals.synthetic.simulator import _template_dir as template_dir
from promptflow.evals.synthetic.simulator.templates._templates import (
    ALL_TEMPLATES,
    CH_TEMPLATES_COLLECTION_KEY,
    CONTEXT_KEY,
)


class Template:
    def __init__(self, template_name, text, context_key, content_harm=False, template_parameters=None):
        self.text = text
        self.context_key = context_key
        self.template_name = template_name
        self.content_harm = content_harm
        self.template_parameters = template_parameters

    def __str__(self):
        if self.content_harm:
            return "{{ch_template_placeholder}}"
        return self.text

    def __to_ch_templates(self):  # pylint: disable=unused-private-member
        pass


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


class SimulatorTemplates:
    def __init__(self, rai_client=None):
        self.cached_templates_source = {}
        self.template_env = JinjaEnvironment(loader=JinjaFileSystemLoader(searchpath=template_dir))
        self.rai_client = rai_client
        self.categorized_ch_parameters = None

    def get_templates_list(self):
        return ALL_TEMPLATES.keys()

    def _get_template_context_key(self, template_name):
        return CONTEXT_KEY.get(template_name)

    async def _get_ch_template_collections(self, collection_key):
        if self.rai_client is None:
            raise EnvironmentError("Service client is unavailable. Ai client is required to use rai service.")

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

                template = Template(
                    template_name=key, text=None, context_key=[], content_harm=True, template_parameters=params
                )

                ch_templates.append(template)
        return ch_templates

    def get_template(self, template_name):
        if template_name in CH_TEMPLATES_COLLECTION_KEY:
            return Template(
                template_name=template_name, text=None, context_key=[], content_harm=True, template_parameters=None
            )

        if template_name in self.cached_templates_source:
            template, _, _ = self.cached_templates_source[template_name]
            return Template(template_name, template, self._get_template_context_key(template_name))

        for name, (template, _, _) in self.cached_templates_source.items():
            if name == template_name:
                return Template(template_name, template, self._get_template_context_key(template_name))

        if template_name not in ALL_TEMPLATES:
            raise ValueError(f"{template_name} not in templates library.")

        template_source = self.template_env.loader.get_source(self.template_env, ALL_TEMPLATES[template_name])
        self.cached_templates_source[template_name] = template_source

        template, _, _ = template_source
        return Template(template_name, template, self._get_template_context_key(template_name))

    def get_template_parameters(self, template_name):
        # make sure template is cached
        self.get_template(template_name)

        template_source = self.cached_templates_source[template_name]
        vars = JinjaMeta.find_undeclared_variables(self.template_env.parse(template_source))
        return {k: None for k in vars}
