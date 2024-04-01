import base64
import json
import re

import streamlit as st
from bs4 import BeautifulSoup, NavigableString, Tag

from promptflow._utils.multimedia_utils import MIME_PATTERN, BasicMultimediaProcessor


def show_image(image, key=None):
    col1, _ = st.columns(2)
    with col1:
        if not image.startswith("data:image"):
            st.image(key + "," + image, use_column_width="auto")
        else:
            st.image(image, use_column_width="auto")


def json_dumps(value):
    try:
        return json.dumps(value, ensure_ascii=False)
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
            isinstance(rich_text_value, str) and rich_text_value.startswith("data:image")
        ):
            result = True
    return result


def item_render_message(value, key=None):
    if key and re.match(MIME_PATTERN, key):
        show_image(value, key)
    elif isinstance(value, str) and value.startswith("data:image"):
        show_image(value)
    else:
        if key is None:
            st.markdown(f"{json_dumps(value)},")
        else:
            st.markdown(f"{key}: {json_dumps(value)},")


def list_iter_render_message(message_items):
    if is_list_contains_rich_text(message_items):
        st.markdown("[ ")
        for item in message_items:
            if isinstance(item, list):
                list_iter_render_message(item)
            if isinstance(item, dict):
                dict_iter_render_message(item)
            else:
                item_render_message(item)
        st.markdown("], ")
    else:
        st.markdown(f"{json_dumps(message_items)},")


def dict_iter_render_message(message_items):
    if BasicMultimediaProcessor.is_multimedia_dict(message_items):
        key = list(message_items.keys())[0]
        value = message_items[key]
        show_image(value, key)
    elif is_dict_contains_rich_text(message_items):
        st.markdown("{ ")
        for key, value in message_items.items():
            if re.match(MIME_PATTERN, key):
                show_image(value, key)
            else:
                if isinstance(value, list):
                    st.markdown(f"{key}: ")
                    list_iter_render_message(value)
                elif isinstance(value, dict):
                    st.markdown(f"{key}: ")
                    dict_iter_render_message(value)
                else:
                    item_render_message(value, key)
        st.markdown("}, ")
    else:
        st.markdown(f"{json_dumps(message_items)},")


def render_single_list_message(message_items):
    # This function is added for chat flow with only single input and single output.
    # So that we can show the message directly without the list and dict wrapper.
    for item in message_items:
        if isinstance(item, list):
            render_single_list_message(item)
        elif isinstance(item, dict):
            render_single_dict_message(item)
        elif isinstance(item, str):
            st.text(item)


def render_single_dict_message(message_items):
    # This function is added for chat flow with only single input and single output.
    # So that we can show the message directly without the list and dict wrapper.
    for key, value in message_items.items():
        if re.match(MIME_PATTERN, key):
            show_image(value, key)
            continue
        else:
            if isinstance(value, list):
                render_single_list_message(value)
            elif isinstance(value, dict):
                render_single_dict_message(value)
            else:
                item_render_message(value, key)


def extract_content(node):
    if isinstance(node, NavigableString):
        text = node.strip()
        if text:
            return [text]
    elif isinstance(node, Tag):
        if node.name == "img":
            prefix, base64_str = node["src"].split(",", 1)
            return [{prefix: base64_str}]
        else:
            result = []
            for child in node.contents:
                result.extend(extract_content(child))
            return result
    return []


def parse_list_from_html(html_content):
    """
    Parse the html content to a list of strings and images.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    result = []
    for p in soup.find_all("p"):
        result.extend(extract_content(p))
    return result


def parse_image_content(image_content, image_type):
    if image_content is not None:
        file_contents = image_content.read()
        image_content = base64.b64encode(file_contents).decode("utf-8")
        prefix = f"data:{image_type};base64"
        return {prefix: image_content}
