Set FSO = CreateObject("Scripting.FileSystemObject")
strPath = FSO.GetParentFolderName(WScript.ScriptFullName)

Set WshShell = CreateObject("WScript.Shell")
' Set the working directory to where the script is located
WshShell.CurrentDirectory = strPath

' Kill any existing instances of the app to prevent multiple copies running
On Error Resume Next
Set objWMIService = GetObject("winmgmts:\\.\root\cimv2")
Set colProcesses = objWMIService.ExecQuery("Select * from Win32_Process Where Name = 'pythonw.exe' And CommandLine Like '%system%main.py%'")
For Each objProcess in colProcesses
    objProcess.Terminate()
Next
On Error GoTo 0

' Check if Python is fully installed
If Not FSO.FileExists(strPath & "\system\python\.installed_ok") Then
    ' Run installer visibly
    MsgBox "First launch: Required files (Python, PyTorch) will now be downloaded. A console window will appear, please do not close it.", 64, "Installation"
    WshShell.Run chr(34) & strPath & "\system\install.cmd" & chr(34), 1, True
End If

' Run app hidden
If FSO.FileExists(strPath & "\system\python\.installed_ok") Then
    WshShell.Run chr(34) & strPath & "\system\python\pythonw.exe" & chr(34) & " " & chr(34) & strPath & "\system\main.py" & chr(34), 1, False
End If
