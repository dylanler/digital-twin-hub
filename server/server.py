import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))  # Add parent directory to path

from fastapi import FastAPI, File, UploadFile, HTTPException, Body, WebSocket, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import time
from pathlib import Path
import requests
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation, ConversationConfig, ClientTools
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import asyncio
import json
from fal_lora_inference import FalLoraInference
from fal_video_gen import FalVideoGenerator
import fal_client

# Load environment variables from .env file
load_dotenv()

# Constants
KEYWORD = "TIMMYLORA"
DEFAULT_OUTPUT_PATH = "output.mp4"
global video_url
video_url = None 
# Debug print to verify API key is loaded
api_key = os.environ.get("ELEVEN_LABS_API_KEY")
if api_key:
    print("ElevenLabs API key loaded successfully")
else:
    print("Warning: ElevenLabs API key not found in environment variables")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080"],  # Allow both common frontend ports
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

UPLOAD_DIR = "avatar_videos"
Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

# Global variables
DEFAULT_VOICE_ID = "yk6z5D05U7ccflgendsD"
AGENT_ID = "XOpQx4GrwSHb7DHolt46"
voice_name = "Timmy"
current_conversation = None
is_conversation_active = False
is_agent_listening = False
is_agent_speaking = False


def update_listening_state(state: bool):
    global is_agent_listening
    is_agent_listening = state
    print(f"Agent listening: {state}")

def update_speaking_state(state: bool):
    global is_agent_speaking
    is_agent_speaking = state
    print(f"Agent speaking: {state}")

class WebSocketAudioInterface(DefaultAudioInterface):
    def __init__(self, websocket: WebSocket):
        super().__init__()
        self.websocket = websocket
        
    async def stream_audio_chunks(self, audio_stream):
        async for chunk in audio_stream:
            await self.websocket.send_bytes(chunk)
            
    async def get_audio_input(self):
        try:
            data = await self.websocket.receive_bytes()
            return data
        except Exception as e:
            print(f"Error receiving audio: {e}")
            return None

@app.post("/upload-video/")
async def upload_video(video: UploadFile = File(...)):
    if video is None:
        raise HTTPException(status_code=400, detail="No video uploaded")
    
    timestamp = int(time.time())
    new_filename = f"avatar_video_{timestamp}.mp4"
    save_path = os.path.join(UPLOAD_DIR, new_filename)
    
    with open(save_path, "wb") as buffer:
        buffer.write(await video.read())
    
    return {"filename": new_filename}

@app.get("/videos/")
async def get_video_list():
    videos = [f for f in os.listdir(UPLOAD_DIR) if f.endswith('.mp4')]
    videos.sort(reverse=True)
    return {"videos": videos}

@app.post("/avatar/clone-voice")
async def clone_voice(audio_file: UploadFile = File(...)):
    global cloned_voice_id, voice_name
    api_url = "https://api.elevenlabs.io/v1/voices/add"
    headers = {
        "xi-api-key": os.environ.get("ELEVEN_LABS_API_KEY"),
    }
    
    try:
        # Read the file content
        file_content = await audio_file.read()
        
        # Make the API request
        files = {'files': (audio_file.filename, file_content, audio_file.content_type)}
        data = {'name': voice_name}
        response = requests.post(api_url, headers=headers, files=files, data=data)
        
        if response.status_code == 200:
            cloned_voice_id = response.json().get("voice_id")
            return {"voice_id": cloned_voice_id}
        else:
            print(f"ElevenLabs API Error: {response.text}")  # Add logging
            raise HTTPException(status_code=response.status_code, detail=response.text)
            
    except Exception as e:
        print(f"Error in clone_voice: {str(e)}")  # Add logging
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/conversation")
async def websocket_endpoint(websocket: WebSocket):
    global current_conversation, is_conversation_active
    await websocket.accept()
    
    try:
        while True:
            if not is_conversation_active or not current_conversation:
                await asyncio.sleep(0.1)
                continue
                
            audio_data = await websocket.receive_bytes()
            # if current_conversation and audio_data:
            #     # Ensure the method name is correct
            #     await current_conversation.handle_audio(audio_data)  # Change to the correct method name
                           
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()

