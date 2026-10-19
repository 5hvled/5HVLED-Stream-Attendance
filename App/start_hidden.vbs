Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = folder
pythonw = folder & "\.venv\Scripts\pythonw.exe"
python = folder & "\.venv\Scripts\python.exe"
If fso.FileExists(pythonw) Then
    shell.Run """" & pythonw & """ """ & folder & "\app.py"""", 0, False
ElseIf fso.FileExists(python) Then
    shell.Run """" & python & """ """ & folder & "\app.py"""", 0, False
End If
