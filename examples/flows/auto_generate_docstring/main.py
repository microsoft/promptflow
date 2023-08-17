import logging

from dotenv import load_dotenv
from file import File
from promptflow import tool
from divider import Divider
from AzureOpenAi import ChatLLM
from prompt import PromptException, docstring_prompt


@tool
def load_code(code_path: str):
    file = File(code_path)
    return file.content()


@tool
def divide_code(file_content: str):
    divided = Divider.divide_file(file_content)
    return divided


@tool
def generate_docstring(divided: list[str]):
    llm = ChatLLM(module="gpt-35-turbo")
    res_code = []
    divided = list(reversed(divided))
    while len(divided) and len(divided) < 100:
        item = divided.pop()
        try:
            docstring = llm.query(docstring_prompt(item))
        except PromptException as e:
            logging.error(e.message)
            divided_tmp = Divider.divide_func(item)
            if len(divided_tmp) > 1:
                divided.extend(list(reversed(divided_tmp)))
                continue
            else:
                docstring = ''
        res_code.append(Divider.merge_doc2code(docstring, item))
    return res_code


@tool
def combine_code(divided: list[str]):
    code = Divider.combine(divided)
    return code


def execute_pipeline(*pipelines, args=None):
    for pipeline in pipelines:
        args = pipeline(args)
    return args


