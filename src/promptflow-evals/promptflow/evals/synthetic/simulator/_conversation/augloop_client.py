# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import logging
import os
from typing import Any, Dict, Optional

import websocket
from azure.core.credentials import TokenCredential
from azure.identity import AzureCliCredential, ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient
from jsonpath_ng import parse
from websocket import WebSocketConnectionClosedException


class AugLoopParams:  # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        url: str,
        authTokenKeyVaultUrl: str,
        authTokenKeyVaultSecretName: str,
        annotationType: str,
        workflowName: str,
        signalType: str,
        signalBaseType: str,
        clientAppName: str,
        pathToMessages: str,
        annotationMessageParamName: str,
        pathToError: str = "",
        signalMessageParamName: str = "message",
        signalOtherParams: str = "",
        flights: str = "",
        cvBase: str = "eAieZY/LoqYfURDv1ao1W3",
        sessionId: str = "1ecf6906-090a-45b1-8d79-88defc62d3cc",
        runtimeVersion: str = "2.34.97",
        otherTokenKeyVaultSecretNames: Optional[list] = None,
    ):
        self.url = url
        self.authTokenKeyVaultUrl = authTokenKeyVaultUrl
        self.authTokenKeyVaultSecretName = authTokenKeyVaultSecretName
        self.annotationType = annotationType
        self.workflowName = workflowName
        self.signalType = signalType
        self.signalBaseType = signalBaseType
        self.clientAppName = clientAppName
        self.pathToMessages = pathToMessages
        self.annotationMessageParamName = annotationMessageParamName
        self.pathToError = pathToError
        self.signalMessageParamName = signalMessageParamName
        self.signalOtherParams = signalOtherParams
        self.flights = flights
        self.cvBase = cvBase
        self.sessionId = sessionId
        self.runtimeVersion = runtimeVersion
        self.otherTokenKeyVaultSecretNames = (
            otherTokenKeyVaultSecretNames if otherTokenKeyVaultSecretNames is not None else []
        )

        # if signalOtherParams is set, make sure it ends with a ","
        if self.signalOtherParams != "" and not self.signalOtherParams.endswith(","):
            self.signalOtherParams = self.signalOtherParams + ","


