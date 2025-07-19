from Frontend.GUI import (
    GraphicalUserInterface,
    SetAssistantStatus,
    ShowTextToScreen,
    TempDirectoryPath,
    SetMicrophoneStatus,
    AnswerModifier,
    QueryModifier
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
import sys # Import sys for platform-specific subprocess creation

# Load environment variables
env_vars = dotenv_values(".env")
Username = env_vars.get("Username")
Assistantname = env_vars.get("Assistantname")
DefaultMessage = f"""{Username} : Hello {Assistantname}, How are you?
{Assistantname} : Welcome {Username}. I am doing well. How may I help you?"""

# Global list to keep track of subprocesses (useful for cleanup if needed)
subprocesses = []
# Global variable to store the image generation process reference
image_generation_process = None 
# Log file for the image generation subprocess
image_gen_log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "image_generation.log")

Functions = ["open", "close", "play", "system", "content", "google search", "Youtube"]

ListeningFlag = False

def ShowDefaultChatIfNoChats():
    try:
        with open(r'Data\ChatLog.json', "r", encoding='utf-8') as File:
            file_content = File.read().strip()
            if not file_content or file_content == "[]":
                os.makedirs(os.path.dirname(TempDirectoryPath('Database.data')), exist_ok=True)

                with open(TempDirectoryPath('Database.data'), 'w', encoding='utf-8') as file:
                    file.write("")
                with open(TempDirectoryPath('Responses.data'), 'w', encoding='utf-8') as file:
                    file.write(DefaultMessage)
                if not file_content:
                    with open(r'Data\ChatLog.json', 'w', encoding='utf-8') as f:
                        json.dump([], f)
    except FileNotFoundError:
        os.makedirs('Data', exist_ok=True)
        with open(r'Data\ChatLog.json', 'w', encoding='utf-8') as f:
            json.dump([], f)
        ShowDefaultChatIfNoChats()

def ReadChatLogJson():
    try:
        with open(r'Data\ChatLog.json', 'r', encoding='utf-8') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"ChatLog.json not found or corrupted. Creating empty file.")
        with open(r'Data\ChatLog.json', 'w', encoding='utf-8') as f:
            json.dump([], f)
        return []

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
    SetMicrophoneStatus("False")
    ShowTextToScreen("")
    ShowDefaultChatIfNoChats()
    ChatLogIntegration()
    ShowChatsOnGUI()
    SetAssistantStatus("Available ...")
    start_image_generation_process() # This is where the image gen script is launched!

# --- Function to manage the image generation subprocess ---
def start_image_generation_process():
    global image_generation_process, image_gen_log_file
    # Check if the process is already running and healthy
    if image_generation_process and image_generation_process.poll() is None:
        print("[Main] Image generation process is already running.")
        return 

    image_gen_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), r"Backend\ImageGeneration.py")
    
    if not os.path.exists(image_gen_script_path):
        print(f"[Main] Error: Image generation script not found at {image_gen_script_path}")
        return

    print(f"[Main] Starting image generation script: {image_gen_script_path}. Logging to {image_gen_log_file}")
    
    # Open log file for subprocess output. 'a' for append, buffering=1 for line-buffering.
    try:
        log_file_handle = open(image_gen_log_file, 'a', buffering=1)
    except IOError as e:
        print(f"[Main] Error opening image generation log file {image_gen_log_file}: {e}")
        return # Cannot start if cannot log

    try:
        # The project root directory is where main.py is located
        project_root_dir = os.path.dirname(os.path.abspath(__file__))

        # Launch the subprocess, redirecting its stdout/stderr to our log file.
        # For initial debugging, we'll avoid DETACHED_PROCESS so it's a child
        # of the current terminal and easier to kill if it hangs.
        if sys.platform == "win32":
            image_generation_process = subprocess.Popen(
                [sys.executable, image_gen_script_path],
                stdout=log_file_handle, # Redirect stdout to log file
                stderr=log_file_handle, # Redirect stderr to log file
                creationflags=0, # No detached process for debugging. Use subprocess.DETACHED_PROCESS for full detachment.
                cwd=project_root_dir # Set working directory for the subprocess
            )
        else: # For Linux/macOS
            image_generation_process = subprocess.Popen(
                [sys.executable, image_gen_script_path],
                stdout=log_file_handle, # Redirect stdout to log file
                stderr=log_file_handle, # Redirect stderr to log file
                preexec_fn=None, # No detachment for debugging. Use os.setsid for full detachment.
                cwd=project_root_dir # Set working directory for the subprocess
            )
        print(f"[Main] Image generation script started with PID: {image_generation_process.pid}")
        # The log_file_handle remains open by Popen and will be closed on parent exit.
    except FileNotFoundError:
        print(f"[Main] Error: Python executable or image generation script not found. Check path: {image_gen_script_path}")
        log_file_handle.close() 
    except Exception as e:
        print(f"[Main] Error starting image generation script subprocess: {e}")
        log_file_handle.close()

