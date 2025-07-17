from Frontend.GUI import (
    GraphicalUserInterface,
    SetAssistantStatus,
    ShowTextToScreen,
    TempDirectoryPath,
    SetMicrophoneStatus,
    AnswerModifier,
    QueryModifier
    # Removed GetMicrophoneStatus and GetAssistantStatus as they are not needed for this logic
)

from Backend.Model import FirstLayerDMM
from Backend.RealtimeSearchEngine import RealtimeSearchEngine
from Backend.Automation import Automation
from Backend.Speech import takecommand, speak
from Backend.Chatbot import ChatBot
from dotenv import dotenv_values
from asyncio import run
from time import sleep
import subprocess
import threading
import json
import os

# Load environment variables
env_vars = dotenv_values(".env")
Username = env_vars.get("Username")
Assistantname = env_vars.get("Assistantname")
DefaultMessage = f"""{Username} : Hello {Assistantname}, How are you?
{Assistantname} : Welcome {Username}. I am doing well. How may I help you?"""

subprocesses = []
Functions = ["open", "close", "play", "system", "content", "google search", "youtube search"]

# --- MODIFIED ---
# This flag is now the single source of truth for the listening state.
ListeningFlag = False

def ShowDefaultChatIfNoChats():
    try:
        with open(r'Data\ChatLog.json', "r", encoding='utf-8') as File:
            if len(File.read()) < 5:
                with open(TempDirectoryPath('Database.data'), 'w', encoding='utf-8') as file:
                    file.write("")
                with open(TempDirectoryPath('Responses.data'), 'w', encoding='utf-8') as file:
                    file.write(DefaultMessage)
    except FileNotFoundError:
        os.makedirs('Data', exist_ok=True)
        with open(r'Data\ChatLog.json', 'w', encoding='utf-8') as f:
            json.dump([], f)
        ShowDefaultChatIfNoChats()

def ReadChatLogJson():
    with open(r'Data\ChatLog.json', 'r', encoding='utf-8') as file:
        return json.load(file)

def ChatLogIntegration():
    json_data = ReadChatLogJson()
    formatted_chatlog = ""
    for entry in json_data:
        if entry["role"] == "user":
            formatted_chatlog += f"User: {entry['content']}\n"
        elif entry["role"] == "assistant":
            formatted_chatlog += f"Assistant: {entry['content']}\n"

    formatted_chatlog = formatted_chatlog.replace("User", Username + "")
    formatted_chatlog = formatted_chatlog.replace("Assistant", Assistantname + "")

    with open(TempDirectoryPath('Database.data'), 'w', encoding='utf-8') as file:
        file.write(AnswerModifier(formatted_chatlog))

def ShowChatsOnGUI():
    with open(TempDirectoryPath('Database.data'), "r", encoding='utf-8') as File:
        Data = File.read()
        if len(str(Data)) > 0:
            with open(TempDirectoryPath('Responses.data'), "w", encoding='utf-8') as f:
                f.write('\n'.join(Data.split('\n')))

def InitialExecution():
    SetMicrophoneStatus("False") # Keep for initial GUI icon state
    ShowTextToScreen("")
    ShowDefaultChatIfNoChats()
    ChatLogIntegration()
    ShowChatsOnGUI()
    SetAssistantStatus("Available ...") # Set initial status

