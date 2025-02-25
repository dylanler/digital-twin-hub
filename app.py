import gradio as gr
import os
import time
from pathlib import Path
from conversation_api_input_output import handle_conversation  # Import the conversation handler
import requests
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation, ConversationConfig
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface

# load_dotenv()

UPLOAD_DIR = "avatar_videos"
Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

current_conversation = None
is_conversation_active = False

# Add a global variable to store the cloned agent ID
cloned_voice_id = "yk6z5D05U7ccflgendsD"
voice_name = "Timmy"
AGENT_ID = "XOpQx4GrwSHb7DHolt46"
def save_video(video_path):
    if video_path is None:
        return None, None
    timestamp = int(time.time())
    new_filename = f"avatar_video_{timestamp}.mp4"
    save_path = os.path.join(UPLOAD_DIR, new_filename)
    os.system(f'cp "{video_path}" "{save_path}"')
    return save_path, get_video_list()

def get_video_list():
    videos = [f for f in os.listdir(UPLOAD_DIR) if f.endswith('.mp4')]
    videos.sort(reverse=True)
    return videos if videos else []

def load_video(video_name):
    if video_name is None:
        return None
    return os.path.join(UPLOAD_DIR, video_name)

def clone_voice(audio_file_path):
    global cloned_voice_id, voice_name
    api_url = "https://api.elevenlabs.io/v1/voices/add"
    headers = {
        "xi-api-key": os.environ.get("ELEVENLABS_API_KEY"),
    }
    with open(audio_file_path, 'rb') as audio_file:
        files = {'files': audio_file}
        data = {'name': voice_name}
        response = requests.post(api_url, headers=headers, files=files, data=data)
    
    if response.status_code == 200:
        cloned_voice_id = response.json().get("voice_id")  # Save the cloned agent ID
        print(f"Cloned agent ID: {cloned_voice_id}")
    else:
        print(f"Error cloning voice: {response.text}")  # Print the error instead of returning it

# def resume_video():
#     video_output.update(autoplay=True)

# def pause_video():
#     video_output.update(autoplay=False)

def start_conversation(agent_id, config=None):
    # pause_video()
    global current_conversation, is_conversation_active
    api_key = os.getenv("ELEVENLABS_API_KEY")
    client = ElevenLabs(api_key=api_key)
    current_conversation = Conversation(
        config=config,
        client=client,
        agent_id=agent_id,
        requires_auth=bool(api_key),
        audio_interface=DefaultAudioInterface(),
        callback_agent_response=lambda response: [
            print(f"Agent: {response}"),
            # resume_video()
        ],
        callback_user_transcript=lambda transcript: [
            print(f"User: {transcript}"),
            # pause_video()
        ],
    )
    current_conversation.start_session()
    conversation_id = current_conversation.wait_for_session_end()
    print(f"Conversation ID: {conversation_id}")
    is_conversation_active = False
    return current_conversation


def toggle_conversation(agent_id=AGENT_ID):
    global is_conversation_active, cloned_voice_id, voice_name
    if cloned_voice_id is not None:
        conversation_override = {
        "agent": {
            "prompt": {
                "prompt": f"You are Timmy, a laid-back skater boy who keeps things chill and simple. You speak in a casual, relaxed way using shorter sentences and skater lingo when appropriate. You're super helpful but never too formal - just a cool dude who's got people's backs. You prefer being concise but friendly."
            },
            "first_message": f"Yo, what's up? I'm {voice_name}, just chillin' here to help you out.",
            "language": "en" # Optional: override the language.
        },
        "tts": {
                "voice_id": cloned_voice_id # Optional: override the voice.
            }
        }

        config = ConversationConfig(
            conversation_config_override=conversation_override
        )
    else:
        config = None

    if is_conversation_active:
        if current_conversation:
            current_conversation.end_session()
            print("Conversation ended.")
            is_conversation_active = False
            return "Start Conversation"
    else:
        if isinstance(agent_id, str):
            start_conversation(agent_id, config)
            is_conversation_active = True
            return "End Conversation"
        else:
            return "Error initializing conversation"

with gr.Blocks() as app:
    with gr.Row():
        video_input = gr.Video(label="Upload Video")
        video_output = gr.Video(label="Current Video", autoplay=True, loop=True)

    with gr.Row():
        video_dropdown = gr.Dropdown(
            label="Previously Uploaded Videos",
            choices=get_video_list(),
            type="value",
            interactive=True,
            allow_custom_value=True
        )
        load_btn = gr.Button("Load Video")
    audio_upload = gr.Audio(
        label="Upload Audio Clip for Cloning",
        type="filepath"
    )
    clone_button = gr.Button("Clone")
    toggle_conversation_button = gr.Button("Start Conversation")
    
    video_input.upload(
        fn=save_video,
        inputs=[video_input],
        outputs=[video_output, video_dropdown]
    )
    load_btn.click(
        fn=load_video,
        inputs=[video_dropdown],
        outputs=[video_output]
    )
    clone_button.click(
        fn=lambda audio_file: clone_voice(audio_file),
        inputs=[audio_upload],
        outputs=[]
    )
    toggle_conversation_button.click(
        fn=lambda: toggle_conversation(agent_id=AGENT_ID),
        inputs=[],
        outputs=[toggle_conversation_button]
    )

if __name__ == "__main__":
    app.launch()
