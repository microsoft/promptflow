import bs4
import requests

from promptflow.core import tool


@tool
def fetch_text_content_from_url(url: str):
    # Send a request to the URL
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/113.0.0.0 Safari/537.36 Edg/113.0.1774.35"
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            # Parse the HTML content using BeautifulSoup
            soup = bs4.BeautifulSoup(response.text, "html.parser")
            soup.prettify()
            return soup.get_text()[:2000]
        else:
            msg = (
                f"Get url failed with status code {response.status_code}.\nURL: {url}\nResponse: "
                f"{response.text[:100]}"
            )
            print(msg)
            return "No available content"
    except Exception as e:
        print("Get url failed with error: {}".format(e))
        return "No available content"
