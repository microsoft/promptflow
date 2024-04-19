DIM objshell
set objshell = wscript.createobject("wscript.shell")
iReturn = objshell.run("pfcli.exe pf service stop", 0, true)