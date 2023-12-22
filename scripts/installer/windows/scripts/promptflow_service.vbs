DIM objshell
set objshell = wscript.createobject("wscript.shell")
iReturn = objshell.run("pfs.bat start --force", 0, true)