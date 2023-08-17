import re


class Settings:
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
    def divide_func(cls, text) -> list[str]:
        pattern = r"(class [A-Za-z0-9_]+\([^)]*\):)|(def [A-Za-z0-9_]+\([^)]*\):)"
        # pattern = r'(class|def)\s+([A-Za-z0-9_]\w*)\s*\(([^)]*)\)(\s*->\s*([^:]+):)?[:\(]'
        splitted_content = []

        matches = re.finditer(pattern, text)
        for match in matches:
            matched_text = match.group()
            start_pos = match.start()
            end_pos = match.end()

            print("Matched Text:\n", matched_text)
            print("Start Position:", start_pos, ' ', text[start_pos])
            print("End Position:", end_pos, ' ', text[end_pos-1])
            print()

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
