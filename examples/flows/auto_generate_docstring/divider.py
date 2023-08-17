import re


class Settings:
    divide_start = {
        "py": r"(?<!.)(class|def)",
    }
    divide_end = {
        "py": r"\n(def|class)",
    }
    matchs = {
        "py": r" *(class|def)\s+(\w+)\s*(\([^)]*\))?\s*(->\s*\w+:|:)"
    }


class Divider:
    language = 'py'

    @classmethod
    def divide_file(cls, text) -> list[str]:
        starts = re.finditer(Settings.divide_start[Divider.language], text)
        ends = re.finditer(Settings.divide_end[Divider.language], text)
        splitted_content = []

        while True:
            start = None
            try:
                start = next(starts).start()
                end = next(ends).start()
                if end < start:
                    end = next(ends).start()
                splitted_content.append(text[start:end])
            except:
                if start != None:
                    splitted_content.append(text[start:])
                break

        return splitted_content

    @classmethod
    def divide_half(cls, text) -> list[str]:
        """
        Divide the content into two parts, but ensure that the function body is not split.
        """
        matches = re.finditer(Settings.matchs[Divider.language], text)
        indexes = []
        for match in matches:
            indexes.append((match.start(), match.end()))

        if len(indexes) > 1:
            i = len(indexes) // 2
            return [text[0:indexes[i][0]], text[indexes[i][0]:]]
        return text

    @classmethod
    def get_functions(cls, text) -> list[str]:
        matches = re.finditer(Settings.matchs[Divider.language], text)
        functions = []
        for match in matches:
            matched_text = match.group().strip()
            functions.append(re.sub(r'\s+', ' ', matched_text.replace('\n', '')).replace(', )', ')'))
        return functions

    @classmethod
    def combine(cls, divided: list[str]):
        return ''.join(divided)

    @classmethod
    def merge_doc2code(cls, docstring: str, origin_code: str) -> str:
        regexpes = re.finditer(r"\==(.+?)\==", docstring)
        indexes = []

        while True:
            try:
                match = next(regexpes)
                start = match.start()
                end = match.end()
                indexes.append((start, end))
            except:
                break

        names = []
        comments = []
        for i in range(len(indexes)):
            names.append(docstring[indexes[i][0] + 2:indexes[i][1] - 2])
            if i < len(indexes) - 1:
                doc = docstring[indexes[i][1] + 1: indexes[i + 1][0]]
                comments.append(doc.rstrip())
            elif docstring[indexes[i][1]:] != "==end==":
                comments.append(docstring[indexes[i][1]:])

        code = origin_code
        for i in range(len(names)):
            try:
                index = code.index(names[i])
            except ValueError:
                continue
            split_start = code[index:]
            doubledot = index + split_start.index(":\n") + 1
            tabs = re.search(r":\n(.*?)[a-zA-Z]", split_start).span()
            tabs_count = tabs[1] - tabs[0]
            tab = (tabs_count - 3) * " "
            replace_text = code[index:doubledot]
            new_replace_text = comments[i].replace("\n", f"\n{tab}")
            code = code.replace(
                replace_text,
                f'{replace_text}\n{tab}"""\n{tab}{new_replace_text}\n{tab}"""',
            )
        return code
