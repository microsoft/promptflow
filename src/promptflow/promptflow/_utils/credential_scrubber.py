# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import re


class CredentialScrubber:
    """Scrub sensitive information in string."""

    PLACE_HOLDER = "**data_scrubbed**"
    LENGTH_THRESHOLD = 2

    def __init__(self):
        self.default_regex_set = set(
            [
                r"(?<=sig=)[^\s;&]+",  # Replace signature.
                r"(?<=key=)[^\s;&]+",  # Replace key.
            ]
        )
        self.default_str_set = set()
        self.custom_regex_set = set()
        self.custom_str_set = set()

    def scrub(self, input: str):
        """Replace sensitive information in input string with PLACE_HOLDER.

        For example, for input string: "print accountkey=accountKey", the output will be:
        "print accountkey=**data_scrubbed**"
        """
        output = input
        regex_set = self.default_regex_set.union(self.custom_regex_set)
        for regex in regex_set:
            output = re.sub(regex, self.PLACE_HOLDER, output, flags=re.IGNORECASE)

        str_set = self.default_str_set.union(self.custom_str_set)
        for s in str_set:
            output = output.replace(s, self.PLACE_HOLDER)
        return output

    def add_regex(self, pattern: str):
        # policy: http://policheck.azurewebsites.net/Pages/TermInfo.aspx?LCID=9&TermID=79458
        """Add regex pattern to checklist."""
        self.custom_regex_set.add(pattern)

    def add_str(self, s: str):
        """Add string to checklist.

        Only scrub string with length > LENGTH_THRESHOLD.
        """
        if s is None:
            return

        if len(s) <= self.LENGTH_THRESHOLD:
            return
        self.custom_str_set.add(s)

    def clear(self):
        """Clear custom regex and string set."""
        self.custom_regex_set = set()
        self.custom_str_set = set()
