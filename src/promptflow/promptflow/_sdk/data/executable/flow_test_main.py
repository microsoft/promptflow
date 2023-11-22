# This template is added only for chat flow with single input and output.
import json
import os
from copy import copy
from pathlib import Path
from PIL import Image
import streamlit as st
from streamlit_quill import st_quill

from promptflow import load_flow

from utils import render_single_dict_message, parse_list_from_html

invoker = None


def start():
    def clear_chat() -> None:
        st.session_state.messages = []

    def render_message(role, message_items):
        with st.chat_message(role):
            render_single_dict_message(message_items)

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

    def submit(**kwargs) -> None:
        st.session_state.messages.append(("user", kwargs))
        session_state_history = dict()
        session_state_history.update({"inputs": kwargs})
        with container:
            render_message("user", kwargs)
        # Append chat history to kwargs
        response = run_flow({chat_history_input_name: get_chat_history_from_session(), **kwargs})
        # Get base64 for multi modal object
        resolved_outputs = invoker._convert_multimedia_data_to_base64(response)
        st.session_state.messages.append(("assistant", resolved_outputs))
        session_state_history.update({"outputs": response.output})
        st.session_state.history.append(session_state_history)
        invoker._dump_invoke_result(response, dump_path=Path(flow_path).parent, dump_file_prefix="chat")
        with container:
            render_message("assistant", resolved_outputs)

    def run_flow(data: dict) -> dict:
        global invoker
        if not invoker:
            flow = Path(flow_path)
            if flow.is_dir():
                os.chdir(flow)
            else:
                os.chdir(flow.parent)
            invoker = load_flow(flow)
        result = invoker.invoke(data)
        return result

    image = Image.open(Path(__file__).parent / "logo.png")
    st.set_page_config(
        layout="wide",
        page_title=f"{flow_name} - Promptflow App",
        page_icon=image,
        menu_items={
            'About': """
            # This is a Promptflow App.

            You can refer to [promptflow](https://github.com/microsoft/promptflow) for more information.
            """
        }
    )
    # Set primary button color here since button color of the same form need to be identical in streamlit, but we
    # only need Run/Chat button to be blue.
    st.config.set_option("theme.primaryColor", "#0F6CBD")
    st.title(flow_name)
    st.divider()
    st.chat_message("assistant").write("Hello, please input following flow inputs.")
    container = st.container()
    with container:
        show_conversation()

    with st.form(key='input_form', clear_on_submit=True):
        flow_inputs_params = {}
        if chat_input_value_type == "list":
            st.text(chat_input_name)
            input = st_quill(html=True, toolbar=["image"], key=chat_input_name,
                             placeholder='Please enter the list values and use the image icon to upload a picture. '
                                         'Make sure to format each list item correctly with line breaks')
            flow_inputs_params.update({chat_input_name: copy(input)})
        elif chat_input_value_type == "string":
            input = st.text_input(label=chat_input_name, placeholder=chat_input_default_value)
            flow_inputs_params.update({chat_input_name: copy(input)})

        cols = st.columns(7)
        submit_bt = cols[0].form_submit_button(label='Chat', type='primary')
        clear_bt = cols[1].form_submit_button(label='Clear')

        if submit_bt:
            with st.spinner("Loading..."):
                if chat_input_value_type == "list":
                    input = parse_list_from_html(flow_inputs_params[chat_input_name])
                    flow_inputs_params.update({chat_input_name: copy(input)})
                submit(**flow_inputs_params)

        if clear_bt:
            with st.spinner("Cleaning..."):
                clear_chat()
                st.rerun()


if __name__ == "__main__":
    with open(Path(__file__).parent / "config.json", 'r') as f:
        config = json.load(f)
        chat_history_input_name = config["chat_history_input_name"]
        flow_path = config["flow_path"]
        connection_provider = config["connection_provider"]
        flow_name = config["flow_name"]
        chat_input_value_type = config["chat_input_value_type"]
        chat_input_name = config["chat_input_name"]
        chat_input_default_value = config["chat_input_default_value"]
    start()
