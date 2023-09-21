# ---------------------------------------------------------
# Copyright (c) 2013-2022 Caleb P. Burns credits dahlia <https://github.com/dahlia>
# Licensed under the MPLv2 License. See License.txt in the project root for
# license information.
# ---------------------------------------------------------
"""
This file code has been vendored from pathspec repo.
Please do not edit it, unless really necessary
"""
import dataclasses
import os
import posixpath
import re
import warnings
from typing import Any, AnyStr, Iterable, Iterator
from typing import Match as MatchHint
from typing import Optional
from typing import Pattern as PatternHint
from typing import Tuple, Union

NORMALIZE_PATH_SEPS = [sep for sep in [os.sep, os.altsep] if sep and sep != posixpath.sep]

# The encoding to use when parsing a byte string pattern.
# This provides the base definition for patterns.
_BYTES_ENCODING = "latin1"


class Pattern(object):
    """
    The :class:`Pattern` class is the abstract definition of a pattern.
    """

    # Make the class dict-less.
    __slots__ = ("include",)

    def __init__(self, include: Optional[bool]) -> None:
        """
        Initializes the :class:`Pattern` instance.
        *include* (:class:`bool` or :data:`None`) is whether the matched
        files should be included (:data:`True`), excluded (:data:`False`),
        or is a null-operation (:data:`None`).
        """

        self.include = include
        """
        *include* (:class:`bool` or :data:`None`) is whether the matched
        files should be included (:data:`True`), excluded (:data:`False`),
        or is a null-operation (:data:`None`).
        """

    def match(self, files: Iterable[str]) -> Iterator[str]:
        """
        DEPRECATED: This method is no longer used and has been replaced by
        :meth:`.match_file`. Use the :meth:`.match_file` method with a loop
        for similar results.
        Matches this pattern against the specified files.
        *files* (:class:`~collections.abc.Iterable` of :class:`str`)
        contains each file relative to the root directory (e.g.,
        :data:`"relative/path/to/file"`).
        Returns an :class:`~collections.abc.Iterable` yielding each matched
        file path (:class:`str`).
        """
        warnings.warn(
            (
                "{0.__module__}.{0.__qualname__}.match() is deprecated. Use "
                "{0.__module__}.{0.__qualname__}.match_file() with a loop for "
                "similar results."
            ).format(self.__class__),
            DeprecationWarning,
            stacklevel=2,
        )

        for file in files:
            if self.match_file(file) is not None:
                yield file

    def match_file(self, file: str) -> Optional[Any]:
        """
        Matches this pattern against the specified file.
        *file* (:class:`str`) is the normalized file path to match against.
        Returns the match result if *file* matched; otherwise, :data:`None`.
        """
        raise NotImplementedError(
            ("{0.__module__}.{0.__qualname__} must override match_file().").format(self.__class__)
        )


class RegexPattern(Pattern):
    """
    The :class:`RegexPattern` class is an implementation of a pattern
    using regular expressions.
    """

    # Keep the class dict-less.
    __slots__ = ("regex",)

    def __init__(
        self,
        pattern: Union[AnyStr, PatternHint],
        include: Optional[bool] = None,
    ) -> None:
        """
        Initializes the :class:`RegexPattern` instance.
        *pattern* (:class:`str`, :class:`bytes`, :class:`re.Pattern`, or
        :data:`None`) is the pattern to compile into a regular expression.
        *include* (:class:`bool` or :data:`None`) must be :data:`None`
        unless *pattern* is a precompiled regular expression (:class:`re.Pattern`)
        in which case it is whether matched files should be included
        (:data:`True`), excluded (:data:`False`), or is a null operation
        (:data:`None`).
            .. NOTE:: Subclasses do not need to support the *include*
                parameter.
        """

        if isinstance(pattern, (str, bytes)):
            assert include is None, ("include:{!r} must be null when pattern:{!r} is a string.").format(
                include, pattern
            )
            regex, include = self.pattern_to_regex(pattern)
            # NOTE: Make sure to allow a null regular expression to be
            # returned for a null-operation.
            if include is not None:
                regex = re.compile(regex)

        elif pattern is not None and hasattr(pattern, "match"):
            # Assume pattern is a precompiled regular expression.
            # - NOTE: Used specified *include*.
            regex = pattern

        elif pattern is None:
            # NOTE: Make sure to allow a null pattern to be passed for a
            # null-operation.
            assert include is None, ("include:{!r} must be null when pattern:{!r} is null.").format(include, pattern)

        else:
            raise TypeError("pattern:{!r} is not a string, re.Pattern, or None.".format(pattern))

        super(RegexPattern, self).__init__(include)

        self.regex: PatternHint = regex
        """
        *regex* (:class:`re.Pattern`) is the regular expression for the
        pattern.
        """

    def __eq__(self, other: "RegexPattern") -> bool:
        """
        Tests the equality of this regex pattern with *other* (:class:`RegexPattern`)
        by comparing their :attr:`~Pattern.include` and :attr:`~RegexPattern.regex`
        attributes.
        """
        if isinstance(other, RegexPattern):
            return self.include == other.include and self.regex == other.regex
        return NotImplemented

    def match_file(self, file: str) -> Optional["RegexMatchResult"]:
        """
        Matches this pattern against the specified file.
        *file* (:class:`str`)
        contains each file relative to the root directory (e.g., "relative/path/to/file").
        Returns the match result (:class:`RegexMatchResult`) if *file*
        matched; otherwise, :data:`None`.
        """
        if self.include is not None:
            match = self.regex.match(file)
            if match is not None:
                return RegexMatchResult(match)

        return None

    @classmethod
    def pattern_to_regex(cls, pattern: str) -> Tuple[str, bool]:
        """
        Convert the pattern into an un-compiled regular expression.
        *pattern* (:class:`str`) is the pattern to convert into a regular
        expression.
        Returns the un-compiled regular expression (:class:`str` or :data:`None`),
        and whether matched files should be included (:data:`True`),
        excluded (:data:`False`), or is a null-operation (:data:`None`).
            .. NOTE:: The default implementation simply returns *pattern* and
                :data:`True`.
        """
        return pattern, True