code_str = """
class PipelineComponentBuilder:
    # map from python built-in type to component type
    # pylint: disable=too-many-instance-attributes
    DEFAULT_DATA_TYPE_MAPPING = {
        "float": "number",
        "int": "integer",
        "bool": "boolean",
        "str": "string",
    }
    DEFAULT_OUTPUT_NAME = "output"

    def __init__(
        self,
        func: Callable,
        name=None,
        version=None,
        display_name=None,
        description=None,
        default_datastore=None,
        tags=None,
        source_path=None,
        non_pipeline_inputs=None,
    ) - >None:
        self.func = func
        name = name if name else func.__name__
        display_name = display_name if display_name else name
        description = description if description else func.__doc__
        self._args_description = parse_args_description_from_docstring(func.__doc__)
        if name is None:
            name = func.__name__
        # List of nodes, order by it's creation order in pipeline.
        self.nodes = []
        self.non_pipeline_parameter_names = non_pipeline_inputs or []
        # A dict of inputs name to InputDefinition.
        # TODO: infer pipeline component input meta from assignment
        self.inputs = self._build_inputs(func)
        self.output_annotation = self._get_output_annotation(func)
        self._name = name
        self.version = version
        self.display_name = display_name
        self.description = description
        self.default_datastore = default_datastore
        self.tags = tags
        self.source_path = source_path

    @property
    def name(self):
        return self._name

    def add_node(self, node: Union[BaseNode, AutoMLJob]):
        self.nodes.append(node)

    def build(
        self, *, user_provided_kwargs=None, non_pipeline_inputs_dict=None, non_pipeline_inputs=None
    ) -> PipelineComponent:
        if user_provided_kwargs is None:
            user_provided_kwargs = {}
        # Clear nodes as we may call build multiple times.
        self.nodes = []

        kwargs = _build_pipeline_parameter(
            func=self.func,
            user_provided_kwargs=user_provided_kwargs,
            # TODO: support result() for pipeline input inside parameter group
            group_default_kwargs=self._get_group_parameter_defaults(),
            non_pipeline_inputs=non_pipeline_inputs,
        )
        kwargs.update(non_pipeline_inputs_dict or {})

        # Use a dict to store all variables in self.func
        # We use this stack to store the dsl pipeline definition hierarchy
        _definition_builder_stack.push(self)

        try:
            outputs, _locals = get_outputs_and_locals(self.func, kwargs)
        finally:
            _definition_builder_stack.pop()

        if outputs is None:
            outputs = {}

        jobs = self._update_nodes_variable_names(_locals)
        pipeline_component = PipelineComponent(
            name=self.name,
            version=self.version,
            display_name=self.display_name,
            description=self.description,
            inputs=self.inputs,
            jobs=jobs,
            tags=self.tags,
            source_path=self.source_path,
            _source=ComponentSource.DSL,
        )
        # TODO: Refine here. The output can not be built first then pass into pipeline component creation,
        # exception will be raised in component.build_validate_io().
        pipeline_component._outputs = self._build_pipeline_outputs(outputs)
        return pipeline_component

    def _validate_group_annotation(self, name: str, val: GroupInput):
        for k, v in val.values.items():
            if isinstance(v, GroupInput):
                self._validate_group_annotation(k, v)
            elif isinstance(v, Output):
                # TODO(2097468): automatically change it to Input when used in input annotation
                raise UserErrorException("Output annotation cannot be used in @pipeline.")
            elif isinstance(v, Input):
                if v.type not in IOConstants.PRIMITIVE_STR_2_TYPE:
                    # TODO(2097478): support port type groups
                    raise UserErrorException(f"Only primitive types can be used as input of group, got {v.type}")
            else:
                raise UserErrorException(f"Unsupported annotation type {type(v)} for group field {name}.{k}")

    def _build_inputs(self, func):
        inputs = _get_param_with_standard_annotation(func, is_func=True, skip_params=self.non_pipeline_parameter_names)
        for k, v in inputs.items():
            if isinstance(v, GroupInput):
                self._validate_group_annotation(name=k, val=v)
            # add arg description
            if k in self._args_description:
                v["description"] = self._args_description[k]
        return inputs

    def _build_pipeline_outputs(self, outputs: typing.Dict[str, NodeOutput]):
        error_msg = (
            "The return type of dsl.pipeline decorated function should be a mapping from output name to "
            "azure.ai.ml.Output with owner."
        )
        if is_group(outputs):
            outputs = {key: val for key, val in outputs.__dict__.items() if val}
        if not isinstance(outputs, dict):
            raise UserErrorException(message=error_msg, no_personal_data_message=error_msg)
        output_dict = {}
        output_meta_dict = {}
        for key, value in outputs.items():
            if not isinstance(key, str) or not isinstance(value, NodeOutput) or value._owner is None:
                raise UserErrorException(message=error_msg, no_personal_data_message=error_msg)
            if value._meta is not None:
                meta = value._meta
            else:
                meta = Output(type=value.type, path=value.path, mode=value.mode, description=value.description)

            # Hack: map internal output type to pipeline output type
            def _map_internal_output_type(_meta):
                if type(_meta).__name__ != "InternalOutput":
                    return _meta.type
                return _meta.map_pipeline_output_type()

            # Note: Here we set PipelineOutput as Pipeline's output definition as we need output binding.
            output_meta = Output(type=_map_internal_output_type(meta), description=meta.description, mode=meta.mode)
            pipeline_output = PipelineOutput(
                port_name=key,
                data=None,
                # meta is used to create pipeline component, store it here to make sure pipeline component and inner
                # node output type are consistent
                meta=output_meta,
                owner="pipeline",
                description=self._args_description.get(key, None),
                # store original node output to be able to trace back to inner node from a pipeline output builder.
                binding_output=value,
            )
            # copy node level output setting to pipeline output
            copy_output_setting(source=value._owner.outputs[value._port_name], target=pipeline_output)

            value._owner.outputs[value._port_name]._data = pipeline_output

            output_dict[key] = pipeline_output
            output_meta_dict[key] = output_meta._to_dict()

        self._validate_inferred_outputs(output_meta_dict, output_dict)
        return output_dict

    def _get_group_parameter_defaults(self):
        group_defaults = {}
        for key, val in self.inputs.items():
            if not isinstance(val, GroupInput):
                continue
            # Copy and insert top-level parameter name into group names for all items
            group_defaults[key] = copy.deepcopy(val.default)
            group_defaults[key].insert_group_name_for_items(key)
        return group_defaults

    def _update_nodes_variable_names(self, func_variables: dict):
        def _get_name_or_component_name(node: Union[BaseNode, AutoMLJob]):
            # TODO(1979547): refactor this
            if isinstance(node, AutoMLJob):
                return node.name or _sanitize_python_variable_name(node.__class__.__name__)
            if isinstance(node, ControlFlowNode):
                return _sanitize_python_variable_name(node.__class__.__name__)
            return node.name or node._get_component_name()

        valid_component_ids = set(item._instance_id for item in self.nodes)
        id_name_dict = {}
        name_count_dict = {}
        compname_udfname_dict = {}
        local_names = set()
        result = OrderedDict()

        for k, v in func_variables.items():
            # TODO(1979547): refactor this
            if not isinstance(v, (BaseNode, AutoMLJob, PipelineJob, ControlFlowNode)):
                continue
            instance_id = getattr(v, "_instance_id", None)
            if instance_id not in valid_component_ids:
                continue
            name = getattr(v, "name", None) or k
            # for node name _, treat it as anonymous node with name unset
            if name == "_":
                continue

            # User defined name must be valid python identifier
            if not is_valid_node_name(name):
                raise UserErrorException(
                    f"Invalid node name found: {name!r}. Node name must start with a lower letter or underscore, "
                    "and can only contain lower letters, numbers and underscore."
                )

            # Raise error when setting a name that already exists, likely conflict with a variable name
            if name in local_names and instance_id not in id_name_dict:
                raise UserErrorException(
                    f"Duplicate node name found in pipeline: {self.name!r}, "
                    f"node name: {name!r}. Duplicate check is case-insensitive."
                )
            local_names.add(name)
            id_name_dict[v._instance_id] = name
            name_count_dict[name] = 1

        # Find the last user-defined name for the same type of components
        for node in self.nodes:
            _id = node._instance_id
            if _id in id_name_dict:
                compname_udfname_dict[_get_name_or_component_name(node)] = id_name_dict[_id]

        # Refine and fill default name
        # If component name is same, append '_{count}' suffix
        for node in self.nodes:
            _id = node._instance_id
            if _id not in id_name_dict:
                target_name = _get_name_or_component_name(node)
                if node.name is None and target_name in compname_udfname_dict:
                    target_name = compname_udfname_dict[target_name]
                if target_name not in name_count_dict:
                    name_count_dict[target_name] = 0
                name_count_dict[target_name] += 1
                suffix = "" if name_count_dict[target_name] == 1 else f"_{name_count_dict[target_name] - 1}"
                id_name_dict[_id] = f"{_sanitize_python_variable_name(target_name)}{suffix}"
            final_name = id_name_dict[_id]
            node.name = final_name
            result[final_name] = node

            # Validate IO name of node with correct node name, and log warning if there is keyword.
            self._validate_keyword_in_node_io(node)
        return result

    def _update_inputs(self, pipeline_inputs):
        for input_name, value in pipeline_inputs.items():
            if input_name not in self.inputs:
                if isinstance(value, PipelineInput):
                    value = value._data
                if isinstance(value, Input):
                    anno = copy.copy(value)
                elif isinstance(value, NodeOutput):
                    anno = Input(type=value.type)
                else:
                    anno = _get_annotation_by_value(value)
                anno.name = input_name
                anno.description = self._args_description.get(input_name)
                self.inputs[input_name] = anno

    @classmethod
    def _get_output_annotation(cls, func):
        return_annotation = inspect.signature(func).return_annotation

        if is_group(return_annotation):
            outputs = _get_param_with_standard_annotation(return_annotation, is_func=False)
        elif isinstance(return_annotation, Output):
            outputs = {cls.DEFAULT_OUTPUT_NAME: return_annotation}
        else:
            # skip if return annotation is not group or output
            return {}

        output_annotations = {}
        for key, val in outputs.items():
            if isinstance(val, GroupInput):
                raise UserErrorException(message="Nested group annotation is not supported in pipeline output.")
            # normalize annotation since currently annotation in @group will be converted to Input
            if isinstance(val, Input):
                val = Output(type=val.type)
            if not isinstance(val, Output):
                raise UserErrorException(
                    message="Invalid output annotation. "
                    f"Only Output annotation in return annotation is supported. Got {type(val)}."
                )
            output_annotations[key] = val._to_dict()
        return output_annotations

    def _validate_inferred_outputs(self, output_meta_dict: dict, output_dict: dict):
        if not self.output_annotation:
            return
        error_prefix = "Unmatched outputs between actual pipeline output and output in annotation"
        if output_meta_dict.keys() != self.output_annotation.keys():
            raise UserErrorException(
                "{}: actual pipeline component outputs: {}, annotation outputs: {}".format(
                    error_prefix, output_meta_dict.keys(), self.output_annotation.keys()
                )
            )

        unmatched_outputs = []
        for key, actual_output in output_meta_dict.items():
            expected_output = self.output_annotation[key]
            actual_output.pop("description", None)
            expected_description = expected_output.pop("description", None)
            # skip comparing mode since when component's from remote, output mode is not available
            actual_output.pop("mode", None)
            expected_mode = expected_output.pop("mode", None)
            if expected_output != actual_output:
                unmatched_outputs.append(
                    f"{key}: pipeline component output: {actual_output} != annotation output {expected_output}"
                )
            if expected_description:
                output_dict[key]._meta.description = expected_description
                # also copy the description to pipeline job
                output_dict[key].description = expected_description
            if expected_mode:
                output_dict[key]._meta.mode = expected_mode
                # also copy the mode to pipeline job
                output_dict[key].mode = expected_mode

        if unmatched_outputs:
            raise UserErrorException(f"{error_prefix}: {unmatched_outputs}")

    @staticmethod
    def _validate_keyword_in_node_io(node: Union[BaseNode, AutoMLJob]):
        if has_attr_safe(node, "inputs"):
            for input_name in set(node.inputs) & COMPONENT_IO_KEYWORDS:
                module_logger.warning(
                    'Reserved word "%s" is used as input name in node "%s", '
                    "can only be accessed with '%s.inputs[\"%s\"]'",
                    input_name,
                    node.name,
                    node.name,
                    input_name,
                )
        if has_attr_safe(node, "outputs"):
            for output_name in set(node.outputs) & COMPONENT_IO_KEYWORDS:
                module_logger.warning(
                    'Reserved word "%s" is used as output name in node "%s", '
                    "can only be accessed with '%s.outputs[\"%s\"]'",
                    output_name,
                    node.name,
                    node.name,
                    output_name,
                )
                
# This collection is used to record pipeline component builders in current call stack
_definition_builder_stack = _PipelineComponentBuilderStack()
"""
if __name__ == "__main__":
    # load_dotenv()
    # res = execute_pipeline(
    #     load_code,
    #     divide_code,
    #     generate_docstring,
    #     combine_code,
    #     args='./demo_code.py'
    # )
    # print(res)
    divided_tmp = Divider.divide_func(code_str)
    print(len(divided_tmp))
    for item in divided_tmp:
        print(item)
        print('====================')