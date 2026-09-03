import os, shutil

# Check what apps are installed
checks = {
    "chrome": [
        os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ],
    "edge": [
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe"),
    ],
    "spotify": [
        os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\Spotify.exe"),
    ],
    "discord": [
        os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Discord\app-*\Discord.exe"),  # glob needed
    ],
    "steam": [
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Steam\steam.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Steam\steam.exe"),
    ],
    "whatsapp": [
        os.path.expandvars(r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe"),
        os.path.expandvars(r"%APPDATA%\WhatsApp\WhatsApp.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\WhatsApp.exe"),
    ],
    "vscode": [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Microsoft VS Code\Code.exe"),
    ]
}

for app, paths in checks.items():
    found = None
    for p in paths:
        if '*' not in p and os.path.exists(p):
            found = p
            break
    if not found:
        found = shutil.which(app) or shutil.which(app + ".exe")
    print(f"{app}: {found or 'NOT FOUND'}")

# Also check Discord via glob
import glob
discord_glob = os.path.expandvars(r"%LOCALAPPDATA%\Discord\app-*\Discord.exe")
matches = glob.glob(discord_glob)
if matches:
    print(f"discord (glob): {matches[-1]}")
else:
    print("discord (glob): NOT FOUND")
