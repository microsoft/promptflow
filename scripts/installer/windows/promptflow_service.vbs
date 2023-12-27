DIM objshell
set objshell = wscript.createobject("wscript.shell")
iReturn = objshell.run("pfs.exe start --force", 0, true)