' Regenera y publica la web de Olfatecho sin ventana ni foco.
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "C:\Users\edumi\OneDrive\Desktop\Devue\PEnt\users\Code\olfatecho-web"
sh.Run "cmd.exe /c C:\Users\edumi\OneDrive\Desktop\Devue\PEnt\users\Code\noticiasdiarias\.venv\Scripts\python.exe -u -X utf8 publicar_web.py >> web.log 2>&1", 0, False
