import os
import pathlib
import random
import time
from functools import partial

import jinja2
import requests
import bs4
import re
from concurrent.futures import ThreadPoolExecutor
from openai import AzureOpenAI


session = requests.Session()

templateLoader = jinja2.FileSystemLoader(pathlib.Path(__file__).parent.resolve())
templateEnv = jinja2.Environment(loader=templateLoader)
system_message_template = templateEnv.get_template("system-message.jinja2")


def decode_str(string):
    return string.encode().decode("unicode-escape").encode("latin1").decode("utf-8")


def remove_nested_parentheses(string):
    pattern = r'\([^()]+\)'
    while re.search(pattern, string):
        string = re.sub(pattern, '', string)
    return string


def get_page_sentence(page, count: int = 10):
    # find all paragraphs
    paragraphs = page.split("\n")
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    # find all sentence
    sentences = []
    for p in paragraphs:
        sentences += p.split('. ')
    sentences = [s.strip() + '.' for s in sentences if s.strip()]
    # get first `count` number of sentences
    return ' '.join(sentences[:count])


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
            soup = bs4.BeautifulSoup(response.text, 'html.parser')
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
            msg = f"Get url failed with status code {response.status_code}.\nURL: {url}\nResponse: " \
                  f"{response.text[:100]}"
            print(msg)
            return (url, "No available content")

    except Exception as e:
        print("Get url failed with error: {}".format(e))
        return (url, "No available content")


def search_result_from_url(url_list: list, count: int = 10):
    results = []
    partial_func_of_fetch_text_content_from_url = partial(fetch_text_content_from_url, count=count)
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = executor.map(partial_func_of_fetch_text_content_from_url, url_list)
        for feature in futures:
            results.append(feature)
    return results


def get_wiki_url(entity: str, count=2):
    # Send a request to the URL
    url = f"https://en.wikipedia.org/w/index.php?search={entity}"
    url_list = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/113.0.0.0 Safari/537.36 Edg/113.0.1774.35"}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            # Parse the HTML content using BeautifulSoup
            soup = bs4.BeautifulSoup(response.text, 'html.parser')
            mw_divs = soup.find_all("div", {"class": "mw-search-result-heading"})
            if mw_divs:  # mismatch
                result_titles = [decode_str(div.get_text().strip()) for div in mw_divs]
                result_titles = [remove_nested_parentheses(result_title) for result_title in result_titles]
                # print(f"Could not find {entity}. Similar entity: {result_titles[:count]}.")
                url_list.extend([f"https://en.wikipedia.org/w/index.php?search={result_title}" for result_title in
                                 result_titles])
            else:
                page_content = [p_ul.get_text().strip() for p_ul in soup.find_all("p") + soup.find_all("ul")]
                if any("may refer to:" in p for p in page_content):
                    url_list.extend(get_wiki_url("[" + entity + "]"))
                else:
                    url_list.append(url)
        else:
            msg = f"Get url failed with status code {response.status_code}.\nURL: {url}\nResponse: " \
                  f"{response.text[:100]}"
            print(msg)
        return url_list[:count]
    except Exception as e:
        print("Get url failed with error: {}".format(e))
        return url_list


def process_search_result(search_result):
    def format(doc: dict):
        return f"Content: {doc['Content']}"

    try:
        context = []
        for url, content in search_result:
            context.append({
                "Content": content,
                # "Source": url
            })
        context_str = "\n\n".join([format(c) for c in context])
        return context_str
    except Exception as e:
        print(f"Error: {e}")
        return ""


def augmented_qa(question, context):
    system_message = system_message_template.render(contexts=context)

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": question}
    ]

    with AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"]
    ) as client:
        response = client.chat.completions.create(
            model=os.environ.get("AZURE_OPENAI_DEPLOYMENT"),
            messages=messages, temperature=0.7,
            max_tokens=800
        )

        return response.choices[0].message.content


def ask_wiki(question):
    url_list = get_wiki_url(question, count=2)
    search_result = search_result_from_url(url_list, count=10)
    context = process_search_result(search_result)
    answer = augmented_qa(question, context)

    return {
        "answer": answer,
        "context": str(context)
    }


if __name__ == "__main__":
    print(ask_wiki("Who is the president of the United States?"))
