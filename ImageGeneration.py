import asyncio
from random import randint
from PIL import Image
import requests
from dotenv import load_dotenv, get_key
from time import sleep
import os
import sys # For sys.exit() and general process control

# --- IMPORTANT PATH SETUP ---
# When this script is run as a subprocess with cwd=project_root_dir,
# os.getcwd() will return the project root.
# So, all paths must be relative to that project root.

# Load environment variables from .env file.
# By default, load_dotenv() looks in the current working directory,
# which we've ensured is the project root in main.py.
load_dotenv()

# Define base directories relative to the project root (which is the cwd of this script)
DATA_FOLDER = "Data"
FRONTEND_FILES_FOLDER = os.path.join("Frontend", "Files")
IMAGE_GENERATION_DATA_FILE = os.path.join(FRONTEND_FILES_FOLDER, "ImageGeneration.data")

# Function to open and display images based on a given prompt
def open_images(prompt):
    # Path to the Data folder, now correctly relative to the project root
    folder_path = DATA_FOLDER
    
    # Sanitize prompt for filename to remove problematic characters
    # This creates a more robust filename.
    prompt_filename = "".join(c if c.isalnum() else "_" for c in prompt).replace("__", "_").strip("_")
    if not prompt_filename: # Fallback if prompt becomes empty after sanitization
        prompt_filename = "generated_image"

    # Generate the filenames for the images
    files = [f"{prompt_filename}_{i}.jpg" for i in range(1, 5)]

    print(f"\n[ImageGen] Attempting to open images for prompt: '{prompt}' (PID: {os.getpid()})")
    for jpg_file in files:
        image_path = os.path.join(folder_path, jpg_file)

        try:
            img = Image.open(image_path)
            print(f"[ImageGen] Opening image: {image_path}")
            img.show()
            sleep(1) # Pause for 1 second before showing the next image

        except FileNotFoundError:
            print(f"[ImageGen] Error: Image not found at {image_path}. Was it generated correctly?")
        except IOError:
            print(f"[ImageGen] Error: Unable to open {image_path}. It might be corrupted or not a valid image file.")
        except Exception as e:
            print(f"[ImageGen] An unexpected error occurred while opening {image_path}: {e}")

# API details for the Hugging Face Stable Diffusion model
API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
hf_api_key = get_key('.env', 'HuggingFaceAPIKey') # Looks for .env in current working directory (project root)

if not hf_api_key:
    print("[ImageGen] CRITICAL ERROR: HuggingFaceAPIKey not found in .env file.")
    print("[ImageGen] Please ensure .env file is in the project root and contains: HuggingFaceAPIKey=\"hf_YOUR_ACTUAL_API_KEY_HERE\"")
    # In a detached background process, it's often better to log and potentially exit
    # if a critical dependency like API key is missing. For now, we'll use a dummy
    # key, but subsequent API calls will fail.
    # sys.exit(1) # Uncomment to exit if API key is missing.
    hf_api_key = "dummy_key_if_missing" # Use a dummy key to prevent header errors, but API calls will fail
headers = {"Authorization": f"Bearer {hf_api_key}"}

# Async function to send a query to the Hugging Face API
async def query(payload ):
    if hf_api_key == "dummy_key_if_missing":
        print("[ImageGen] Skipping API call: API Key is missing/invalid.")
        return b""
    try:
        response = await asyncio.to_thread(requests.post, API_URL, headers=headers, json=payload)

        if response.status_code != 200:
            print(f"[ImageGen] API Error: {response.status_code} - {response.text}")
            return b""
        
        content_type = response.headers.get('Content-Type', '')
        if 'image' not in content_type:
            print(f"[ImageGen] Warning: API response content type is not an image. Content-Type: {content_type}")
            print(f"[ImageGen] Response content (first 200 chars): {response.text[:200]}...")
            return b""

        return response.content
    except requests.exceptions.RequestException as e:
        print(f"[ImageGen] Network or API request error: {e}")
        return b""
    except Exception as e:
        print(f"[ImageGen] An unexpected error occurred during API query: {e}")
        return b""

