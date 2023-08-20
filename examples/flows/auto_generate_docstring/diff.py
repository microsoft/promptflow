import difflib
import webbrowser


def show_diff(left_content, right_content, name="file"):
    d = difflib.HtmlDiff()
    html = d.make_file(
        left_content.splitlines(),
        right_content.splitlines(),
        "origin " + name,
        "new " + name,
        context=True,
        numlines=20)
    html = html.encode()
    html_name = name + "_diff.html"
    fp = open(html_name, "w+b")
    fp.write(html)
    webbrowser.open(html_name)
    fp.close()
