import difflib
import webbrowser


def show_diff(left_content, right_content):
    d = difflib.HtmlDiff()
    html = d.make_file(
        left_content.splitlines(),
        right_content.splitlines(),
        "origin code",
        "new code",
        context=True,
        numlines=20)
    html = html.encode()
    fp = open("diff.html", "w+b")
    fp.write(html)
    webbrowser.open("diff.html")
    fp.close()