# Async function to generate images based on the given prompt
async def generate_images(prompt: str):
    tasks = []
    prompt_filename = "".join(c if c.isalnum() else "_" for c in prompt).replace("__", "_").strip("_")
    if not prompt_filename:
        prompt_filename = "generated_image"

    print(f"[ImageGen] Starting image generation for prompt: '{prompt}'")
    for i in range(4):
        payload = {
            "inputs": f"{prompt}, quality=4K, sharpness=maximum, Ultra High details, high resolution, seed= {randint(0, 1000000)}",
        }
        task = asyncio.create_task(query(payload))
        tasks.append(task)
        await asyncio.sleep(0.1) 

    image_bytes_list = await asyncio.gather(*tasks)
    
    # Path to the Data directory, relative to project root
    data_dir_path = DATA_FOLDER
    os.makedirs(data_dir_path, exist_ok=True) # Ensure the Data directory exists

    generated_count = 0
    for i, image_bytes in enumerate(image_bytes_list):
        if image_bytes:
            file_path = os.path.join(data_dir_path, f"{prompt_filename}_{i+1}.jpg")
            try:
                with open(file_path, "wb") as f:
                    f.write(image_bytes)
                print(f"[ImageGen] Saved image: {file_path}")
                generated_count += 1
            except IOError:
                print(f"[ImageGen] Error: Could not write image file to {file_path}. Check directory permissions.")
            except Exception as e:
                print(f"[ImageGen] An unexpected error occurred while saving image {file_path}: {e}")
        else:
            print(f"[ImageGen] Skipping saving image {i+1} due to empty/invalid response from API.")
    
    if generated_count > 0:
        print(f"[ImageGen] Successfully generated and saved {generated_count} images.")
        return True
    else:
        print("[ImageGen] No images were successfully generated or saved.")
        return False

# Wrapper function to generate and open images
def GenerateImages(prompt: str):
    print(f"[ImageGen] Initiating image generation and display for: '{prompt}'")
    generation_successful = asyncio.run(generate_images(prompt)) 
    if generation_successful:
        open_images(prompt)
    else:
        print("[ImageGen] Image generation failed, not attempting to open images.")

# --- Main loop to check for image generation requests ---
# Path to ImageGeneration.data, correctly relative to project root
FRONTEND_DATA_FILE_PATH = IMAGE_GENERATION_DATA_FILE

# Ensure Frontend\Files directory exists for the data file
os.makedirs(os.path.dirname(FRONTEND_DATA_FILE_PATH), exist_ok=True)

# Initialize the data file if it doesn't exist or is empty
if not os.path.exists(FRONTEND_DATA_FILE_PATH) or os.stat(FRONTEND_DATA_FILE_PATH).st_size == 0:
    print(f"[ImageGen] Initializing {FRONTEND_DATA_FILE_PATH} with default content 'False, False'.")
    try:
        with open(FRONTEND_DATA_FILE_PATH, "w") as f:
            f.write("False, False")
    except Exception as e:
        print(f"[ImageGen] Error initializing data file: {e}")

print(f"[ImageGen] Monitoring '{FRONTEND_DATA_FILE_PATH}' for image generation requests...")

# Add a marker to show this script started
print(f"[ImageGen] ImageGeneration.py process started. PID: {os.getpid()}")

while True:
    try:
        # Read the status and prompt from the data file
        with open(FRONTEND_DATA_FILE_PATH, "r") as f:
            data_content: str = f.read().strip()

        if not data_content:
            print(f"[ImageGen] Warning: {FRONTEND_DATA_FILE_PATH} is empty. Re-initializing.")
            with open(FRONTEND_DATA_FILE_PATH, "w") as f:
                f.write("False, False")
            sleep(1)
            continue

        try:
            prompt, status = data_content.split(",", 1)
            prompt = prompt.strip()
            status = status.strip()
        except ValueError:
            print(f"[ImageGen] Error: Invalid format in {FRONTEND_DATA_FILE_PATH}. Expected 'Prompt,Status'. Content: '{data_content}'")
            print("[ImageGen] Resetting file to 'False, False' and waiting...")
            with open(FRONTEND_DATA_FILE_PATH, "w") as f:
                f.write("False, False")
            sleep(5)
            continue

        if status.lower() == "true":
            print(f"\n[ImageGen] --- Detected request to generate images for prompt: '{prompt}' ---")
            GenerateImages(prompt=prompt)
            
            print(f"[ImageGen] Resetting status in {FRONTEND_DATA_FILE_PATH} to 'False, False'.")
            with open(FRONTEND_DATA_FILE_PATH, "w") as f:
                f.write("False, False")
            
            sleep(0.5) # Small pause after processing a request
            continue # Continue loop to check for next request

        else:
            sleep(1) # Wait for 1 second before checking again
    
    except FileNotFoundError:
        print(f"[ImageGen] Error: The data file '{FRONTEND_DATA_FILE_PATH}' was not found.")
        print(f"[ImageGen] Please ensure the 'Frontend\\Files' directory exists relative to the project root.")
        os.makedirs(os.path.dirname(FRONTEND_DATA_FILE_PATH), exist_ok=True)
        with open(FRONTEND_DATA_FILE_PATH, "w") as f:
            f.write("False, False")
        sleep(5)
    except Exception as e:
        print(f"[ImageGen] An unexpected error occurred in the main loop: {e}")
        print("[ImageGen] Waiting for 5 seconds before retrying...")
        sleep(5)