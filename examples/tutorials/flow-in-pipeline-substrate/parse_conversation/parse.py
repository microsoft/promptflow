import argparse
import json


ONE_TURN_CONVERSATION_STEWIE_LEO = """   - User: {user}
   - Bing: {bot}"""

def parse_conversation(conversation: object) -> object:
    turns = conversation['Turns']
    conversation = []
    for val in turns:
        sydney_response = "\n\n".join([message.rstrip("\n").lstrip("\n") for message in val["SydneyReply"]])
        user_message = val['Human']

        conversation.append(ONE_TURN_CONVERSATION_STEWIE_LEO.format(user = user_message, bot = sydney_response))

    conversation = "\n".join(conversation)

    metadata = ""
    if "RequestTime" in turns[0]: metadata += f"""	- Time at which conversation started: {str(turns[0]["Time"])}\n"""
    if "Location" in turns[0]: metadata += f"""	- Location of user: {str(turns[0]["Location"])}\n"""

    return_obj = {
        'conversation' : conversation,
        'meta' : metadata
    }
    
    return return_obj

config_Leo_Metrics = {
    "dv3_token_file_path": "./authtoken.txt",
    "sydney_client_secret": None,
    "conversations": {
        "input_file": "data/2023-04-13-e2e-queryset.tsv",
        "thread_size": 1,
        "output_folder": "./GroundLeoTmp",
        "exp_configs": [
            {
                "exp_name": "fake_tenant",
                "runType": "scheduled",
                "user":  "Andy",
                "sydney": {
                    "url": "https://turingbot.sdf-master.substrate-turing-turingbot.eastus-sdf.cosmic-ppe.office.net/TuringBot",
                    "option_sets": "enterprise_chomsky_ppo_with_errors",
                    "substrateSearchTokenPath": "./3stoken.txt",
                    "bingTokenPath": "./bingToken.txt"
                }
            }
        ]
    },
    "ratings": {
        "baseline_name": "demo"
    }
}

def parse_config(key: str) -> object:
    if(key == 'Leo_Metrics'):
        return config_Leo_Metrics
    else:
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-data", required=True, type=str)
    parser.add_argument("--output-data", required=True, type=str)
    parser.add_argument("--config-key", type=str, default="Leo_Metrics")
    args = parser.parse_args()
    
    input_raws = []
    with open(args.input_data, "r", encoding="utf-8") as input_data:
        for raw in input_data:
            input_raws.append(json.loads(raw))
    
    output_raws = []
    for raw in input_raws:
        output_raws.append({
            "conversation_obj": parse_conversation(raw),
            "config": parse_config(args.config_key),
            "conversation_id": raw["ConversationId"],
            "query": raw['Turns'][0]['Human']
        })
    with open(args.output_data, "w", encoding="utf-8") as output_file:
        for raw in output_raws:
            text = json.dumps(raw)
            output_file.write(text + "\n")