@dataclasses.dataclass()
class RegexMatchResult(object):
    """
    The :class:`RegexMatchResult` data class is used to return information
    about the matched regular expression.
    """

    # Keep the class dict-less.
    __slots__ = ("match",)

    match: MatchHint
    """
    *match* (:class:`re.Match`) is the regex match result.
    """


class GitWildMatchPatternError(ValueError):
    """
    The :class:`GitWildMatchPatternError` indicates an invalid git wild match
    pattern.
    """


class GitWildMatchPattern(RegexPattern):
    """
    The :class:`GitWildMatchPattern` class represents a compiled Git
    wildmatch pattern.
    """

    # Keep the dict-less class hierarchy.
    __slots__ = ()

    @classmethod
    # pylint: disable=too-many-branches,too-many-statements
    def pattern_to_regex(
        cls,
        pattern: AnyStr,
    ) -> Tuple[Optional[AnyStr], Optional[bool]]:
        """
        Convert the pattern into a regular expression.
        *pattern* (:class:`str` or :class:`bytes`) is the pattern to convert
        into a regular expression.
        Returns the un-compiled regular expression (:class:`str`, :class:`bytes`,
        or :data:`None`); and whether matched files should be included
        (:data:`True`), excluded (:data:`False`), or if it is a
        null-operation (:data:`None`).
        """
        if isinstance(pattern, str):
            return_type = str
        elif isinstance(pattern, bytes):
            return_type = bytes
            pattern = pattern.decode(_BYTES_ENCODING)
        else:
            raise TypeError(f"pattern:{pattern!r} is not a unicode or byte string.")

        original_pattern = pattern
        pattern = pattern.strip()

        if pattern.startswith("#"):
            # A pattern starting with a hash ('#') serves as a comment
            # (neither includes nor excludes files). Escape the hash with a
            # back-slash to match a literal hash (i.e., '\#').
            regex = None
            include = None

        elif pattern == "/":
            # EDGE CASE: According to `git check-ignore` (v2.4.1), a single
            # '/' does not match any file.
            regex = None
            include = None

        elif pattern:
            if pattern.startswith("!"):
                # A pattern starting with an exclamation mark ('!') negates the
                # pattern (exclude instead of include). Escape the exclamation
                # mark with a back-slash to match a literal exclamation mark
                # (i.e., '\!').
                include = False
                # Remove leading exclamation mark.
                pattern = pattern[1:]
            else:
                include = True

            # Allow a regex override for edge cases that cannot be handled
            # through normalization.
            override_regex = None

            # Split pattern into segments.
            pattern_segments = pattern.split("/")

            # Normalize pattern to make processing easier.

            # EDGE CASE: Deal with duplicate double-asterisk sequences.
            # Collapse each sequence down to one double-asterisk. Iterate over
            # the segments in reverse and remove the duplicate double
            # asterisks as we go.
            for i in range(len(pattern_segments) - 1, 0, -1):
                prev = pattern_segments[i - 1]
                seg = pattern_segments[i]
                if prev == "**" and seg == "**":
                    del pattern_segments[i]

            if len(pattern_segments) == 2 and pattern_segments[0] == "**" and not pattern_segments[1]:
                # EDGE CASE: The '**/' pattern should match everything except
                # individual files in the root directory. This case cannot be
                # adequately handled through normalization. Use the override.
                override_regex = "^.+(?P<ps_d>/).*$"

            if not pattern_segments[0]:
                # A pattern beginning with a slash ('/') will only match paths
                # directly on the root directory instead of any descendant
                # paths. So, remove empty first segment to make pattern relative
                # to root.
                del pattern_segments[0]

            elif len(pattern_segments) == 1 or (len(pattern_segments) == 2 and not pattern_segments[1]):
                # A single pattern without a beginning slash ('/') will match
                # any descendant path. This is equivalent to "**/{pattern}". So,
                # prepend with double-asterisks to make pattern relative to
                # root.
                # EDGE CASE: This also holds for a single pattern with a
                # trailing slash (e.g. dir/).
                if pattern_segments[0] != "**":
                    pattern_segments.insert(0, "**")

            else:
                # EDGE CASE: A pattern without a beginning slash ('/') but
                # contains at least one prepended directory (e.g.
                # "dir/{pattern}") should not match "**/dir/{pattern}",
                # according to `git check-ignore` (v2.4.1).
                pass

            if not pattern_segments:
                # After resolving the edge cases, we end up with no pattern at
                # all. This must be because the pattern is invalid.
                raise GitWildMatchPatternError(f"Invalid git pattern: {original_pattern!r}")

            if not pattern_segments[-1] and len(pattern_segments) > 1:
                # A pattern ending with a slash ('/') will match all descendant
                # paths if it is a directory but not if it is a regular file.
                # This is equivalent to "{pattern}/**". So, set last segment to
                # a double-asterisk to include all descendants.
                pattern_segments[-1] = "**"

            if override_regex is None:
                # Build regular expression from pattern.
                output = ["^"]
                need_slash = False
                end = len(pattern_segments) - 1
                for i, seg in enumerate(pattern_segments):
                    if seg == "**":
                        if i == 0 and i == end:
                            # A pattern consisting solely of double-asterisks ('**')
                            # will match every path.
                            output.append(".+")
                        elif i == 0:
                            # A normalized pattern beginning with double-asterisks
                            # ('**') will match any leading path segments.
                            output.append("(?:.+/)?")
                            need_slash = False
                        elif i == end:
                            # A normalized pattern ending with double-asterisks ('**')
                            # will match any trailing path segments.
                            output.append("(?P<ps_d>/).*")
                        else:
                            # A pattern with inner double-asterisks ('**') will match
                            # multiple (or zero) inner path segments.
                            output.append("(?:/.+)?")
                            need_slash = True

                    elif seg == "*":
                        # Match single path segment.
                        if need_slash:
                            output.append("/")

                        output.append("[^/]+")

                        if i == end:
                            # A pattern ending without a slash ('/') will match a file
                            # or a directory (with paths underneath it). E.g., "foo"
                            # matches "foo", "foo/bar", "foo/bar/baz", etc.
                            output.append("(?:(?P<ps_d>/).*)?")

                        need_slash = True

                    else:
                        # Match segment glob pattern.
                        if need_slash:
                            output.append("/")

                        try:
                            output.append(cls._translate_segment_glob(seg))
                        except ValueError as e:
                            raise GitWildMatchPatternError(f"Invalid git pattern: {original_pattern!r}") from e

                        if i == end:
                            # A pattern ending without a slash ('/') will match a file
                            # or a directory (with paths underneath it). E.g., "foo"
                            # matches "foo", "foo/bar", "foo/bar/baz", etc.
                            output.append("(?:(?P<ps_d>/).*)?")

                        need_slash = True

                output.append("$")
                regex = "".join(output)

            else:
                # Use regex override.
                regex = override_regex

        else:
            # A blank pattern is a null-operation (neither includes nor
            # excludes files).
            regex = None
            include = None

        if regex is not None and return_type is bytes:
            regex = regex.encode(_BYTES_ENCODING)

        return regex, include

    @staticmethod
    def _translate_segment_glob(pattern: str) -> str:
        """
        Translates the glob pattern to a regular expression. This is used in
        the constructor to translate a path segment glob pattern to its
        corresponding regular expression.
        *pattern* (:class:`str`) is the glob pattern.
        Returns the regular expression (:class:`str`).
        """
        # NOTE: This is derived from `fnmatch.translate()` and is similar to
        # the POSIX function `fnmatch()` with the `FNM_PATHNAME` flag set.

        escape = False
        regex = ""
        i, end = 0, len(pattern)
        while i < end:
            # Get next character.
            char = pattern[i]
            i += 1

            if escape:
                # Escape the character.
                escape = False
                regex += re.escape(char)

            elif char == "\\":
                # Escape character, escape next character.
                escape = True

            elif char == "*":
                # Multi-character wildcard. Match any string (except slashes),
                # including an empty string.
                regex += "[^/]*"

            elif char == "?":
                # Single-character wildcard. Match any single character (except
                # a slash).
                regex += "[^/]"

            elif char == "[":
                # Bracket expression wildcard. Except for the beginning
                # exclamation mark, the whole bracket expression can be used
                # directly as regex but we have to find where the expression
                # ends.
                # - "[][!]" matches ']', '[' and '!'.
                # - "[]-]" matches ']' and '-'.
                # - "[!]a-]" matches any character except ']', 'a' and '-'.
                j = i
                # Pass back expression negation.
                if j < end and pattern[j] == "!":
                    j += 1
                # Pass first closing bracket if it is at the beginning of the
                # expression.
                if j < end and pattern[j] == "]":
                    j += 1
                # Find closing bracket. Stop once we reach the end or find it.
                while j < end and pattern[j] != "]":
                    j += 1

                if j < end:
                    # Found end of bracket expression. Increment j to be one past
                    # the closing bracket:
                    #
                    #  [...]
                    #   ^   ^
                    #   i   j
                    #
                    j += 1
                    expr = "["

                    if pattern[i] == "!":
                        # Bracket expression needs to be negated.
                        expr += "^"
                        i += 1
                    elif pattern[i] == "^":
                        # POSIX declares that the regex bracket expression negation
                        # "[^...]" is undefined in a glob pattern. Python's
                        # `fnmatch.translate()` escapes the caret ('^') as a
                        # literal. To maintain consistency with undefined behavior,
                        # I am escaping the '^' as well.
                        expr += "\\^"
                        i += 1

                    # Build regex bracket expression. Escape slashes so they are
                    # treated as literal slashes by regex as defined by POSIX.
                    expr += pattern[i:j].replace("\\", "\\\\")

                    # Add regex bracket expression to regex result.
                    regex += expr

                    # Set i to one past the closing bracket.
                    i = j

                else:
                    # Failed to find closing bracket, treat opening bracket as a
                    # bracket literal instead of as an expression.
                    regex += "\\["

            else:
                # Regular character, escape it for regex.
                regex += re.escape(char)

        if escape:
            raise ValueError(f"Escape character found with no next character to escape: {pattern!r}")

        return regex

    @staticmethod
    def escape(s: AnyStr) -> AnyStr:
        """
        Escape special characters in the given string.
        *s* (:class:`str` or :class:`bytes`) a filename or a string that you
        want to escape, usually before adding it to a ".gitignore".
        Returns the escaped string (:class:`str` or :class:`bytes`).
        """
        if isinstance(s, str):
            return_type = str
            string = s
        elif isinstance(s, bytes):
            return_type = bytes
            string = s.decode(_BYTES_ENCODING)
        else:
            raise TypeError(f"s:{s!r} is not a unicode or byte string.")

        # Reference: https://git-scm.com/docs/gitignore#_pattern_format
        meta_characters = r"[]!*#?"

        out_string = "".join("\\" + x if x in meta_characters else x for x in string)

        if return_type is bytes:
            return out_string.encode(_BYTES_ENCODING)
        return out_string


def normalize_file(file, separators=None):
    # type - (Union[Text, PathLike], Optional[Collection[Text]]) -> Text
    """
    Normalizes the file path to use the POSIX path separator (i.e.,
    ``'/'``), and make the paths relative (remove leading ``'/'``).

    *file* (:class:`str` or :class:`pathlib.PurePath`) is the file path.

    *separators* (:class:`~collections.abc.Collection` of :class:`str`; or
    :data:`None`) optionally contains the path separators to normalize.
    This does not need to include the POSIX path separator (``'/'``), but
    including it will not affect the results. Default is :data:`None` for
    :data:`NORMALIZE_PATH_SEPS`. To prevent normalization, pass an empty
    container (e.g., an empty tuple ``()``).

    Returns the normalized file path (:class:`str`).
    """
    # Normalize path separators.
    if separators is None:
        separators = NORMALIZE_PATH_SEPS

    # Convert path object to string.
    norm_file = str(file)

    for sep in separators:
        norm_file = norm_file.replace(sep, posixpath.sep)

    if norm_file.startswith("/"):
        # Make path relative.
        norm_file = norm_file[1:]

    elif norm_file.startswith("./"):
        # Remove current directory prefix.
        norm_file = norm_file[2:]

    return norm_file
