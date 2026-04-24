from bs4 import BeautifulSoup
import re
import requests


def decode_str(string):
    return string.encode().decode("unicode-escape").encode("latin1").decode("utf-8")


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


def remove_nested_parentheses(string):
    pattern = r'\([^()]+\)'
    while re.search(pattern, string):
        string = re.sub(pattern, '', string)
    return string


def search(entity: str, count: int = 10):
    """
    The input is an exact entity name. The action will search this entity name on Wikipedia and returns the first
    count sentences if it exists. If not, it will return some related entities to search next.
    """

    entity_ = entity.replace(" ", "+")
    search_url = f"https://en.wikipedia.org/w/index.php?search={entity_}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/113.0.0.0 Safari/537.36 Edg/113.0.1774.35"
    }
    response_text = requests.get(search_url, headers=headers).text
    soup = BeautifulSoup(response_text, features="html.parser")
    result_divs = soup.find_all("div", {"class": "mw-search-result-heading"})
    if result_divs:  # mismatch
        result_titles = [decode_str(div.get_text().strip()) for div in result_divs]
        result_titles = [remove_nested_parentheses(result_title) for result_title in result_titles]
        obs = f"Could not find {entity}. Similar: {result_titles[:5]}."
    else:
        page_content = [p_ul.get_text().strip() for p_ul in soup.find_all("p") + soup.find_all("ul")]
        if any("may refer to:" in p for p in page_content):
            obs = search("[" + entity + "]")
        else:
            page = ""
            for content in page_content:
                if len(content.split(" ")) > 2:
                    page += decode_str(content)
                if not content.endswith("\n"):
                    page += "\n"
            obs = get_page_sentence(page, count=count)
    return obs
