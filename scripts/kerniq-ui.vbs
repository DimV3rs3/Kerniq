Set sh = CreateObject("WScript.Shell")
' No console window — run UI from repo parent of scriptsDim fso, here, root
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
root = fso.GetParentFolderName(here)
sh.CurrentDirectory = root
sh.Run "pythonw -m Kerniq plugins ui", 0, False