def MainExecution():
    global ListeningFlag
    TaskExecution = False
    ImageExecution = False
    ImageGenerationQuery = ""

    SetAssistantStatus("Listening ...")
    Query = takecommand()
    if not Query:
        SetAssistantStatus("Available ...")
        ListeningFlag = False
        SetMicrophoneStatus("False")
        return

    ListeningFlag = False
    SetMicrophoneStatus("False")

    ShowTextToScreen(f"{Username} : {Query}")
    SetAssistantStatus("Thinking ...")
    Decision = FirstLayerDMM(Query)

    print(f"\nDecision: {Decision}\n")

    G = any(i.startswith("general") for i in Decision)
    R = any(i.startswith("realtime") for i in Decision)

    Merged_query = " and ".join(
        [" ".join(i.split()[1:]) for i in Decision if i.startswith("general") or i.startswith("realtime")]
    )

    # Check for image generation request
    for queries in Decision:
        if "generate image" in queries:
            ImageGenerationQuery = queries.replace("generate image", "").strip()
            ImageExecution = True
            break # Only need to find one "generate image" decision

    # Handle Automation commands (open, close, play, etc.)
    for queries in Decision:
        if not TaskExecution: # Only execute one task for automation if multiple apply
            if any(queries.startswith(func) for func in Functions):
                try:
                    # Note: Automation itself might run async code.
                    # Ensure 'Automation' is compatible with threading or called on the main thread if needed.
                    run(Automation(Decision)) # Automation takes the whole decision list
                    TaskExecution = True
                except Exception as e:
                    print(f"[Main] Automation Error on '{queries}': {e}")
                
    # If an image generation request was detected
    if ImageExecution:
        # Construct the absolute path to the data file (relative to project root)
        image_data_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), r"Frontend\Files\ImageGeneration.data")
        os.makedirs(os.path.dirname(image_data_file_path), exist_ok=True) # Ensure directory exists
        
        try:
            # Write the command to the file. ImageGeneration.py (running in background) will pick it up.
            with open(image_data_file_path, "w") as file:
                file.write(f"{ImageGenerationQuery},True")
            print(f"[Main] Wrote '{ImageGenerationQuery},True' to {image_data_file_path}")
            speak(f"Generating image for {ImageGenerationQuery}.")
        except Exception as e:
            print(f"[Main] Error writing to ImageGeneration.data: {e}")
            speak("Sorry, I couldn't set up image generation.")
        
        SetAssistantStatus("Available ...")
        return # Exit MainExecution after handling image request

    # Handle combined General and Realtime search, or just Realtime
    if G and R or R:
        try:
            SetAssistantStatus("Searching ...")
            Answer = RealtimeSearchEngine(QueryModifier(Merged_query))
            ShowTextToScreen(f"{Assistantname} : {Answer}")
            SetAssistantStatus("Answering ...")
            speak(Answer)
        except Exception as e:
            print("[Main] RealtimeSearch Error:", e)
            speak("Sorry, I had trouble with the search.")
        SetAssistantStatus("Available ...")
        return

    # Handle individual General or Realtime commands, or exit
    for Queries in Decision: # Loop through decisions again for general/realtime/exit if not handled above
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
            # Terminate the image generation child process gracefully
            if image_generation_process and image_generation_process.poll() is None:
                print("[Main] Terminating image generation process...")
                image_generation_process.terminate() 
                try:
                    image_generation_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print("[Main] Image generation process did not terminate gracefully, killing it.")
                    image_generation_process.kill()
            # Close the log file handle for the subprocess
            # This is crucial to ensure all buffered output is written before exit.
            # Using globals() to access the handle if it was opened
            for f_obj in sys.stdout, sys.stderr: # Also ensure stdout/stderr are flushed
                if f_obj is not None:
                    f_obj.flush()
            if 'log_file_handle' in globals() and not log_file_handle.closed:
                log_file_handle.close()
            os._exit(0)

# --- This is the backend logic loop. ---
def FirstThread():
    InitialExecution() # This launches the image generation subprocess
    
    while True:
        if ListeningFlag:
            MainExecution()
        else:
            sleep(0.1)

# --- This function is the controller for the microphone. ---
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
    # The GUI must run on the main thread.
    # The backend logic will run in a separate, non-blocking "daemon" thread.

    # 1. Create and start the backend thread.
    backend_thread = threading.Thread(target=FirstThread, daemon=True)
    backend_thread.start()

    # 2. Run the GUI on the main thread, passing it the function to call when the mic is clicked.
    GraphicalUserInterface(toggle_callback=ToggleListening)