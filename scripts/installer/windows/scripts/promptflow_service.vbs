DIM objshell
set objshell = wscript.createobject("wscript.shell")
iReturn = objshell.run("pfs.bat", 0, true)