class AugLoopClient:  # pylint: disable=client-accepts-api-version-keyword
    def __init__(
        # pylint: disable=unused-argument
        self,
        augLoopParams: AugLoopParams,
        credential: Optional[TokenCredential] = None,
        **kwargs: Any,
    ) -> None:
        self.augLoopParams = augLoopParams
        self.sequence = 0

        self.logger = logging.getLogger(repr(self))

        self.logger.info("Connecting Websocket")

        url = self.augLoopParams.url
        clientAppName = self.augLoopParams.clientAppName
        sessionId = self.augLoopParams.sessionId
        flights = self.augLoopParams.flights
        runtimeVersion = self.augLoopParams.runtimeVersion
        cvBase = self.augLoopParams.cvBase
        sequence = self.sequence

        self.websocket = websocket.create_connection(url)

        # send session init
        # pylint: disable=line-too-long
        self.send_message_to_al(
            '{{"protocolVersion":2,"clientMetadata":{{"appName":"{0}",'
            '"appPlatform":"Client","sessionId":"{1}","flights":"{2}",'
            '"appVersion":"","uiLanguage":"","roamingServiceAppId":0,'
            '"runtimeVersion":"{3}","docSessionId":"{1}"}},"extensionConfigs":[],'
            '"returnWorkflowInputTypes":false,"enableRemoteExecutionNotification":false,'
            '"H_":{{"T_":"AugLoop_Session_Protocol_SessionInitMessage",'
            '"B_":["AugLoop_Session_Protocol_Message"]}},"cv":"{4}.{5}",'
            '"messageId":"c{5}"}}'.format(clientAppName, sessionId, flights, runtimeVersion, cvBase, sequence)
        )
        message = self.websocket.recv()
        self.logger.info("SessionInit Response: %s", message)

        sessionInitResponse = json.loads(message)
        self.sessionKey = sessionInitResponse["sessionKey"]
        self.origin = sessionInitResponse["origin"]
        self.anonToken = sessionInitResponse["anonymousToken"]

        self.setup_session_after_init()

        self.prevId: str = ""
        self.id: str = ""

    # Deleting (Calling destructor)
    def __del__(self):  # pylint: disable=client-method-name-no-double-underscore
        self.logger.info("Closing Websocket")
        self.websocket.close()

    def send_signal_and_wait_for_annotation(self, message: str, isInRecursiveCall: bool = False) -> Dict:
        try:
            self.send_signal_message(message)

            responseMessage = None
            while True:
                responseMessage = self.websocket.recv()
                self.logger.info("Received message: %s", responseMessage)

                if (
                    responseMessage is not None
                    and self.augLoopParams.annotationType in responseMessage
                    and self.augLoopParams.workflowName in responseMessage
                ):
                    break

            if responseMessage is not None:
                response_json = json.loads(responseMessage)

                if self.augLoopParams.pathToError != "":
                    error_expr = parse(self.augLoopParams.pathToError)

                    self.logger.warning("Checking for error in response")
                    errorMessages = []
                    for errMatch in error_expr.find(response_json):
                        errorMessages.append(f'{errMatch.value["category"]}: {errMatch.value["message"]}')

                    if errorMessages is not None and len(errorMessages) > 0:
                        self.logger.warning("Found Error in response")
                        return {
                            "id": response_json["cv"],
                            "messages": errorMessages,
                            "success": True,
                            "full_message": response_json,
                        }

                self.logger.info("No error in response")

                response_expr = parse(self.augLoopParams.pathToMessages)
                responseMessages = []
                for match in response_expr.find(response_json):
                    if isinstance(match.value, str):
                        match_value = json.loads(match.value)
                    else:
                        match_value = match.value

                    if self.augLoopParams.annotationMessageParamName not in match_value:
                        continue

                    if (
                        "author" not in match_value or match_value["author"] != "user"
                    ) and "messageType" not in match_value:
                        responseMessages.append(match_value[self.augLoopParams.annotationMessageParamName])

                return {
                    "id": response_json["cv"],
                    "messages": responseMessages,
                    "success": True,
                    "full_message": response_json,
                }

            return {"success": False}
        except WebSocketConnectionClosedException:
            self.logger.info("Websocket is closed. Re-attempting connection")
            if isInRecursiveCall is False:
                self.reconnect_and_attempt_session_init()

                return self.send_signal_and_wait_for_annotation(message=message, isInRecursiveCall=True)
            return {"success": False}
        except ValueError as e:
            self.logger.error("Error: %s", str(e))
            # TODO: adding detailed message is not working, e disappears
            # if 'Expecting value: line 1 column 1 (char 0)' in str(e):
            #     self.logger.error("Check that augloop_bot_path_to_message param points to a JSON in the response")
            return {"success": False}

    def send_message_to_al(self, message: str) -> None:
        self.sequence += 1

        # make sure message does not have any new line characters
        lines = message.split("\n")

        for line in lines:
            line = line.lstrip()
            line = line.rstrip()

        message = " ".join(lines)

        if "authToken" not in message:
            self.logger.info("Sending message to AL: %s", message)

        self.websocket.send(message)

    def send_signal_message(self, message: str) -> None:
        self.id = f"id{self.sequence}"
        message = message.replace('"', '\\"')
        # pylint: disable=line-too-long
        self.send_message_to_al(
            (
                f'{{"cv":"{self.augLoopParams.cvBase}.{self.sequence}",'
                f'"seq":{self.sequence},'
                f'"ops":[{{'
                f'"parentPath":["session","doc"],'
                f'"prevId":"{self.prevId}",'
                f'"items":[{{'
                f'"id":"{self.id}",'
                f'"body":{{'
                f'"{self.augLoopParams.signalMessageParamName}":"{message}",'
                f" {self.augLoopParams.signalOtherParams} "
                f'"H_":{{'
                f'"T_":"{self.augLoopParams.signalType}",'
                f'"B_":["{self.augLoopParams.signalBaseType}"]'
                f"}}}},"
                f'"contextId":"C{self.sequence}"'
                f"}}],"
                f'"H_":{{'
                f'"T_":"AugLoop_Core_AddOperation",'
                f'"B_":["AugLoop_Core_OperationWithSiblingContext","AugLoop_Core_Operation"]'
                f"}}}},"
                f'"H_":{{'
                f'"T_":"AugLoop_Session_Protocol_SyncMessage",'
                f'"B_":["AugLoop_Session_Protocol_Message"]'
                f'}},"messageId":"c{self.sequence}"}}'
            )
        )
        self.prevId = self.id

    def reconnect_and_attempt_session_init(self) -> None:
        if self.sessionKey is None or self.sessionKey == "":
            raise Exception("SessionKey Not Found!!")

        self.logger.info("Connecting Websocket again")
        self.websocket = websocket.create_connection(self.augLoopParams.url)

        # send session init
        # pylint: disable=line-too-long
        self.send_message_to_al(
            '{{"protocolVersion":2,"clientMetadata":{{"appName":"{0}",'
            '"appPlatform":"Client","sessionKey":"{1}","origin":"{2}",'
            '"anonymousToken":"{3}","sessionId":"{4}","flights":"{5}",'
            '"appVersion":"","uiLanguage":"","roamingServiceAppId":0,'
            '"runtimeVersion":"{6}","docSessionId":"{4}"}},"extensionConfigs":[],'
            '"returnWorkflowInputTypes":false,"enableRemoteExecutionNotification":false,'
            '"H_":{{"T_":"AugLoop_Session_Protocol_SessionInitMessage",'
            '"B_":["AugLoop_Session_Protocol_Message"]}},"cv":"{7}.{8}",'
            '"messageId":"c{8}"}}'.format(
                self.augLoopParams.clientAppName,
                self.sessionKey,
                self.origin,
                self.anonToken,
                self.augLoopParams.sessionId,
                self.augLoopParams.flights,
                self.augLoopParams.runtimeVersion,
                self.augLoopParams.cvBase,
                self.sequence,
            )
        )

        maxRetry = 3
        while True:
            message = self.websocket.recv()
            self.logger.info("Re-SessionInit Response: %s", message)

            if message is None or message.find("AugLoop_Session_Protocol_SessionInitResponse") == -1:
                maxRetry = maxRetry - 1
                if maxRetry == 0:
                    raise Exception("SessionInit response not found!!")
                self.logger.info("This is not session init, response so waiting on next response")
                continue

            sessionInitResponse = json.loads(message)
            oldSessionKey = self.sessionKey
            self.sessionKey = sessionInitResponse["sessionKey"]
            self.origin = sessionInitResponse["origin"]
            self.anonToken = sessionInitResponse["anonymousToken"]
            break

        if self.sessionKey != oldSessionKey:
            msg = f"new: {sessionInitResponse['sessionKey']}"
            self.logger.warning(f"Connected to a different session, previous: {self.sessionKey}, " + msg)

            self.setup_session_after_init()

    def setup_session_after_init(self) -> None:
        # Activate annotation
        # pylint: disable=line-too-long
        self.send_message_to_al(
            '{{"annotationType":"{0}","token":"{1}-1",'
            '"ignoreExistingAnnotations":false,'
            '"H_":{{"T_":"AugLoop_Session_Protocol_AnnotationActivationMessage",'
            '"B_":["AugLoop_Session_Protocol_Message"]}},'
            '"cv":"{2}.{3}",'
            '"messageId":"c{3}"}}'.format(
                self.augLoopParams.annotationType,
                self.augLoopParams.annotationType,
                self.augLoopParams.cvBase,
                self.sequence,
            )
        )
        message = self.websocket.recv()
        self.logger.info("Ack for activate annotation: %s", message)

        # auth token message
        token = self.get_auth_token()
        # pylint: disable=line-too-long
        self.send_message_to_al(
            '{{"authToken":"{0}",'
            '"H_":{{"T_":"AugLoop_Session_Protocol_TokenProvisionMessage",'
            '"B_":["AugLoop_Session_Protocol_Message"]}},'
            '"cv":"{1}.{2}",'
            '"messageId":"c{2}"}}'.format(token, self.augLoopParams.cvBase, self.sequence)
        )
        message = self.websocket.recv()
        self.logger.info("Ack for auth token message: %s", message)

        # add doc container to session
        # pylint: disable=line-too-long
        self.send_message_to_al(
            '{{"cv":"{0}.{1}","seq":{1},"ops":['
            '{{"parentPath":["session"],"prevId":"#head","items":['
            '{{"id":"doc","body":{{"isReadonly":false,"H_":{{"T_":"AugLoop_Core_Document",'
            '"B_":["AugLoop_Core_TileGroup"]}}}},"contextId":"C{1}"}}],'
            '"H_":{{"T_":"AugLoop_Core_AddOperation","B_":['
            '"AugLoop_Core_OperationWithSiblingContext","AugLoop_Core_Operation"]}}}}],'
            '"H_":{{"T_":"AugLoop_Session_Protocol_SyncMessage",'
            '"B_":["AugLoop_Session_Protocol_Message"]}},"messageId":"c{1}"}}'.format(
                self.augLoopParams.cvBase, self.sequence
            )
        )
        message = self.websocket.recv()
        self.logger.info("Ack for seed doc: %s", message)

        self.prevId = "#head"

    def get_auth_token(self) -> Any:
        # get augloop auth token
        identity_client_id = os.environ.get("DEFAULT_IDENTITY_CLIENT_ID", None)
        if identity_client_id is not None:
            self.logger.info("Using DEFAULT_IDENTITY_CLIENT_ID: %s", identity_client_id)
            credential = ManagedIdentityCredential(client_id=identity_client_id)
        else:
            # Good for local testing.
            self.logger.info("Environment variable DEFAULT_IDENTITY_CLIENT_ID is not set, using DefaultAzureCredential")
            credential = AzureCliCredential()

        secret_client = SecretClient(vault_url=self.augLoopParams.authTokenKeyVaultUrl, credential=credential)
        auth_token = secret_client.get_secret(self.augLoopParams.authTokenKeyVaultSecretName).value
        self.logger.info(
            "Obtained augloop auth token using AzureCliCredential: %s", auth_token and not auth_token.isspace()
        )
        return auth_token

    def get_other_tokens(self) -> Dict:
        # get augloop auth token
        identity_client_id = os.environ.get("DEFAULT_IDENTITY_CLIENT_ID", None)
        if identity_client_id is not None:
            self.logger.info("Using DEFAULT_IDENTITY_CLIENT_ID: %s", identity_client_id)
            credential = ManagedIdentityCredential(client_id=identity_client_id)
        else:
            # Good for local testing.
            self.logger.info("Environment variable DEFAULT_IDENTITY_CLIENT_ID is not set, using DefaultAzureCredential")
            credential = AzureCliCredential()

        secret_client = SecretClient(vault_url=self.augLoopParams.authTokenKeyVaultUrl, credential=credential)
        tokens = {}
        for name in self.augLoopParams.otherTokenKeyVaultSecretNames:
            tokens[name] = secret_client.get_secret(name).value
            msg = f"Obtained token '{name}' using AzureCliCredential: {tokens[name] and not tokens[name].isspace()}"
            self.logger.info(msg)
        return tokens
