from promptflow import ToolProvider, tool
from promptflow.core.tools_manager import register_builtins
from promptflow.connections import BingConnection


class MyBing(ToolProvider):
    def __init__(self, my_connection: BingConnection):
        self.connection = my_connection
        super().__init__()

    @staticmethod
    def from_config(config: BingConnection):
        return MyBing(config)

    @tool
    def search(self, query: str, count: int = 10):
        import json

        import requests

        search_url = "https://api.bing.microsoft.com/v7.0/search"
        headers = {"Ocp-Apim-Subscription-Key": str(self.connection.api_key)}
        params = {"q": query, "count": count, "textDecorations": True, "textFormat": "HTML"}
        # get response
        response = requests.get(search_url, headers=headers, params=params)
        response.raise_for_status()
        # return json.dumps(response.json())
        # TODO: remove below workaround when resolving "PropertyValueTooLarge" error.
        result = {"webPages": {"value": []}}
        try:
            for values in response.json()["webPages"]["value"]:
                result["webPages"]["value"].append(
                    {"name": values["name"], "snippet": values["snippet"], "url": values["url"]}
                )
        except Exception:
            result["webPages"]["value"].append({"name": "No results found", "snippet": "No results found", "url": ""})
        return json.dumps(result)


register_builtins(MyBing)
