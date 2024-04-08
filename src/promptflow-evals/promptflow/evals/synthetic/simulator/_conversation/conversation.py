# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
import logging
from typing import Any, Callable, List, Tuple

from .conversation_bot import ConversationBot, RetryClient
from .conversation_turn import ConversationTurn


def is_closing_message(response: Any, recursion_depth: int = 0):
    if recursion_depth > 10:
        raise Exception("Exceeded max call depth in is_closing_message")

    # recursively go through each inner dictionary in the JSON dict
    # and check if any value entry contains a closing message
    if isinstance(response, dict):
        for value in response.values():
            if is_closing_message(value, recursion_depth=recursion_depth + 1):
                return True
    elif isinstance(response, str):
        return is_closing_message_helper(response)

    return False


def is_closing_message_helper(response: str):
    message = response.lower()
    if "?" in message.lower():
        return False
    punc = [".", ",", "!", ";", ":"]
    for p in punc:
        message = message.replace(p, "")
    if (
        "bye" not in message.lower().split()
        and "goodbye" not in message.lower().split()
        # and "thanks" not in message.lower()
        # and "thank" not in message.lower()
    ):
        return False
    return True


async def simulate_conversation(
    bots: List[ConversationBot],
    session: RetryClient,
    stopping_criteria: Callable[[str], bool] = is_closing_message,
    turn_limit: int = 10,
    history_limit: int = 5,
    api_call_delay_sec: float = 0,
    logger: logging.Logger = logging.getLogger(__name__),
    mlflow_logger=None,
) -> Tuple:
    """
    Simulate a conversation between the given bots.

    :param bots: List of ConversationBot instances participating in the conversation.
    :type bots: List[ConversationBot]
    :param session: The session to use for making API calls.
    :type session: RetryClient
    :param stopping_criteria: A callable that determines when the conversation should stop.
    :type stopping_criteria: Callable[[str], bool]
    :param turn_limit: The maximum number of turns in the conversation. Defaults to 10.
    :type turn_limit: int
    :param history_limit: The maximum number of turns to keep in the conversation history. Defaults to 5.
    :type history_limit: int
    :param api_call_delay_sec: Delay between API calls in seconds. Defaults to 0.
    :type api_call_delay_sec: float
    :param logger: The logger to use for logging. Defaults to the logger named after the current module.
    :type logger: logging.Logger
    :param mlflow_logger: MLflow logger instance. Defaults to None.
    :type mlflow_logger: Any
    :return: Simulation a conversation between the given bots.
    :rtype: Tuple
    """
    logger_tasks = []

    # Read the first prompt.
    (first_response, request, _, full_response) = await bots[0].generate_response(
        session=session,
        conversation_history=[],
        max_history=history_limit,
        turn_number=0,
    )
    if "id" in first_response:
        conversation_id = first_response["id"]
    else:
        conversation_id = None
    first_prompt = first_response["samples"][0]
    # Add all generated turns into array to pass for each bot while generating
    # new responses. We add generated response and the person generating it.
    # in the case of the first turn, it is supposed to be the user search query
    conversation_history = [
        ConversationTurn(
            role=bots[0].role,
            name=bots[0].name,
            message=first_prompt,
            full_response=full_response,
            request=request,
        )
    ]

    # initialize the turn counter
    current_turn = 1

    # Keep iterating and alternate between bots until a stopping word is
    # generated or maximum number of turns is reached.
    while (not stopping_criteria(conversation_history[-1].message)) and (current_turn < turn_limit):
        try:
            current_character_idx = current_turn % len(bots)
            current_bot = bots[current_character_idx]
            # invoke Bot to generate response given the input request
            # pass only the last generated turn without passing the bot name.
            response, request, time_taken, full_response = await current_bot.generate_response(
                session=session,
                conversation_history=conversation_history,
                max_history=history_limit,
                turn_number=current_turn,
            )

            # check if conversation id is null, which means conversation starter was used. use id from next turn
            if conversation_id is None and "id" in response:
                conversation_id = response["id"]
            # add the generated response to the list of generated responses
            conversation_history.append(
                ConversationTurn(
                    role=current_bot.role,
                    name=current_bot.name,
                    message=response["samples"][0],
                    full_response=full_response,
                    request=request,
                )
            )
            if mlflow_logger is not None:
                logger_tasks.append(  # schedule logging but don't get blocked by it
                    asyncio.create_task(mlflow_logger.log_successful_response(time_taken))
                )
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("Error: %s", str(e))
            if mlflow_logger is not None:
                logger_tasks.append(  # schedule logging but don't get blocked by it
                    asyncio.create_task(mlflow_logger.log_error())
                )

        # Increment outside the try block so we don't get stuck if
        # an exception is thrown
        current_turn += 1

        # Sleep between consecutive requests to avoid rate limit
        await asyncio.sleep(api_call_delay_sec)

    if mlflow_logger is not None:
        return conversation_id, conversation_history, logger_tasks
    return conversation_id, conversation_history


def play_conversation(conversation_history: List[ConversationTurn]):
    """
    Play the given conversation.

    :param conversation_history: A list of ConversationTurn objects representing the conversation history.
    :type conversation_history: List[ConversationTurn]
    """
    for turn in conversation_history:
        if turn.name:
            print(f"{turn.name}: {turn.message}")
        else:
            print(f"{turn.role.value}: {turn.message}")


def debug_conversation(conversation_history: List[ConversationTurn]):
    """
    Debug the requests, responses, and extracted messages from a conversation history.

    :param conversation_history: A list of ConversationTurn objects representing the conversation history.
    :type conversation_history: List[ConversationTurn]
    """
    for i, turn in enumerate(conversation_history):
        print("=" * 80)
        print(f"Request #{i}:")
        if turn.request and "prompt" in turn.request:
            print(turn.request["prompt"])
        elif turn.request and "messages" in turn.request:
            print(turn.request["messages"])
        elif turn.request and "transcript" in turn.request:
            transcript = turn.request["transcript"]
            for item in transcript:
                if item["type"] == "image":
                    item = item.copy()
                    item["data"] = "... (image data)"
                print(item)
        else:
            print(turn.request)
        print("=" * 80)
        print(f"Response #{i}:")
        if turn.full_response and "choices" in turn.full_response:
            response = turn.full_response["choices"][0]
            if "text" in response:
                print(response["text"])
            else:
                print(response["message"])
        elif turn.full_response and "samples" in turn.full_response:
            print(turn.full_response["samples"][0])
        else:
            print(turn.full_response)
        print("=" * 80)
        print(f"Extracted Message #{i}: ")
        print(turn.message)
        print("=" * 80)
