import bs4
import requests
from requests.exceptions import HTTPError

from promptflow import tool


def fetch_url(url):
    # Send a request to the URL
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/113.0.0.0 Safari/537.36 Edg/113.0.1774.35"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status(response)
        return response.text
    except HTTPError as e:
        print(
            f"Get url failed with status code {e.status_code}.\nURL: {url}\nResponse: "
            f"{e.response.text[:100]}"
        )
        raise
    except Exception as e:
        print("Get url failed with error: {}".format(e))
        raise


@tool
def fetch_text_content_from_url(url: str):
    # Send a request to the URL
    try:
        text = fetch_url(url)
        # Parse the HTML content using BeautifulSoup
        soup = bs4.BeautifulSoup(text, "html.parser")
        soup.prettify()
        return soup.get_text()[:2000]
    except Exception as e:
        print("Get url failed with error: {}".format(e))
        return "No available content"
