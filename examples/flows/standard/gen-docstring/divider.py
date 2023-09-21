import logging
import re


class Settings:
    divide_file = {
        "py": r"(?<!.)(class|def)",
    }
    divide_func = {
        "py": r"((\n {,6})|^)(class|def)\s+(\S+(?=\())\s*(\([^)]*\))?\s*(->[^:]*:|:) *"
    }


class Divider:
    language = 'py'

    @classmethod
    def divide_file(cls, text) -> list[str]:
        matches = list(re.finditer(Settings.divide_file[Divider.language], text))
        splitted_content = []
        min_pos = matches[0].start() if len(matches) > 0 else len(text)
        for i in range(len(matches)):
            start = matches[i].start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            splitted_content.append(text[start:end])
        if min_pos != 0:
            splitted_content.insert(0, text[0:min_pos])
        return splitted_content

    @classmethod
    def divide_half(cls, text) -> list[str]:
        """
        Divide the content into two parts, but ensure that the function body is not split.
        """
        _, pos = Divider.get_functions_and_pos(text)
        if len(pos) > 1:  # Divide the code into two parts and every part start with a function.
            i = len(pos) // 2
            return [text[0:pos[i][0]], text[pos[i][0]:]]
        if len(pos) == 1:  # Divide the code into two parts, [function define + body, other body].
            body = text[pos[0][1]:]
            body_lines = body.split('\n')
            body_ten_lines = '\n'.join(body_lines[0:10])
            return [text[0:pos[0][1]] + body_ten_lines, body[len(body_ten_lines):]]
        return [text]

    @classmethod
    def get_functions_and_pos(cls, text):
        matches = re.finditer(Settings.divide_func[Divider.language], text)
        functions = []
        pos = []
        for match in matches:
            matched_text = match.group().replace('\n', '')
            func = re.sub(r' +', ' ', matched_text).replace(' :', ':')
            func = re.sub(r'[\s,]+\)', ')', func)
            func = re.sub(r'\([\s,]+', '(', func)
            functions.append(func.strip())
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
        code = origin_code if len(funcs2) == 0 else origin_code[0:pos2[0][0]]
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
                func_line = origin_code[pos2[i2][0]:pos2[i2][1]].replace('\n', '')
                empty_line_num = (len(func_line) - len(func_line.lstrip()) + 4)
                func_body = origin_code[pos2[i2][1]:pos2[i2 + 1][0]]
                code_doc = list(re.finditer(pattern, func_body, re.DOTALL))
                format_new_doc = Divider.format_indentation(new_doc[0], empty_line_num)
                is_replace_doc = len(code_doc) > 0 and (re.sub(r'\s+', '', func_body[0:code_doc[0].start()]) == '')
                if is_replace_doc:
                    code += part_full_code.replace(code_doc[0].group(), format_new_doc.strip(), 1)
                else:
                    code += origin_code[pos2[i2][0]:pos2[i2][1]] + '\n' + format_new_doc + '\n' + origin_code[
                                                                                                  pos2[i2][1]:
                                                                                                  pos2[i2 + 1][0]]
            else:
                code += part_full_code
        return code

    @classmethod
    def format_indentation(cls, text, empty_line_num):
        lines = text.splitlines()
        last_line_space_num = len(lines[-1]) - len(lines[-1].lstrip())
        need_add_space = max(empty_line_num - last_line_space_num, 0) * ' '
        lines[0] = last_line_space_num * ' ' + lines[0].lstrip()  # Align the first row to the last row
        indented_lines = [(need_add_space + line).rstrip() for line in lines]
        indented_string = '\n'.join(indented_lines)
        return indented_string

    @classmethod
    def has_class_or_func(cls, text):
        funcs, _ = Divider.get_functions_and_pos(text)
        return len(funcs) > 0
