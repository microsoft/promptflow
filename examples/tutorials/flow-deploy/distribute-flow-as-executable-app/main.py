import base64
import json
import os
import re
import streamlit as st
from pathlib import Path
from streamlit_quill import st_quill
from bs4 import BeautifulSoup, NavigableString, Tag

from promptflow._sdk._utils import print_yellow_warning
from promptflow._sdk._serving.flow_invoker import FlowInvoker
from promptflow._utils.multimedia_utils import is_multimedia_dict, MIME_PATTERN

invoker = None


def start():
    def clear_chat() -> None:
        st.session_state.messages = []

    def show_image(image, key=None):
        if not image.startswith("data:image"):
            st.image(key + ',' + image)
        else:
            st.image(image)

    def json_dumps(value):
        try:
            return json.dumps(value)
        except Exception:
            return value


    def is_list_contains_rich_text(rich_text):
        result = False
        for item in rich_text:
            if isinstance(item, list):
                result |= is_list_contains_rich_text(item)
            elif isinstance(item, dict):
                result |= is_dict_contains_rich_text(item)
            else:
                if isinstance(item, str) and item.startswith("data:image"):
                    result = True
        return result

    def is_dict_contains_rich_text(rich_text):
        result = False
        for rich_text_key, rich_text_value in rich_text.items():
            if isinstance(rich_text_value, list):
                result |= is_list_contains_rich_text(rich_text_value)
            elif isinstance(rich_text_value, dict):
                result |= is_dict_contains_rich_text(rich_text_value)
            elif re.match(MIME_PATTERN, rich_text_key) or (
                    isinstance(rich_text_value, str) and rich_text_value.startswith("data:image")):
                result = True
        return result

    def render_message(role, message_items):

        def item_render_message(value, key=None):
            if key and re.match(MIME_PATTERN, key):
                show_image(value, key)
            elif isinstance(value, str) and value.startswith("data:image"):
                show_image(value)
            else:
                if key is None:
                    st.markdown(f"`{json_dumps(value)},`")
                else:
                    st.markdown(f"`{key}: {json_dumps(value)},`")

        def list_iter_render_message(message_items):
            if is_list_contains_rich_text(message_items):
                st.markdown("`[ `")
                for item in message_items:
                    if isinstance(item, list):
                        list_iter_render_message(item)
                    if isinstance(item, dict):
                        dict_iter_render_message(item)
                    else:
                        item_render_message(item)
                st.markdown("`], `")
            else:
                st.markdown(f"`{json_dumps(message_items)},`")

        def dict_iter_render_message(message_items):
            if is_multimedia_dict(message_items):
                key = list(message_items.keys())[0]
                value = message_items[key]
                show_image(value, key)
            elif is_dict_contains_rich_text(message_items):
                st.markdown("`{ `")
                for key, value in message_items.items():
                    if re.match(MIME_PATTERN, key):
                        show_image(value, key)
                    else:
                        if isinstance(value, list):
                            st.markdown(f"`{key}: `")
                            list_iter_render_message(value)
                        elif isinstance(value, dict):
                            st.markdown(f"`{key}: `")
                            dict_iter_render_message(value)
                        else:
                            item_render_message(value, key)
                st.markdown("`}, `")
            else:
                st.markdown(f"`{json_dumps(message_items)},`")

        with st.chat_message(role):
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

    def submit(**kwargs) -> None:
        st.session_state.messages.append(("user", kwargs))
        session_state_history = dict()
        session_state_history.update({"inputs": kwargs})
        with container:
            render_message("user", kwargs)
        # Force append chat history to kwargs
        response = run_flow(kwargs)
        st.session_state.messages.append(("assistant", response))
        session_state_history.update({"outputs": response})
        st.session_state.history.append(session_state_history)
        with container:
            render_message("assistant", response)

    def run_flow(data: dict) -> dict:
        global invoker
        if not invoker:
            flow = Path(__file__).parent / "flow"
            dump_path = flow.parent
            if flow.is_dir():
                os.chdir(flow)
            else:
                os.chdir(flow.parent)
            invoker = FlowInvoker(flow, connection_provider="local", dump_to=dump_path)
        result, result_output = invoker.invoke(data)
        print_yellow_warning(f"Result: {result_output}")
        return result

    def extract_content(node):
        if isinstance(node, NavigableString):
            text = node.strip()
            if text:
                return [text]
        elif isinstance(node, Tag):
            if node.name == 'img':
                prefix, base64_str = node['src'].split(',', 1)
                return [{prefix: base64_str}]
            else:
                result = []
                for child in node.contents:
                    result.extend(extract_content(child))
                return result
        return []


    def parse_html_content(html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        result = []
        for p in soup.find_all('p'):
            result.extend(extract_content(p))
        return result

    def parse_image_content(image_content, image_type):
        if image_content is not None:
            file_contents = image_content.read()
            image_content = base64.b64encode(file_contents).decode('utf-8')
            prefix = f"data:{image_type};base64"
            return {prefix: image_content}

    st.title("web-classification APP")
    st.chat_message("assistant").write("Hello, please input following flow inputs.")
    container = st.container()
    with container:
        show_conversation()

    with st.form(key='input_form', clear_on_submit=True):
        settings_path = os.path.join(os.path.dirname(__file__), "settings.json")
        if os.path.exists(settings_path):
            with open(settings_path, "r") as file:
                json_data = json.load(file)
            environment_variables = list(json_data.keys())
            for environment_variable in environment_variables:
                secret_input = st.text_input(
                    label=environment_variable,
                    type="password",
                    placeholder=f"Please input {environment_variable} here. If you input before, you can leave it "
                                f"blank.")
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
