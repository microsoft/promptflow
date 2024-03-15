DIM objshell
set objshell = wscript.createobject("wscript.shell")
cmd = """%MAIN_EXE%"" pfs %*"
iReturn = objshell.run(cmd, 0, true)