DIM objshell
set objshell = wscript.createobject("wscript.shell")
cmd = WScript.Arguments(0)
iReturn = objshell.run(cmd, 0, false)
