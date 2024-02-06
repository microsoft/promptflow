import json
import os
import time
from copy import copy
from pathlib import Path
from types import GeneratorType

import streamlit as st
from PIL import Image
from streamlit_quill import st_quill
from utils import dict_iter_render_message, parse_image_content, parse_list_from_html, render_single_dict_message

from promptflow import load_flow
from promptflow._constants import STREAMING_ANIMATION_TIME
from promptflow._sdk._submitter.utils import resolve_generator, resolve_generator_output_with_cache
from promptflow._sdk._utils import dump_flow_result
from promptflow._utils.multimedia_utils import convert_multimedia_data_to_base64, persist_multimedia_data

invoker = None


def start():
    def clear_chat() -> None:
        st.session_state.messages = []

    def render_message(role, message_items):
        with st.chat_message(role):
            if is_chat_flow:
                render_single_dict_message(message_items)
            else:
                dict_iter_render_message(message_items)

    def show_conversation() -> None:
        if "messages" not in st.session_state:
            st.session_state.messages = []
            st.session_state.history = []
        if st.session_state.messages:
            for role, message_items in st.session_state.messages:
                render_message(role, message_items)

    def get_chat_history_from_session():
        if "history" in st.session_state:
            return st.session_state.history
        return []

    def post_process_dump_result(response, session_state_history, *, generator_record):
        response = resolve_generator(response, generator_record)
        # Get base64 for multi modal object
        resolved_outputs = {
            k: convert_multimedia_data_to_base64(v, with_type=True, dict_type=True) for k, v in response.output.items()
        }
        st.session_state.messages.append(("assistant", resolved_outputs))
        session_state_history.update({"outputs": response.output})
        st.session_state.history.append(session_state_history)
        if is_chat_flow:
            dump_path = Path(flow_path).parent
            response.output = persist_multimedia_data(
                response.output, base_dir=dump_path, sub_dir=Path(".promptflow/output")
            )
            dump_flow_result(flow_folder=dump_path, flow_result=response, prefix="chat")
        return resolved_outputs

    def submit(**kwargs) -> None:
        # generator record should be reset for each submit
        generator_record = {}

        st.session_state.messages.append(("user", kwargs))
        session_state_history = dict()
        session_state_history.update({"inputs": kwargs})
        with container:
            render_message("user", kwargs)
        # Force append chat history to kwargs
        if is_chat_flow:
            response = run_flow({chat_history_input_name: get_chat_history_from_session(), **kwargs})
        else:
            response = run_flow(kwargs)

        if response.run_info.status.value == "Failed":
            raise Exception(response.run_info.error)

        if is_streaming:
            # Display assistant response in chat message container
            with container:
                with st.chat_message("assistant"):
                    message_placeholder = st.empty()
                    full_response = f"{chat_output_name}: "
                    prefix_length = len(full_response)
                    chat_output = response.output[chat_output_name]
                    if isinstance(chat_output, GeneratorType):
                        # Simulate stream of response with milliseconds delay
                        for chunk in resolve_generator_output_with_cache(
                            chat_output, generator_record, generator_key=f"run.outputs.{chat_output_name}"
                        ):
                            # there should be no extra spaces between adjacent chunks?
                            full_response += chunk
                            time.sleep(STREAMING_ANIMATION_TIME)
                            # Add a blinking cursor to simulate typing
                            message_placeholder.markdown(full_response + "▌")
                        message_placeholder.markdown(full_response)
                        response.output[chat_output_name] = full_response[prefix_length:]
                        post_process_dump_result(response, session_state_history, generator_record=generator_record)
                        return

        resolved_outputs = post_process_dump_result(response, session_state_history, generator_record=generator_record)
        with container:
            render_message("assistant", resolved_outputs)

    def run_flow(data: dict) -> dict:
        global invoker
        if not invoker:
            if flow_path:
                flow = Path(flow_path)
            else:
                flow = Path(__file__).parent / "flow"
            if flow.is_dir():
                os.chdir(flow)
            else:
                os.chdir(flow.parent)
            invoker = load_flow(flow)
            invoker.context.streaming = is_streaming
        result = invoker.invoke(data)
        return result

    image = Image.open(Path(__file__).parent / "logo.png")
    st.set_page_config(
        layout="wide",
        page_title=f"{flow_name} - Promptflow App",
        page_icon=image,
        menu_items={
            "About": """
            # This is a Promptflow App.

            You can refer to [promptflow](https://github.com/microsoft/promptflow) for more information.
            """
        },
    )
    # Set primary button color here since button color of the same form need to be identical in streamlit, but we only
    # need Run/Chat button to be blue.
    st.config.set_option("theme.primaryColor", "#0F6CBD")
    st.title(flow_name)
    st.divider()
    st.chat_message("assistant").write("Hello, please input following flow inputs.")
    container = st.container()
    with container:
        show_conversation()

    with st.form(key="input_form", clear_on_submit=True):
        settings_path = os.path.join(os.path.dirname(__file__), "settings.json")
        if os.path.exists(settings_path):
            with open(settings_path, "r", encoding="utf-8") as file:
                json_data = json.load(file)
            environment_variables = list(json_data.keys())
            for environment_variable in environment_variables:
                secret_input = st.sidebar.text_input(
                    label=environment_variable,
                    type="password",
                    placeholder=f"Please input {environment_variable} here. "
                    f"If you input before, you can leave it blank.",
                )
                if secret_input != "":
                    os.environ[environment_variable] = secret_input

        flow_inputs_params = {}
        for flow_input, (default_value, value_type) in flow_inputs.items():
            if value_type == "list":
                st.text(flow_input)
                input = st_quill(
                    html=True,
                    toolbar=["image"],
                    key=flow_input,
                    placeholder="Please enter the list values and use the image icon to upload a picture. "
                    "Make sure to format each list item correctly with line breaks",
                )
            elif value_type == "image":
                input = st.file_uploader(label=flow_input)
            elif value_type == "string":
                input = st.text_input(label=flow_input, placeholder=default_value)
            else:
                input = st.text_input(label=flow_input, placeholder=default_value)
            flow_inputs_params.update({flow_input: copy(input)})

        cols = st.columns(7)
        submit_bt = cols[0].form_submit_button(label=label, type="primary")
        clear_bt = cols[1].form_submit_button(label="Clear")

        if submit_bt:
            with st.spinner("Loading..."):
                for flow_input, (default_value, value_type) in flow_inputs.items():
                    if value_type == "list":
                        input = parse_list_from_html(flow_inputs_params[flow_input])
                        flow_inputs_params.update({flow_input: copy(input)})
                    elif value_type == "image":
                        input = parse_image_content(
                            flow_inputs_params[flow_input],
                            flow_inputs_params[flow_input].type if flow_inputs_params[flow_input] else None,
                        )
                        flow_inputs_params.update({flow_input: copy(input)})
                submit(**flow_inputs_params)

        if clear_bt:
            with st.spinner("Cleaning..."):
                clear_chat()
                st.rerun()


if __name__ == "__main__":
    with open(Path(__file__).parent / "config.json", "r") as f:
        config = json.load(f)
        is_chat_flow = config["is_chat_flow"]
        chat_history_input_name = config["chat_history_input_name"]
        flow_path = config["flow_path"]
        flow_name = config["flow_name"]
        flow_inputs = config["flow_inputs"]
        label = config["label"]
        is_streaming = config["is_streaming"]
        chat_output_name = config["chat_output_name"]

    start()
