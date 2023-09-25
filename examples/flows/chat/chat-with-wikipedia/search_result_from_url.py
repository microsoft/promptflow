import random
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial

import bs4
import requests

from promptflow import tool

session = requests.Session()


def decode_str(string):
    return string.encode().decode("unicode-escape").encode("latin1").decode("utf-8")


def get_page_sentence(page, count: int = 10):
    # find all paragraphs
    paragraphs = page.split("\n")
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    # find all sentence
    sentences = []
    for p in paragraphs:
        sentences += p.split(". ")
    sentences = [s.strip() + "." for s in sentences if s.strip()]
    # get first `count` number of sentences
    return " ".join(sentences[:count])


def fetch_text_content_from_url(url: str, count: int = 10):
    # Send a request to the URL
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/113.0.0.0 Safari/537.36 Edg/113.0.1774.35"
        }
        delay = random.uniform(0, 0.5)
        time.sleep(delay)
        response = session.get(url, headers=headers)
        if response.status_code == 200:
            # Parse the HTML content using BeautifulSoup
            soup = bs4.BeautifulSoup(response.text, "html.parser")
            page_content = [p_ul.get_text().strip() for p_ul in soup.find_all("p") + soup.find_all("ul")]
            page = ""
            for content in page_content:
                if len(content.split(" ")) > 2:
                    page += decode_str(content)
                if not content.endswith("\n"):
                    page += "\n"
            text = get_page_sentence(page, count=count)
            return (url, text)
        else:
            msg = (
                f"Get url failed with status code {response.status_code}.\nURL: {url}\nResponse: "
                f"{response.text[:100]}"
            )
            print(msg)
            return (url, "No available content")

    except Exception as e:
        print("Get url failed with error: {}".format(e))
        return (url, "No available content")


@tool
def search_result_from_url(url_list: list, count: int = 10):
    results = []
    partial_func_of_fetch_text_content_from_url = partial(fetch_text_content_from_url, count=count)
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = executor.map(partial_func_of_fetch_text_content_from_url, url_list)
        for feature in futures:
            results.append(feature)
    return results
