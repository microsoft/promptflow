import re


class Settings:
    supported_languages = ["py"]
    divide_start = {
        "py": r"(?<!.)(class|def)",
    }
    divide_end = {
        "py": r"\n(def|class)",
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
    def divide_class_or_func(cls, text) -> list[str]:
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
                comments.append(docstring[indexes[i][1] + 1: indexes[i + 1][0]])
            elif docstring[indexes[i][1]:] != "==end==":
                comments.append(docstring[indexes[i][1]:])

        code = origin_code
        for i in range(len(names)):
            index = code.index(names[i])
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

    def __ts(self) -> str:
        regexpes = re.finditer(r"\|(.+?)\|\n", self.__text_comment)
        indexes = []

        while True:
            try:
                match = next(regexpes)
                start = match.start()
                end = match.end() - 1
                indexes.append((start, end))
            except:
                break

        names: list[str] = []
        comments: list[str] = []
        for i in range(len(indexes)):
            names.append(self.__text_comment[indexes[i][0] + 1 : indexes[i][1] - 1])
            if i < len(indexes) - 1:
                comments.append(
                    re.sub(
                        r"Comment:\n|Comment: \n",
                        "",
                        self.__text_comment[indexes[i][1] + 1 : indexes[i + 1][0]],
                    )
                )
            else:
                comments.append(
                    self.__text_comment[indexes[i][1] :].replace("Comment:\n", "")
                )

        for i in range(len(names)):
            comments[i] = " * " + comments[i].replace("\n", "\n * ")
            comments[i] = re.sub(r"\n\s\*\s\n\s\*\s", "", comments[i])
            index = self.__code.find(names[i])

            for j in range(index, 0, -1):
                if self.__code[j] == "\n":
                    from_new_string = self.__code[j + 1 :]
                    tabs_end = re.search(r"[a-zA-Z]", from_new_string).start()
                    tabs = from_new_string[:tabs_end]
                    comments[i] = re.sub(r"\n", f"\n{tabs}", comments[i])
                    splitted_code = list(self.__code)
                    splitted_code[j] = f"\n{tabs}/**\n{tabs}{comments[i]}\n{tabs} */\n"
                    self.__code = "".join(splitted_code)
                    break
            else:
                self.__code = f"\n/**\n{comments[i]}\n */\n" + self.__code
        return self.__code
