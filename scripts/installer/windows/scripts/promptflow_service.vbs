DIM objshell
set objshell = wscript.createobject("wscript.shell")
iReturn = objshell.run("pfcli.exe pfs start --force", 0, true)