def MainExecution():
    global ListeningFlag
    TaskExecution = False
    ImageExecution = False
    ImageGenerationQuery = ""

    SetAssistantStatus("Listening ...")
    Query = takecommand()
    if not Query:
        SetAssistantStatus("Available ...")
        # --- MODIFIED ---
        # We set the flag to False here because takecommand() returned nothing,
        # meaning the user didn't speak. This allows the GUI to update correctly.
        ListeningFlag = False
        SetMicrophoneStatus("False")
        return

    # --- MODIFIED ---
    # The listening process is complete, so we turn the flag off
    # It will be turned on again ONLY when the user clicks the button
    ListeningFlag = False
    SetMicrophoneStatus("False") # To ensure GUI icon updates

    ShowTextToScreen(f"{Username} : {Query}")
    SetAssistantStatus("Thinking ...")
    Decision = FirstLayerDMM(Query)

    print(f"\nDecision: {Decision}\n")

    G = any(i.startswith("general") for i in Decision)
    R = any(i.startswith("realtime") for i in Decision)

    Merged_query = " and ".join(
        [" ".join(i.split()[1:]) for i in Decision if i.startswith("general") or i.startswith("realtime")]
    )

    for queries in Decision:
        if "generate image" in queries:
            ImageGenerationQuery = queries.replace("generate image", "").strip()
            ImageExecution = True

    for queries in Decision:
        if not TaskExecution:
            if any(queries.startswith(func) for func in Functions):
                try:
                    run(Automation(Decision))
                    TaskExecution = True
                except Exception as e:
                    print("Automation Error:", e)

    if ImageExecution:
        try:
            with open(r"Frontend\Files\ImageGeneration.data", "w") as file:
                file.write(f"{ImageGenerationQuery}, True")
            p1 = subprocess.Popen(['python', r'Backend\ImageGeneration.py'],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  stdin=subprocess.PIPE, shell=False)
            subprocesses.append(p1)
            speak(f"Generating image for {ImageGenerationQuery}.")
        except Exception as e:
            print(f"Error starting ImageGeneration.py: {e}")
        # --- ADDED --- This was missing before
        SetAssistantStatus("Available ...")
        return

    if G and R or R:
        try:
            SetAssistantStatus("Searching ...")
            Answer = RealtimeSearchEngine(QueryModifier(Merged_query))
            ShowTextToScreen(f"{Assistantname} : {Answer}")
            SetAssistantStatus("Answering ...")
            speak(Answer)
        except Exception as e:
            print("RealtimeSearch Error:", e)
        # --- ADDED --- This was missing before
        SetAssistantStatus("Available ...")
        return

    for Queries in Decision:
        if "general" in Queries:
            SetAssistantStatus("Thinking ...")
            QueryFinal = Queries.replace("general ", "")
            Answer = ChatBot(QueryModifier(QueryFinal))
            ShowTextToScreen(f"{Assistantname} : {Answer}")
            SetAssistantStatus("Answering ...")
            speak(Answer)
            SetAssistantStatus("Available ...")
            return

        elif "realtime" in Queries:
            SetAssistantStatus("Searching ...")
            QueryFinal = Queries.replace("realtime ", "")
            Answer = RealtimeSearchEngine(QueryModifier(QueryFinal))
            ShowTextToScreen(f"{Assistantname} : {Answer}")
            SetAssistantStatus("Answering ...")
            speak(Answer)
            SetAssistantStatus("Available ...")
            return

        elif "exit" in Queries:
            QueryFinal = "Okay, Bye!"
            Answer = ChatBot(QueryModifier(QueryFinal))
            ShowTextToScreen(f"{Assistantname} : {Answer}")
            SetAssistantStatus("Answering ...")
            speak(Answer)
            SetAssistantStatus("Available ...")
            os._exit(0)

# --- MODIFIED --- This is the backend logic loop.
def FirstThread():
    # Run initial setup once.
    InitialExecution()
    
    while True:
        if ListeningFlag:
            MainExecution()
        else:
            # Sleep to prevent the loop from using 100% CPU when not listening
            sleep(0.1)

# --- MODIFIED --- This function is now the controller.
def ToggleListening():
    global ListeningFlag
    ListeningFlag = not ListeningFlag
    if ListeningFlag:
        SetMicrophoneStatus("True") # For GUI icon
        SetAssistantStatus("Listening ...")
    else:
        SetMicrophoneStatus("False") # For GUI icon
        SetAssistantStatus("Available ...")


if __name__ == "__main__":
    # --- MODIFIED ---
    # The GUI must run on the main thread.
    # The backend logic will run in a separate, non-blocking "daemon" thread.

    # 1. Create and start the backend thread.
    backend_thread = threading.Thread(target=FirstThread, daemon=True)
    backend_thread.start()

    # 2. Run the GUI on the main thread, passing it the function to call when the mic is clicked.
    GraphicalUserInterface(toggle_callback=ToggleListening)