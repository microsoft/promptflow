from promptflow.tools.aoai import chat as aoai_chat
from promptflow.tools.openai import chat as openai_chat
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection
from util import count_message_tokens, count_string_tokens, create_chat_message, generate_context, get_logger, \
    parse_reply, construct_prompt

autogpt_logger = get_logger("autogpt_agent")


class AutoGPT:
    def __init__(
        self,
        connection,
        tools,
        full_message_history,
        functions,
        system_prompt=None,
        triggering_prompt=None,
        user_prompt=None,
        model_or_deployment_name=None
    ):
        self.tools = tools
        self.full_message_history = full_message_history
        self.functions = functions
        self.system_prompt = system_prompt
        self.connection = connection
        self.model_or_deployment_name = model_or_deployment_name
        self.triggering_prompt = triggering_prompt
        self.user_prompt = user_prompt

    def chat_with_ai(self, token_limit):
        """Interact with the OpenAI API, sending the prompt, message history and functions."""

        # Reserve 1000 tokens for the response
        send_token_limit = token_limit - 1000
        (
            next_message_to_add_index,
            current_tokens_used,
            insertion_index,
            current_context,
        ) = generate_context(self.system_prompt, self.full_message_history, self.user_prompt)
        # Account for user input (appended later)
        current_tokens_used += count_message_tokens([create_chat_message("user", self.triggering_prompt)])
        current_tokens_used += 500  # Account for memory (appended later)
        # Add Messages until the token limit is reached or there are no more messages to add.
        while next_message_to_add_index >= 0:
            message_to_add = self.full_message_history[next_message_to_add_index]

            tokens_to_add = count_message_tokens([message_to_add])
            if current_tokens_used + tokens_to_add > send_token_limit:
                break

            # Add the most recent message to the start of the current context, after the two system prompts.
            current_context.insert(
                insertion_index, self.full_message_history[next_message_to_add_index]
            )

            # Count the currently used tokens
            current_tokens_used += tokens_to_add
            # Move to the next most recent message in the full message history
            next_message_to_add_index -= 1

        # Append user input, the length of this is accounted for above
        current_context.extend([create_chat_message("user", self.triggering_prompt)])
        # Calculate remaining tokens
        tokens_remaining = token_limit - current_tokens_used

        current_context = construct_prompt(current_context)
        if isinstance(self.connection, AzureOpenAIConnection):
            try:
                response = aoai_chat(
                    connection=self.connection,
                    prompt=current_context,
                    deployment_name=self.model_or_deployment_name,
                    max_tokens=tokens_remaining,
                    functions=self.functions)
                return response
            except Exception as e:
                if "The API deployment for this resource does not exist" in str(e):
                    raise Exception(
                        "Please fill in the deployment name of your Azure OpenAI resource gpt-4 model.")

        elif isinstance(self.connection, OpenAIConnection):
            response = openai_chat(
                connection=self.connection,
                prompt=current_context,
                model=self.model_or_deployment_name,
                max_tokens=tokens_remaining,
                functions=self.functions)
            return response
        else:
            raise ValueError("Connection must be an instance of AzureOpenAIConnection or OpenAIConnection")

    def run(self):
        tools = {t.__name__: t for t in self.tools}
        while True:
            # Send message to AI, get response
            response = self.chat_with_ai(token_limit=4000)
            if "function_call" in response:
                # Update full message history
                function_name = response["function_call"]["name"]
                parsed_output = parse_reply(response["function_call"]["arguments"])
                if "Error" in parsed_output:
                    error_message = parsed_output["Error"]
                    autogpt_logger.info(f"Error: {error_message}")
                    command_result = f"Error: {error_message}"
                else:
                    autogpt_logger.info(f"Function generation requested, function = {function_name}, args = "
                                        f"{parsed_output}")
                    self.full_message_history.append(
                        create_chat_message("assistant", f"Function generation requested, function = {function_name}, "
                                                         f"args = {parsed_output}")
                    )
                    if function_name == "finish":
                        response = parsed_output["response"]
                        autogpt_logger.info(f"Responding to user: {response}")
                        return response
                    if function_name in tools:
                        tool = tools[function_name]
                        try:
                            autogpt_logger.info(f"Next function = {function_name}, arguments = {parsed_output}")
                            result = tool(**parsed_output)
                            command_result = f"Executed function {function_name} and returned: {result}"
                        except Exception as e:
                            command_result = (
                                f"Error: {str(e)}, {type(e).__name__}"
                            )
                        result_length = count_string_tokens(command_result)

                        if result_length + 600 > 4000:
                            command_result = f"Failure: function {function_name} returned too much output. Do not " \
                                             f"execute this function again with the same arguments."
                    else:
                        command_result = f"Unknown function '{function_name}'. Please refer to available functions " \
                                         f"defined in functions parameter."

                # Append command result to the message history
                self.full_message_history.append(create_chat_message("function", str(command_result), function_name))
                autogpt_logger.info(f"function: {command_result}")
            else:
                autogpt_logger.info(f"No function generated, returned: {response['content']}")
                self.full_message_history.append(
                    create_chat_message("assistant", f"No function generated, returned: {response['content']}")
                )
