DIM objshell
set objshell = wscript.createobject("wscript.shell")
iReturn = objshell.run("pfcli.exe pf service start --force", 0, true)