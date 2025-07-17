from AppOpener import close, open as appopen
from webbrowser import open as webopen
from pywhatkit import search, playonyt
from dotenv import dotenv_values
from bs4 import BeautifulSoup
from rich import print
from groq import Groq
import webbrowser
import subprocess
import requests
import keyboard
import asyncio
import os

env_vars = dotenv_values(".env")
GroqAPIKey = env_vars.get("GroqAPIKey")

useragent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
client = Groq(api_key=GroqAPIKey)

messages = []
SystemChatBot = [{"role": "system", "content": f"Hello, I am {os.environ.get('Username', 'User')}, You're a content writer."}]

def GoogleSearch(Topic):
    search(Topic)
    return True

def Content(Topic):
    def OpenNotepad(File):
        subprocess.Popen(['notepad.exe', File])

    def ContentWriterAI(prompt):
        messages.append({"role": "user", "content": prompt})
        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=SystemChatBot + messages,
            max_tokens=2048,
            temperature=0.7,
            top_p=1,
            stream=True,
            stop=None
        )
        Answer = ""
        for chunk in completion:
            if chunk.choices[0].delta.content:
                Answer += chunk.choices[0].delta.content
        Answer = Answer.replace("</s>", "")
        messages.append({"role": "assistant", "content": Answer})
        return Answer

    Topic = Topic.replace("Content", "").strip()
    ContentByAI = ContentWriterAI(Topic)
    filepath = rf"Data\{Topic.lower().replace(' ', '_')}.txt"
    with open(filepath, "w", encoding="utf-8") as file:
        file.write(ContentByAI)
    OpenNotepad(filepath)
    return True

def YouTubeSearch(Topic):
    url = f"https://www.youtube.com/results?search_query={Topic}"
    webbrowser.open(url)
    return True

def PlayYoutube(query):
    playonyt(query)
    return True

def OpenApp(app, sess=requests.session()):
    try:
        appopen(app, match_closest=True, output=True, throw_error=True)
        return True
    except:
        if "youtube" in app.lower():
            webbrowser.open("https://www.youtube.com")
            return True

        def extract_links(html):
            soup = BeautifulSoup(html or '', 'html.parser')
            links = soup.find_all('a', {'jsname': 'UWckNb'})
            return [link.get('href') for link in links if link.get('href')]

        def search_google(query):
            url = f"https://www.google.com/search?q={query}"
            headers = {"User-Agent": useragent}
            response = sess.get(url, headers=headers)
            return response.text if response.status_code == 200 else None

        html = search_google(app)
        links = extract_links(html)
        if links:
            webopen(links[0])
        else:
            print("No links found.")
        return True

def CloseApp(app):
    try:
        close(app, match_closest=True, output=True, throw_error=True)
        return True
    except:
        print(f"Failed to close: {app}")
        return False

def system(command):
    if command == "mute" or command == "unmute":
        keyboard.press_and_release("volume mute")
    elif command == "volume up":
        keyboard.press_and_release("volume up")
    elif command == "volume down":
        keyboard.press_and_release("volume down")
    return True

async def TranslateAndExecute(commands: list[str]):
    funcs = []
    for command in commands:
        cmd = command.lower().strip()
        if cmd.startswith("open "):
            funcs.append(asyncio.to_thread(OpenApp, cmd.removeprefix("open ").strip()))
        elif cmd.startswith("close"):
            funcs.append(asyncio.to_thread(CloseApp, cmd.removeprefix("close").strip()))
        elif cmd.startswith("play"):
            funcs.append(asyncio.to_thread(PlayYoutube, cmd.removeprefix("play").strip()))
        elif cmd.startswith("content"):
            funcs.append(asyncio.to_thread(Content, cmd.removeprefix("content").strip()))
        elif cmd.startswith("google search"):
            funcs.append(asyncio.to_thread(GoogleSearch, cmd.removeprefix("google search").strip()))
        elif cmd.startswith("youtube search"):
            funcs.append(asyncio.to_thread(YouTubeSearch, cmd.removeprefix("youtube search").strip()))
        elif cmd.startswith("system"):
            funcs.append(asyncio.to_thread(system, cmd.removeprefix("system").strip()))
        elif cmd.startswith("general") or cmd.startswith("realtime"):
            continue  # Skip these types for automation
        else:
            print(f"No Function Found For: {command}")

    results = await asyncio.gather(*funcs)
    for result in results:
        yield result

async def Automation(commands: list[str]):
    async for _ in TranslateAndExecute(commands):
        pass
    return True
