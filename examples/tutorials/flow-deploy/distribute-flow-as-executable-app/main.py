import json
import os
import streamlit as st
from pathlib import Path

from promptflow._sdk._utils import print_yellow_warning
from promptflow._sdk._serving.flow_invoker import FlowInvoker

invoker = None


def start():
    def clear_chat() -> None:
        st.session_state.messages = []

    def show_conversation() -> None:
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if st.session_state.messages:
            for role, message in st.session_state.messages:
                st.chat_message(role).write(message)

    def submit(**kwargs) -> None:
        container.chat_message("user").write(json.dumps(kwargs))
        st.session_state.messages.append(("user", json.dumps(kwargs)))
        response = run_flow(kwargs)
        container.chat_message("assistant").write(response)
        st.session_state.messages.append(("assistant", response))

    def run_flow(data: dict) -> dict:
        global invoker
        if not invoker:
            flow = Path(__file__).parent / "flow"
            os.chdir(flow)
            invoker = FlowInvoker(flow, connection_provider="local")
        result = invoker.invoke(data)
        print_yellow_warning(f"Result: {result}")
        return result

    st.title("web-classification APP")
    st.chat_message("assistant").write("Hello, please input following flow inputs and connection keys.")
    container = st.container()
    with container:
        show_conversation()

    with st.form(key='input_form', clear_on_submit=True):
        with open(os.path.join(os.path.dirname(__file__), "settings.json"), "r") as file:
            json_data = json.load(file)
        environment_variables = list(json_data.keys())
        for environment_variable in environment_variables:
            secret_input = st.text_input(label=environment_variable, type="password",
                                         placeholder=f"Please input {environment_variable} here. If you input before, "
                                                     f"you can leave it blank.")
            if secret_input != "":
                os.environ[environment_variable] = secret_input

        url = st.text_input(label='url',
                            placeholder='https://play.google.com/store/apps/details?id=com.twitter.android')
        cols = st.columns(7)
        submit_bt = cols[0].form_submit_button(label='Submit')
        clear_bt = cols[1].form_submit_button(label='Clear')

    if submit_bt:
        submit(url=url)

    if clear_bt:
        clear_chat()


if __name__ == "__main__":
    start()