@app.post("/toggle-conversation/")
async def toggle_conversation(agent_id: str = Body(...), voice_id: str = Body(DEFAULT_VOICE_ID)):
    global is_conversation_active, current_conversation, voice_name
    
    if is_conversation_active:
        if current_conversation:
            current_conversation.end_session()
            is_conversation_active = False
            return {"message": "Conversation ended.", "is_active": False}
    else:
        conversation_override = {
            "agent": {
                "prompt": {
                    "prompt": f"You are Timmy, a laid-back skater boy who keeps things chill and simple. You speak in a casual, relaxed way using shorter sentences and skater lingo when appropriate. You're super helpful but never too formal - just a cool dude who's got people's backs. You prefer being concise but friendly."
                },
                "first_message": f"Yo, what's up? I'm {voice_name}, just chillin' here to help you out.",
                "language": "en"
            },
            "tts": {
                "voice_id": voice_id
            }
        }
        config = ConversationConfig(conversation_config_override=conversation_override)

        api_key = os.getenv("ELEVEN_LABS_API_KEY")
        client = ElevenLabs(api_key=api_key)
        
        current_conversation = Conversation(
            config=config,
            client=client,
            agent_id=agent_id,
            requires_auth=bool(api_key),
            audio_interface=DefaultAudioInterface(),
            callback_agent_response=lambda response: (update_speaking_state(True), print(f"Agent: {response}"), update_speaking_state(False)),
            callback_user_transcript=lambda transcript: (update_listening_state(True), print(f"User: {transcript}"), update_listening_state(False))
        )
        
        current_conversation.start_session()
        is_conversation_active = True
        return {"message": "Conversation started.", "is_active": True}
    
    return {"message": "Error initializing conversation.", "is_active": False}

@app.get("/")
async def get_index():
    return HTMLResponse(open("index.html").read())

@app.get("/load-avatar-video")
async def load_avatar_video():
    if is_agent_speaking:
        video_url = "https://v3.fal.media/files/penguin/K8y_1daV8OOm2jMdGfeEZ_output.mp4"        
    else:
        video_url = "https://v3.fal.media/files/penguin/K8y_1daV8OOm2jMdGfeEZ_output.mp4"
    # else:
    #     raise HTTPException(status_code=400, detail="Invalid speaking states")
    # generate the video
    # if video_url:
    #     return {"videoUrl": video_url}
    # else:
    #     raise HTTPException(status_code=400, detail="Video URL not found")
    return {"videoUrl": video_url}

@app.get("/agent/state")
async def get_agent_state():
    return {"listening": not is_conversation_active, "speaking": is_conversation_active}

async def generate_avatar_video():
    global video_url

    # first generate a static image
    inference = FalLoraInference()
    prompt = f"{KEYWORD} sitting in a cafe talking while looking at the center of the frame"
    lora_path = "https://v3.fal.media/files/kangaroo/ZMhu8LIb17rNmew6wXYjz_pytorch_lora_weights.safetensors"
    image_path = "talking_image.jpg"

    result = inference.run_inference(prompt, lora_path, image_path)
    if result:
        print("Image generation successful!")
        print(f"Seed: {result['seed']}")
        print(f"Inference time: {result['timings']['inference']} seconds")
        print(f"NSFW content detected: {result['has_nsfw_concepts'][0]}")
    else:
        print("Image generation failed.")

    # then generate a video from the image
    # generator = FalVideoGenerator()
    arguments = dict(
        prompt="man sitting in a cafe talking while looking at the center of the frame with hand movements",
        image_path=image_path,
        aspect_ratio="16:9",
        resolution="540p",
        duration="5s",
        loop=True
    )

    # print(result)
    def on_queue_update(update):
        if isinstance(update, fal_client.InProgress):
            for log in update.logs:
                print(log["message"])

    result = fal_client.subscribe(
        "fal-ai/luma-dream-machine/ray-2/image-to-video",
        arguments=arguments,
        with_logs=True,
        on_queue_update=on_queue_update,
    )
    print(f"Generation completed. Result: {result}")

    # Get video URL from the completed 
    video_url = result.get('video', {}).get('url')

# @app.on_event("startup")
# async def startup_event():
#     await generate_avatar_video()

# Serve static files (React build)
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
