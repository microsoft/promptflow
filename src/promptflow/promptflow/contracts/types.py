# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


class Secret(str):
    """This class is used to hint a parameter is a secret to load."""

    def set_secret_name(self, name):
        """Set the secret_name attribute for the Secret instance.

        :param name: The name of the secret.
        :type name: str
        """
        self.secret_name = name


class PromptTemplate(str):
    """This class is used to hint a parameter is a prompt template."""

    pass


class FilePath(str):
    """This class is used to hint a parameter is a file path."""

    pass
