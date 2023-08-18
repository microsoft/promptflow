import logging
import re


class Settings:
    divide_start = {
        "py": r"(?<!.)(class|def)",
    }
    divide_end = {
        "py": r"\n(def|class)",
    }
    matchs = {
        "py": r"((\n {,6})|^)(class|def)\s+(\w+)\s*(\([^)]*\))?\s*(->\s*\w+:|:) *"
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
        _, pos = Divider.get_functions_and_pos(text)
        if len(pos) > 1:
            i = len(pos) // 2
            return [text[0:pos[i][0]], text[pos[i][0]:]]
        return text

    @classmethod
    def get_functions_and_pos(cls, text):
        matches = re.finditer(Settings.matchs[Divider.language], text)
        functions = []
        pos = []
        for match in matches:
            matched_text = match.group().replace('\n', '')
            func = re.sub(r' +', ' ', matched_text)
            functions.append(re.sub(r'[\s,]+\)', ')', func).strip())
            pos.append((match.start(), match.end()))
        return functions, pos

    @classmethod
    def combine(cls, divided: list[str]):
        return ''.join(divided)

    @classmethod
    def merge_doc2code(cls, docstring: str, origin_code: str) -> str:
        funcs1, pos1 = Divider.get_functions_and_pos(docstring)
        funcs2, pos2 = Divider.get_functions_and_pos(origin_code)
        pattern = r'""".*?"""'
        code = ""
        pos1.append((len(docstring), len(docstring)))  # avoid index out of range
        pos2.append((len(origin_code), len(origin_code)))  # avoid index out of range
        for i2 in range(len(funcs2)):  # add docstring for each function in origin_code
            part_full_code = origin_code[pos2[i2][0]:pos2[i2 + 1][0]]
            try:
                i1 = funcs1.index(funcs2[i2])
            except ValueError:
                logging.warning(f"No docstring found for {funcs2[i2]}")
                code += part_full_code
                continue
            new_doc = re.findall(pattern, docstring[pos1[i1][1]:pos1[i1 + 1][0]], re.DOTALL)
            if new_doc:
                line = origin_code[pos2[i2][0]:pos2[i2][1]].replace('\n', '')
                lspace_num = (len(line) - len(line.lstrip()) + 4)
                code_doc = re.findall(pattern, origin_code[pos2[i2][1]:pos2[i2 + 1][0]], re.DOTALL)
                format_new_doc = Divider.format_indentation(new_doc[0], lspace_num)
                if code_doc:
                    code += part_full_code.replace(code_doc[0], format_new_doc.strip(), 1)
                else:
                    code += origin_code[pos2[i2][0]:pos2[i2][1]] + '\n' + format_new_doc + '\n' + origin_code[pos2[i2][1]:pos2[i2 + 1][0]]
        return code

    @classmethod
    def format_indentation(cls, text, lspace_num):
        lines = text.split('\n')
        last_line_space_num = len(lines[-1]) - len(lines[-1].lstrip())
        need_add_space = max(lspace_num - last_line_space_num, 0) * ' '
        lines[0] = last_line_space_num * ' ' + lines[0].lstrip()  # Align the first row to the last row
        indented_lines = [(need_add_space + line).rstrip() for line in lines]
        indented_string = '\n'.join(indented_lines)
        return indented_string
