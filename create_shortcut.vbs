Set WshShell = CreateObject("WScript.Shell")
desktopPath = WshShell.SpecialFolders("Desktop")
Set shortcut = WshShell.CreateShortcut(desktopPath & "\Meeting Minutes AI.lnk")
shortcut.TargetPath = "C:\zriil\code\Meeting Minutes AI\start.bat"
shortcut.WorkingDirectory = "C:\zriil\code\Meeting Minutes AI"
shortcut.Description = "AI Meeting Minutes"
shortcut.WindowStyle = 1
shortcut.Save
WScript.Echo "Done"
