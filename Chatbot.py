import os
import json  # Needed for JSONDecodeError
from json import load, dump
import datetime
from dotenv import dotenv_values
from groq import Groq

# Create Data folder if it doesn't exist
os.makedirs("Data", exist_ok=True)

# Load environment variables from .env file
env_vars = dotenv_values(".env")

# Retrieve specific environment variables
Username = env_vars.get("Username")
Assistantname = env_vars.get("Assistantname")
GroqAPIKey = env_vars.get("GroqAPIKey")

# Initialize the Groq client
client = Groq(api_key=GroqAPIKey)

# System message for the AI
System = f"""Hello, I am {Username}, You are a very accurate and advanced AI chatbot named {Assistantname} which also has real-time up-to-date information from the internet.
*** Do not tell time until I ask, do not talk too much, just answer the question.***
*** Reply in only English, even if the question is in Hindi, reply in English.***
*** Do not provide notes in the output, just answer the question and never mention your training data. ***
"""

SystemChatBot = [
    {"role": "system", "content": System}
]

# Load chat history if available
try:
    with open(r"Data\ChatLog.json", "r") as f:
        messages = load(f)
except (FileNotFoundError, json.decoder.JSONDecodeError):
    with open(r"Data\ChatLog.json", "w") as f:
        dump([], f)
    messages = []

# Function to return real-time information
def RealtimeInformation():
    now = datetime.datetime.now()
    return (
        f"Please use this real-time information if needed, \n"
        f"Day: {now.strftime('%A')}\n"
        f"Date: {now.strftime('%d')}\n"
        f"Month: {now.strftime('%B')}\n"
        f"Year: {now.strftime('%Y')}\n"
        f"Time: {now.strftime('%H')} hours: {now.strftime('%M')} minutes: {now.strftime('%S')} seconds.\n"
    )

# Clean up chatbot's answer
def AnswerModifier(Answer):
    lines = Answer.split('\n')
    non_empty_lines = [line.strip() for line in lines if line.strip()]
    return '\n'.join(non_empty_lines)

# Main chatbot function
def ChatBot(Query, retry=False):
    try:
        with open(r"Data\ChatLog.json", "r") as fr:
            messages = load(fr)

        messages.append({"role": "user", "content": Query})

        completion = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=SystemChatBot + [{"role": "system", "content": RealtimeInformation()}] + messages,
            max_tokens=1024,
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

        with open(r"Data\ChatLog.json", "w") as f:
            dump(messages, f, indent=4)

        return AnswerModifier(Answer)

    except Exception as e:
        print(f"Error: {e}")
        if not retry:
            with open(r"Data\ChatLog.json", "w") as f:
                dump([], f, indent=4)
            return ChatBot(Query, retry=True)
        else:
            return "An error occurred. Please try again."

# Run in a loop
if __name__ == "__main__":
    while True:
        user_input = input("Enter your question: ")
        if user_input.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break
        print(ChatBot(user_input))
