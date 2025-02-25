import os
import json
import time
from datetime import datetime
from google import genai
import requests
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip, CompositeVideoClip
from img_bucket import GCPImageUploader
import cv2
from elevenlabs import ElevenLabs
import argparse
import ast
import eleven_labs_tts
from eleven_labs_tts import generate_speech
import shutil
from fal_video_gen import FalVideoGenerator
from luma_video_gen import LumaVideoGenerator
import anthropic
# Load environment variables
from dotenv import load_dotenv
load_dotenv()
from ltx_video_generation import generate_ltx_video

# Initialize clients
gemini_api_key = os.getenv("GEMINI_API_KEY")
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

if not gemini_api_key:
    print("Warning: GEMINI_API_KEY not found in environment variables")
else:
    gemini_client = genai.Client(api_key=gemini_api_key)

if not anthropic_api_key:
    print("Warning: ANTHROPIC_API_KEY not found in environment variables")

# Add video duration configuration
LUMA_VIDEO_GENERATION_DURATION_OPTIONS = [5, 9, 14, 18]  # Duration in seconds

# Get current timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# Define video directory path (but don't create it yet)
video_dir = f"generated_videos/video_{timestamp}"

def validate_model_choice(model_choice):
    """Validate that the chosen model's API key is available"""
    if model_choice == "gemini" and not gemini_api_key:
        raise ValueError("GEMINI_API_KEY environment variable is required for using Gemini model")
    elif model_choice == "claude" and not anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required for using Claude model")

def generate_physical_environments(num_scenes, script, max_environments=3, model="gemini", custom_prompt=None, custom_environments=None):
    # If custom environments are provided, use them directly
    if custom_environments is not None:
        print("Using provided custom environment descriptions")
        json_path = os.path.join(video_dir, f'scene_physical_environment_{timestamp}.json')
        with open(json_path, 'w') as f:
            json.dump(custom_environments, f, indent=2)
        return custom_environments, json_path

    print(f"There are {num_scenes} scenes in the script.")
    
    # Use custom prompt if provided, otherwise use default
    base_prompt = f"""
    Create a JSON array of a bunch of detailed physical environment descriptions based on the movie script.
    Each environment should be detailed and include:
    - Setting details
    - Lighting conditions
    - Weather and atmospheric conditions
    - Time of day
    - Key objects and elements in the scene
    - Maximum number of physical environments is {max_environments}
    
    Some scenes will reuse the same physical environment. Across multiple scenes, the physical environment should maintain the same physical environment across two or more scenes.
    Focus on creating a cohesive visual narrative with the physical environment descriptions.
    """
    
    prompt = custom_prompt if custom_prompt else base_prompt
    prompt += """
    Return: array of objects with format:
    {
        "scene_physical_environment": "detailed string description"
    }
    """
    
    try:
        if model == "gemini":
            response = gemini_client.models.generate_content(
                model="gemini-2.0-flash-001",
                contents=[script, prompt],
                config={
                    'response_mime_type': 'application/json',
                    'temperature': 0.7,
                    'top_p': 0.8,
                    'top_k': 40,
                    'response_schema': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'scene_physical_environment': {'type': 'string'}
                            },
                            'required': ['scene_physical_environment']
                        }
                    }
                }
            )
            environments = response.parsed
        
        elif model == "claude":
            client = anthropic.Anthropic(api_key=anthropic_api_key)
            
            system_prompt = """You are an expert at describing physical environments for video scenes."""

            claude_environments_format = """
            {
                "environments": [
                    {
                        "scene_physical_environment": "detailed string description"
                    },
                    ...
                ]
            }
            """
            
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=8192,
                temperature=0.7,
                system=system_prompt,
                messages=[{"role": "user", "content": f"""
                {script}\n\n{prompt}
                Output JSON format like this:
                {claude_environments_format}
                """}]
            )
            
            try:
                response_text = response.content[0].text
                environments = ast.literal_eval(response_text)
                environments = environments["environments"]
                print(f"There are {len(environments)} scene physical environments in the script.")
            except Exception as e:
                print("Raw response content:", response_text)
                raise RuntimeError(f"Failed to parse Claude's response: {e}")
        
        else:
            raise ValueError(f"Unsupported model: {model}")
        
        os.makedirs(video_dir, exist_ok=True)
        json_path = os.path.join(video_dir, f'scene_physical_environment_{timestamp}.json')
        with open(json_path, 'w') as f:
            json.dump(environments, f, indent=2)
        
        return environments, json_path
        
    except Exception as e:
        raise e

def generate_metadata_without_environment(num_scenes, script, model="gemini", video_engine="luma", lora_in_first_frame_mode=False, trigger_word=None):
    # Validate model choice and API keys
    validate_model_choice(model)
    
    # Add trigger word validation
    if lora_in_first_frame_mode and not trigger_word:
        raise ValueError("trigger_word must be provided when lora_in_first_frame_mode is enabled")

    prompt = f"""Create a JSON array of {num_scenes} detailed scene descriptions based on the movie script. Each scene should include:
    1. A descriptive scene name that captures the essence of the moment
    2. Movement descriptions including:
       - Character movements and actions
       - Character appereances should be described in detail along with ethnicity, gender, age, clothing, style, and any other relevant details
       - Character appearances should be consistent with the previous scene's character appearances
       - Object interactions and dynamics
       - Flow of action
    3. Emotional components including:
       - Scene mood and atmosphere
       - Emotional undertones
       - Visual emotional cues
    4. Camera movement specifications including:
       - Shot types (wide, medium, close-up)
       - Camera angles
       - Movement patterns (pan, tilt, dolly, etc.)
       - Camera movement should be smooth and fluid and not jarring
       - If a scene does not require camera movement, enter camera movement as "static"
    5. Sound effects focusing on:
       - Environmental sounds
       - Action-related sounds
       - Ambient atmosphere
       - Musical mood suggestions
       - Keep it below 30 words
    6. Take into account the previous scene's movement description, emotions, camera movement, and sound effects prompt when creating the next scene's movement description, emotions, camera movement, and sound effects prompt.
    7. The first scene should have no previous scene movement description, emotions, camera movement, and sound effects prompt, enter string "none".
    8. Scene duration must be selected from these options: {[5, 9, 14, 18] if video_engine == "luma" else "[5, 10]"} (in seconds)
    9. The first frame prompt should be a detailed description of the first frame of the scene."""

    if lora_in_first_frame_mode:
        prompt += f'\n10. For the first frame prompt, there is a LoRA trigger word called "{trigger_word}" which represents the character of the video, include the character as "{trigger_word}" when writing the first frame prompt.'
        prompt += f'\n11. For the first frame prompt, include the character as "{trigger_word}" when describing the character doing something. For example:'
        prompt += f'\n    - Instead of "A man is walking on the beach", write "{trigger_word} is walking on the beach"'
        prompt += f'\n    - Instead of "She sits under a palm tree", write "{trigger_word} sits under a palm tree"'
        prompt += f'\n12. Remember that the LoRA trigger word is "{trigger_word}" and should only be in first_frame_prompt and not the other keys of the json object.'
        prompt += f'\n13. The trigger word "{trigger_word}" should only appear once in the first_frame_prompt.'
        prompt += f'\n14. The first frame prompt should only include a single person - {trigger_word} - and no other people in the scene.'
    prompt += """

    Focus on creating a cohesive visual narrative without any dialogue.
    
    Return: array of objects with format:
    {
        "scene_number": integer, # must be sequential starting from 1
        "scene_name": "string value",
        "previous_scene_movement_description": "string value",
        "scene_movement_description": "string value",
        "previous_scene_emotions": "string value",
        "scene_emotions": "string value",
        "previous_scene_camera_movement": "string value",
        "scene_camera_movement": "string value",
        "previous_scene_duration": "integer value", 
        "scene_duration": "integer value", 
        "previous_scene_sound_effects_prompt": "string value",
        "sound_effects_prompt": "string value",
        "first_frame_prompt": "string value"
    }
    """
    
    try:
        if model == "gemini":
            response = gemini_client.models.generate_content(
                model="gemini-2.0-flash-001",
                contents=[script, prompt],
                config={
                    'response_mime_type': 'application/json',
                    'temperature': 0.7,
                    'top_p': 0.8,
                    'top_k': 40,
                    'response_schema': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'scene_number': {'type': 'integer'},
                                'scene_name': {'type': 'string'},
                                'scene_movement_description': {'type': 'string'},
                                'scene_emotions': {'type': 'string'},
                                'scene_camera_movement': {'type': 'string'},
                                'scene_duration': {'type': 'integer'},
                                'sound_effects_prompt': {'type': 'string'},
                                'first_frame_prompt': {'type': 'string'}
                            },
                            'required': ['scene_number', 'scene_name', 'scene_movement_description', 
                                       'scene_emotions', 'scene_camera_movement', 'scene_duration', 'sound_effects_prompt', 'first_frame_prompt']
                        }
                    }
                }
            )
            metadata = response.parsed
        
        elif model == "claude":
            client = anthropic.Anthropic(api_key=anthropic_api_key)
            
            system_prompt = """You are an expert at creating detailed scene descriptions for videos. 
            You are also an expert at creating sound effects prompts for videos.
            You will output all number of scenes needed to tell the story effectively.
            """

            claude_metadata_no_env_format = """
            {
                "scenes": [
                    {
                        "scene_number": "integer value", # must be sequential starting from 1
                        "scene_name": "string value",
                        "previous_scene_movement_description": "string value",
                        "scene_movement_description": "string value",
                        "previous_scene_emotions": "string value",
                        "scene_emotions": "string value",
                        "previous_scene_camera_movement": "string value",
                        "scene_camera_movement": "string value",
                        "previous_scene_duration": "integer value",
                        "scene_duration": "integer value",
                        "previous_scene_sound_effects_prompt": "string value",
                        "sound_effects_prompt": "string value",
                        "first_frame_prompt": "string value"
                    },
                    ...
                ]
            }
            """
            
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=8192,
                temperature=0.7,
                system=system_prompt,
                messages=[{"role": "user", "content": f"""
                {script}\n\n{prompt}
                Output JSON format like this:
                {claude_metadata_no_env_format}
                Output all scenes needed to tell the story effectively. No explanation is needed.
                """}]
            )
            
            try:
                response_text = response.content[0].text
                metadata = ast.literal_eval(response_text)
                metadata = metadata["scenes"]
            except Exception as e:
                print("Raw response content:", response_text)
                raise RuntimeError(f"Failed to parse Claude's response: {e}")
        
        else:
            raise ValueError(f"Unsupported model: {model}")

        # If lora_in_first_frame_mode is enabled, ensure trigger word is in the first_frame_prompt, or else add it to the first_frame_prompt
        if lora_in_first_frame_mode:
            for scene in metadata:
                if trigger_word not in scene['first_frame_prompt']:
                    scene['first_frame_prompt'] = f"{trigger_word}, {scene['first_frame_prompt']}"
        
        json_path = os.path.join(video_dir, f'scene_metadata_no_env_{timestamp}.json')
        with open(json_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return metadata, json_path
        
    except Exception as e:
        raise e

def combine_metadata_with_environment(num_scenes, script, metadata_path, environments_path, model="gemini"):
    # Load both JSON files
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    with open(environments_path, 'r') as f:
        environments = json.load(f)
    
    prompt = f"""
    Given a list of {num_scenes} scene metadata and a list of physical environments, select the most appropriate physical environment 
    for each scene to ensure scene continuity in the physical environment of the video.
    
    Return: array of complete scene descriptions, each containing all metadata fields plus the selected physical environment.
    """
    
    try:
        if model == "gemini":
            response = gemini_client.models.generate_content(
                model="gemini-2.0-flash-001",
                contents=[script, json.dumps(metadata), json.dumps(environments), prompt],
                config={
                    'response_mime_type': 'application/json',
                    'temperature': 0.7,
                    'top_p': 0.8,
                    'top_k': 40,
                    'response_schema': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'scene_number': {'type': 'integer'},
                                'scene_name': {'type': 'string'},
                                'scene_physical_environment': {'type': 'string'},
                                'scene_movement_description': {'type': 'string'},
                                'scene_emotions': {'type': 'string'},
                                'scene_camera_movement': {'type': 'string'},
                                'scene_duration': {'type': 'integer'},
                                'sound_effects_prompt': {'type': 'string'},
                                'first_frame_prompt': {'type': 'string'}    
                            },
                            'required': ['scene_number', 'scene_name', 'scene_physical_environment',
                                       'scene_movement_description', 'scene_emotions',
                                       'scene_camera_movement', 'scene_duration', 'sound_effects_prompt', 'first_frame_prompt']
                        }
                    }
                }
            )
            final_metadata = response.parsed
        
        elif model == "claude":
            client = anthropic.Anthropic(api_key=anthropic_api_key)
            
            system_prompt = """You are an expert at combining scene metadata with appropriate physical environments.
            """

            claude_metadata_with_env_format = """
            {
                "scenes": [
                    {
                        "scene_number": "integer value", 
                        "scene_name": "string value",
                        "scene_physical_environment": "string value",
                        "scene_movement_description": "string value",
                        "scene_emotions": "string value",
                        "scene_camera_movement": "string value",
                        "scene_duration": "integer value", # 5, 9, or 14
                        "sound_effects_prompt": "string value",
                        "first_frame_prompt": "string value"
                    },
                    ...
                ]
            }
            """
            
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=8192,
                temperature=0.7,
                system=system_prompt,
                messages=[{
                    "role": "user", 
                    "content": f'''
                    Script:\n{script}\n\nMetadata:\n{json.dumps(metadata)}\n\nEnvironments:\n{json.dumps(environments)}\n\n{prompt}
                    Output in JSON format like this:
                    {claude_metadata_with_env_format}
                    '''
                }]
            )
            
            try:
                response_text = response.content[0].text
                final_metadata = ast.literal_eval(response_text)
                final_metadata = final_metadata["scenes"]
                
                # Add scene_physical_environment to first_frame_prompt
                for scene in final_metadata:
                    scene["first_frame_prompt"] = scene["first_frame_prompt"] + " at " + scene["scene_physical_environment"]

            except Exception as e:
                print("Raw response content:", response_text)
                raise RuntimeError(f"Failed to parse Claude's response: {e}")
        
        else:
            raise ValueError(f"Unsupported model: {model}")
        
        json_path = os.path.join(video_dir, f'scenes_{timestamp}.json')
        with open(json_path, 'w') as f:
            json.dump(final_metadata, f, indent=2)
        
        return final_metadata
        
    except Exception as e:
        raise e

def generate_scene_metadata(script, model="gemini", max_scenes=5, max_environments=3, custom_env_prompt=None, custom_environments=None, video_engine="luma", lora_in_first_frame_mode=False, trigger_word=None):
    try:
        # First, determine optimal number of scenes
        prompt = f"""
        Analyze this movie script and determine the optimal number of scenes needed to tell the story effectively.
        Consider that:
        - Each scene is {LUMA_VIDEO_GENERATION_DURATION_OPTIONS if video_engine == "luma" else "[5, 10]"} seconds long
        - Scenes should maintain visual continuity
        - The story should flow naturally
        - Complex actions may need multiple scenes
        - The story should be told in a way that is engaging and interesting to watch
        - Maximum number of scenes is {max_scenes}
        - Scene should not have racist, sexist elements
        - Scene should be artistically pleasing and creative
        Return only a single integer representing the optimal number of scenes. No explanation is needed.
        """
        
        if model == "gemini":
            response = gemini_client.models.generate_content(
                model="gemini-2.0-flash-001",
                contents=[script, prompt],
                config={
                    'temperature': 0.7,
                    'top_p': 0.8,
                    'top_k': 40
                }
            )
            num_scenes = min(int(response.text.strip()), max_scenes)
            
        elif model == "claude":
            client = anthropic.Anthropic(api_key=anthropic_api_key)
            
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=100,
                temperature=0.7,
                system="You are an expert at analyzing scripts and determining optimal scene counts.",
                messages=[{"role": "user", "content": f"{script}\n\n{prompt}"}]
            )
            num_scenes = min(int(response.content[0].text.strip()), max_scenes)
        
        print(f"LLM determined optimal number of scenes: {num_scenes} (max allowed: {max_scenes})")
        
        # Continue with existing scene generation logic using determined num_scenes
        environments, env_path = generate_physical_environments(
            num_scenes, 
            script,
            max_environments=max_environments,
            model=model,
            custom_prompt=custom_env_prompt,
            custom_environments=custom_environments
        )
        metadata, metadata_path = generate_metadata_without_environment(
            num_scenes, 
            script, 
            model=model, 
            video_engine=video_engine,
            lora_in_first_frame_mode=lora_in_first_frame_mode,
            trigger_word=trigger_word
        )
        final_metadata = combine_metadata_with_environment(num_scenes, script, metadata_path, env_path, model)
        
        return final_metadata
        
    except Exception as e:
        if os.path.exists(video_dir):
            try:
                os.rmdir(video_dir)
            except OSError:
                pass
        raise e

def generate_scenes(scenes, video_engine="luma", skip_sound_effects=False, initial_image_path=None, initial_image_prompt=None, lora_in_first_frame_mode=False, lora_inference=None, lora_path=None, ltx_model_args=None):
    """
    Generate video scenes with optional initial image input.
    
    Args:
        scenes (list): List of scene metadata
        video_engine (str): Video generation engine to use ('luma', 'ltx', or 'fal')
        skip_sound_effects (bool): Whether to skip sound effects generation. If False, will generate sound effects using ElevenLabs API
        initial_image_path (str): Path to local image to use as starting frame
        initial_image_prompt (str): Prompt to generate initial image using Luma AI
        lora_in_first_frame_mode (bool): Whether to use LoRA for first frame generation
        lora_inference (FalLoraInference, optional): Instance of FalLoraInference for LoRA generation
        lora_path (str, optional): Path to the LoRA weights file
        ltx_model_args (dict, optional): Additional arguments for LTX model
    """
    scene_video_files = []  # List of lists, each inner list contains videos for one scene
    sound_effect_files = []
    last_frame_path = None
    last_frame_url = None
    first_frame_of_first_scene_url = None  # Initialize this variable
    
    # Validate ElevenLabs API key if sound effects are enabled
    if not skip_sound_effects and not os.getenv("ELEVEN_LABS_API_KEY"):
        raise ValueError("ELEVEN_LABS_API_KEY environment variable is required for sound effects generation")
    
    uploader = GCPImageUploader()
    
    # Initialize video generators
    fal_generator = FalVideoGenerator() if video_engine == "fal" else None
    luma_generator = LumaVideoGenerator() if video_engine == "luma" else None
    
    # Validate LoRA parameters
    if lora_in_first_frame_mode:
        if not lora_inference or not lora_path:
            raise ValueError("lora_inference and lora_path must be provided when lora_in_first_frame_mode is enabled")
    
    # Create video directory if it doesn't exist
    os.makedirs(video_dir, exist_ok=True)
    
    # Handle initial image if provided
    if initial_image_path or initial_image_prompt:
        saved_image_path = f"{video_dir}"
        
        if initial_image_path and os.path.exists(initial_image_path):
            # Copy the provided image to video directory
            shutil.copy2(initial_image_path, saved_image_path)
            # Upload local image to GCP and get URL
            first_frame_of_first_scene_url = uploader.upload_image(initial_image_path)
            print(f"Using provided local image as initial frame: {initial_image_path}")
            print(f"Saved initial image to: {saved_image_path}")
            
        elif initial_image_prompt:
            # Generate image using Luma AI
            from luma_image_gen import generate_image
            try:
                # Use generated_images directory for initial generation
                image_url, image_path = generate_image(initial_image_prompt, saved_image_path)
                if image_url:
                    first_frame_of_first_scene_url = image_url
                    print(f"Generated initial image from prompt: {initial_image_prompt}")
                    print(f"Saved initial image to: {saved_image_path}")
                else:
                    print(f"Warning: Failed to generate or save image from prompt: {initial_image_prompt}")
                    first_frame_of_first_scene_url = None
            except Exception as e:
                print(f"Warning: Failed to generate initial image: {str(e)}")
                first_frame_of_first_scene_url = None
    
    for i, scene in enumerate(scenes):
        print(f"Generating videos for Scene {scene['scene_number']}")
        scene_dir = f"{video_dir}/scene_{scene['scene_number']}_all_vid_{timestamp}"
        os.makedirs(scene_dir, exist_ok=True)
        
        # For LTX and FAL, we only support 5 second videos
        if video_engine in ["ltx", "fal"]:
            scene_duration = scene['scene_duration']
            # For LTX and FAL, 5 means single 5s video, 10 means two 5s videos
            if scene_duration == 5:
                video_durations = [5]
            elif scene_duration == 10:
                video_durations = [5, 5]
            else:
                raise ValueError(f"Invalid scene duration for {video_engine}: {scene_duration}. Must be 5 or 10.")
        else:
            scene_duration = scene['scene_duration']
            # Determine video durations based on scene duration for Luma
            if scene_duration == 5 or scene_duration == 9:
                video_durations = [scene_duration]
            elif scene_duration == 14:
                video_durations = [5, 9]
            elif scene_duration == 18:
                video_durations = [9, 9]
            else:
                raise ValueError(f"Invalid scene duration for Luma: {scene_duration}. Must be 5, 9, 14, or 18.")
        
        scene_videos = []  # Store videos for this scene
        
        # Handle sound effects
        if skip_sound_effects:
            sound_effect_files.append(None)
        else:
            sound_effect_path = f"{scene_dir}/scene_{scene['scene_number']}_sound.mp3"
            print(f"Generating sound effect for Scene {scene['scene_number']}")
            try:
                # Initialize ElevenLabs client
                eleven_labs = ElevenLabs(api_key=os.getenv("ELEVEN_LABS_API_KEY"))
                
                # Generate sound effects
                sound_effect_generator = eleven_labs.text_to_sound_effects.convert(
                    text=scene['sound_effects_prompt'],
                    duration_seconds=scene_duration,
                    prompt_influence=0.5
                )
                
                # Save sound effects to file
                with open(sound_effect_path, 'wb') as f:
                    for chunk in sound_effect_generator:
                        if chunk is not None:
                            f.write(chunk)
                
                # Verify the file was created and has content
                if os.path.exists(sound_effect_path) and os.path.getsize(sound_effect_path) > 0:
                    sound_effect_files.append(sound_effect_path)
                    print(f"Sound effect saved to: {sound_effect_path}")
                else:
                    print(f"Warning: Generated sound effect file is empty or missing")
                    sound_effect_files.append(None)
                    
            except Exception as e:
                print(f"Failed to generate sound effect for scene {scene['scene_number']}: {str(e)}")
                sound_effect_files.append(None)
        
        # Construct comprehensive video generation prompt
        video_prompt = f"""
        {scene['scene_physical_environment']}
        
        Movement and Action:
        {scene['scene_movement_description']}
        
        Emotional Atmosphere:
        {scene['scene_emotions']}
        
        Camera Instructions:
        {scene['scene_camera_movement']}
        """
        
        # Generate each video segment for the scene
        segment_last_frame_url = None  # Track last frame URL within the scene
        
        # Handle first frame generation
        scene_start_image_url = None
        if lora_in_first_frame_mode:
            # Generate first frame using FalLoraInference
            try:
                first_frame_path = f"{scene_dir}/scene_{scene['scene_number']}_first_frame.jpg"
                result = lora_inference.run_inference(scene['first_frame_prompt'], lora_path, first_frame_path)
                if result and 'images' in result and len(result['images']) > 0:
                    scene_start_image_url = result['images'][0]['url']
                    print(f"Generated first frame for scene {scene['scene_number']} using LoRA")
                else:
                    print(f"Warning: Failed to generate first frame for scene {scene['scene_number']}")
            except Exception as e:
                print(f"Warning: Failed to generate first frame for scene {scene['scene_number']}: {str(e)}")
        
        for vid_idx, duration in enumerate(video_durations, 1):
            # Use different naming convention based on number of videos in scene
            if len(video_durations) == 1:
                video_path = f"{scene_dir}/scene_{scene['scene_number']}_{timestamp}.mp4"
            else:
                video_path = f"{scene_dir}/scene_{scene['scene_number']}_vid_{vid_idx}_{timestamp}.mp4"
            
            print("Generate video name: ", video_path)
            print("Generating video with prompt: ", video_prompt.strip())
            print("Video duration: ", duration)
            print()

            if video_engine == "fal":
                # For FAL, use last frame URL as image input if available
                fal_args = {
                    "prompt": video_prompt.strip(),
                    "output_path": video_path
                }
                
                # Add image URL if available
                if vid_idx == 1 and i == 0 and first_frame_of_first_scene_url:
                    fal_args["image_url"] = first_frame_of_first_scene_url
                elif vid_idx == 1 and scene_start_image_url:
                    fal_args["image_url"] = scene_start_image_url
                elif vid_idx == 1 and i > 0 and last_frame_url:
                    fal_args["image_url"] = last_frame_url
                elif vid_idx > 1 and segment_last_frame_url:
                    fal_args["image_url"] = segment_last_frame_url
                
                try:
                    fal_generator.generate_video(**fal_args)
                    if not os.path.exists(video_path):
                        raise RuntimeError("FAL video generation failed to save the video file")
                except Exception as e:
                    raise RuntimeError(f"FAL video generation failed: {str(e)}")

            elif video_engine == "ltx":
                # For LTX, use last frame URL as image input if available
                ltx_args = {
                    "prompt": video_prompt.strip(),
                    "output_path": video_path
                }
                if vid_idx == 1 and i == 0 and first_frame_of_first_scene_url:
                    ltx_args["image_url"] = first_frame_of_first_scene_url
                elif vid_idx == 1 and scene_start_image_url:
                    ltx_args["image_url"] = scene_start_image_url
                elif vid_idx == 1 and i > 0 and last_frame_url:
                    ltx_args["image_url"] = last_frame_url
                elif vid_idx > 1 and segment_last_frame_url:
                    ltx_args["image_url"] = segment_last_frame_url
                
                # Add LTX model arguments if provided
                if ltx_model_args:
                    ltx_args["model_args"] = ltx_model_args
                
                try:
                    result = generate_ltx_video(**ltx_args)
                    if not os.path.exists(video_path):
                        raise RuntimeError("LTX video generation failed to save the video file")
                except Exception as e:
                    raise RuntimeError(f"LTX video generation failed: {str(e)}")
            else:
                # Use Luma for video generation
                luma_args = {
                    "prompt": video_prompt.strip(),
                    "output_path": video_path,
                    "resolution": "540p",
                    "duration": f"{duration}s"
                }

                # Add image URL if available
                if vid_idx == 1 and i == 0 and first_frame_of_first_scene_url:
                    luma_args["image_url"] = first_frame_of_first_scene_url
                elif vid_idx == 1 and scene_start_image_url:
                    luma_args["image_url"] = scene_start_image_url
                elif vid_idx == 1 and i > 0 and last_frame_url:
                    luma_args["image_url"] = last_frame_url
                elif vid_idx > 1 and segment_last_frame_url:
                    luma_args["image_url"] = segment_last_frame_url

                try:
                    result = luma_generator.generate_video(**luma_args)
                    if not os.path.exists(video_path):
                        raise RuntimeError("Luma video generation failed to save the video file")
                except Exception as e:
                    raise RuntimeError(f"Luma video generation failed: {str(e)}")
            
            scene_videos.append(video_path)
            
            # Extract last frame from each video segment
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise RuntimeError(f"Could not open video file: {video_path}")
            
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_count-1)
            ret, frame = cap.read()
            
            # Save last frame for each video segment
            if len(video_durations) == 1:
                frame_path = f"{scene_dir}/scene_{scene['scene_number']}_last_frame.jpg"
            else:
                frame_path = f"{scene_dir}/scene_{scene['scene_number']}_vid_{vid_idx}_last_frame.jpg"
                
            if ret:
                cv2.imwrite(frame_path, frame)
                print(f"Successfully extracted last frame to: {frame_path}")
            else:
                raise RuntimeError(f"Failed to extract last frame from video: {video_path}")
            
            cap.release()
            
            # Upload frame to GCP and get signed URL
            max_retries = 3
            retry_count = 0
            while retry_count < max_retries:
                new_frame_url = uploader.upload_image(frame_path)
                if new_frame_url != segment_last_frame_url:
                    if vid_idx == len(video_durations):  # If this is the last video in the scene
                        last_frame_url = new_frame_url  # Save for next scene
                    else:
                        segment_last_frame_url = new_frame_url  # Save for next video in this scene
                    print(f"Successfully uploaded frame with unique URL: {new_frame_url}")
                    break
                print(f"Got duplicate URL, retrying... (attempt {retry_count + 1}/{max_retries})")
                time.sleep(2)
                retry_count += 1
            
            if retry_count == max_retries:
                raise RuntimeError(f"Failed to get unique frame URL for video {vid_idx} in scene {scene['scene_number']}")
        
        # Stitch videos for this scene if there are multiple
        if len(scene_videos) > 1:
            scene_clips = [VideoFileClip(video) for video in scene_videos]
            scene_final = concatenate_videoclips(scene_clips)
            scene_final_path = f"{video_dir}/scene_{scene['scene_number']}_{timestamp}.mp4"
            scene_final.write_videofile(scene_final_path)
            
            # Close clips
            for clip in scene_clips:
                clip.close()
            
            scene_video_files.append(scene_final_path)
        else:
            # Copy the single video to the main directory as well
            single_video_path = scene_videos[0]
            final_video_path = f"{video_dir}/scene_{scene['scene_number']}_{timestamp}.mp4"
            shutil.copy2(single_video_path, final_video_path)
            scene_video_files.append(final_video_path)
        
        time.sleep(2)
    
    return scene_video_files, sound_effect_files

def calculate_total_duration(scenes):
    """Calculate total duration of all scenes in seconds"""
    return sum(scene['scene_duration'] for scene in scenes)

def generate_narration_text(scenes, total_duration, model="gemini"):
    """
    Generate narration text based on the scene metadata and desired duration.
    The narration should be timed to roughly match the video duration.
    """
    # Create a comprehensive scene description from metadata
    scene_descriptions = []
    for scene in scenes:
        description = f"""
        {scene['scene_name']}:
        Environment: {scene['scene_physical_environment']}
        Action: {scene['scene_movement_description']}
        Emotional Atmosphere: {scene['scene_emotions']}
        Camera Movement: {scene['scene_camera_movement']}
        """
        scene_descriptions.append(description)
    
    combined_description = "\n".join(scene_descriptions)
    
    prompt = f"""
    Create a narration script based on the scene descriptions below. The narration should:
    1. Be timed to take approximately {total_duration} seconds when read at a normal pace
    2. Output should be {total_duration * 2} number of words
    3. Provide context and atmosphere that enhances the visual elements
    4. Focus on describing key events, emotions, and revelations
    5. Maintain a consistent tone that matches the story's mood
    6. Be written in present tense
    7. Use clear, engaging language suitable for voice-over
    8. Include natural pauses and breaks in the pacing
    9. Flow smoothly between scenes while maintaining continuity
    
    Return the narration text only, without any formatting or additional notes.
    """
    
    try:
        if model == "gemini":
            response = gemini_client.models.generate_content(
                model="gemini-2.0-flash-001",
                contents=[combined_description, prompt],
                config={
                    'temperature': 0.7,
                    'top_p': 0.8,
                    'top_k': 40
                }
            )
            narration = response.text
            
        elif model == "claude":
            client = anthropic.Anthropic(api_key=anthropic_api_key)
            
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=8192,
                temperature=0.7,
                system="You are an expert at writing engaging narration scripts.",
                messages=[{"role": "user", "content": f"{combined_description}\n\n{prompt}"}]
            )
            narration = response.content[0].text
            
        else:
            raise ValueError(f"Unsupported model: {model}")
        
        # Save narration text
        narration_path = os.path.join(video_dir, f'narration_text_{timestamp}.txt')
        with open(narration_path, 'w') as f:
            f.write(narration)
        
        return narration, narration_path
        
    except Exception as e:
        raise e

def generate_narration_audio(narration_text, target_duration):
    """
    Generate audio narration from text and adjust its speed to match target duration.
    Returns the path to the processed audio file.
    """
    try:
        # Generate initial audio using ElevenLabs
        audio_path = os.path.join(video_dir, f'narration_audio_{timestamp}.mp3')
        success = generate_speech(narration_text, audio_path)
        
        if not success:
            raise RuntimeError("Failed to generate speech audio")
        
        # Load the generated audio to get its duration
        audio = AudioFileClip(audio_path)
        original_duration = audio.duration
        
        # Calculate the speed factor needed to match target duration
        speed_factor = original_duration / target_duration
        
        # Create speed-adjusted audio using time transformation
        def speed_change(t):
            return speed_factor * t
            
        adjusted_audio = audio.set_make_frame(lambda t: audio.get_frame(speed_change(t)))
        adjusted_audio.duration = target_duration
        
        # Save the adjusted audio with a valid sample rate
        adjusted_audio_path = os.path.join(video_dir, f'narration_audio_adjusted_{timestamp}.mp3')
        adjusted_audio.write_audiofile(adjusted_audio_path, fps=44100)  # Use standard sample rate
        
        # Clean up
        audio.close()
        adjusted_audio.close()
        
        return adjusted_audio_path
        
    except Exception as e:
        print(f"Error generating narration audio: {str(e)}")
        return None

def stitch_videos(video_files, sound_effect_files=None, narration_audio_path=None):
    final_clips = []
    
    for video_file, sound_file in zip(video_files, sound_effect_files or [None] * len(video_files)):
        try:
            video_clip = VideoFileClip(video_file)
            
            if sound_file and os.path.exists(sound_file):
                try:
                    # Load sound effect
                    audio_clip = AudioFileClip(sound_file)
                    
                    # If audio is longer than video, trim it
                    if audio_clip.duration > video_clip.duration:
                        audio_clip = audio_clip.subclip(0, video_clip.duration)
                    # If audio is shorter than video, loop it or pad with silence
                    elif audio_clip.duration < video_clip.duration:
                        # For simplicity, we'll just use the shorter duration
                        video_clip = video_clip.subclip(0, audio_clip.duration)
                    
                    # Combine video with sound effect
                    video_clip = video_clip.set_audio(audio_clip)
                except Exception as e:
                    print(f"Warning: Failed to process audio for {sound_file}: {str(e)}")
                    # Continue with video without audio if audio processing fails
            
            final_clips.append(video_clip)
        except Exception as e:
            print(f"Warning: Failed to process video {video_file}: {str(e)}")
            continue
    
    if not final_clips:
        raise RuntimeError("No video clips were successfully processed")
    
    # Concatenate all clips
    final_clip = concatenate_videoclips(final_clips)
    
    # Add narration audio if provided and exists
    if narration_audio_path and os.path.exists(narration_audio_path):
        try:
            narration_audio = AudioFileClip(narration_audio_path)
            # Combine original audio with narration
            final_audio = CompositeVideoClip([final_clip]).audio
            if final_audio is not None:
                combined_audio = CompositeVideoClip([
                    final_clip.set_audio(final_audio.volumex(0.7)),  # Reduce original volume
                    final_clip.set_audio(narration_audio.volumex(1.0))  # Keep narration at full volume
                ]).audio
                final_clip = final_clip.set_audio(combined_audio)
            else:
                final_clip = final_clip.set_audio(narration_audio)
        except Exception as e:
            print(f"Warning: Failed to add narration audio: {str(e)}")
    
    # Write final video
    output_path = f"{video_dir}/final_video_{timestamp}.mp4"
    final_clip.write_videofile(output_path)
    
    # Close all clips
    for clip in final_clips:
        clip.close()
    
    return output_path

def generate_video(
    script_text, 
    model_choice="gemini",
    video_engine="luma",
    metadata_only=False,
    max_scenes=12,
    max_environments=3,
    custom_env_prompt=None,
    custom_environments=None,
    skip_narration=True,
    skip_sound_effects=True,
    initial_image_path=None,
    initial_image_prompt=None,
    lora_in_first_frame_mode=False,
    trigger_word=None,
    lora_inference=None,
    lora_path=None,
    ltx_model_args=None
):
    try:
        if initial_image_path and initial_image_prompt:
            raise ValueError("Cannot provide both initial_image_path and initial_image_prompt. Please choose one.")
            
        if (initial_image_prompt or lora_in_first_frame_mode) and not os.getenv("LUMAAI_API_KEY"):
            raise ValueError("Luma AI API key is required for image generation.")
            
        if lora_in_first_frame_mode and (not lora_inference or not lora_path):
            raise ValueError("lora_inference and lora_path must be provided when lora_in_first_frame_mode is enabled")

        # Generate scene metadata with custom parameters
        scenes = generate_scene_metadata(
            script_text, 
            model=model_choice,
            max_scenes=max_scenes,
            max_environments=max_environments,
            custom_env_prompt=custom_env_prompt,
            custom_environments=custom_environments,
            video_engine=video_engine,
            lora_in_first_frame_mode=lora_in_first_frame_mode,
            trigger_word=trigger_word
        )
        
        if metadata_only:
            return json.dumps(scenes, indent=2), None
        
        # Generate narration if not skipped
        narration_audio_path = None
        if not skip_narration:
            # Calculate total duration only if needed for narration
            total_duration = calculate_total_duration(scenes)
            narration_text, narration_text_path = generate_narration_text(scenes, total_duration, model_choice)
            narration_audio_path = generate_narration_audio(narration_text, total_duration)
        
        # Generate videos and sound effects
        print("Generating videos and sound effects...")
        video_files, sound_effect_files = generate_scenes(
            scenes, 
            video_engine, 
            skip_sound_effects,
            initial_image_path=initial_image_path,
            initial_image_prompt=initial_image_prompt,
            lora_in_first_frame_mode=lora_in_first_frame_mode,
            lora_inference=lora_inference,
            lora_path=lora_path,
            ltx_model_args=ltx_model_args
        )
        
        # Stitch videos with sound effects and narration
        final_video = stitch_videos(video_files, sound_effect_files, narration_audio_path)
        
        return json.dumps(scenes, indent=2), final_video
    except Exception as e:
        return str(e), None

def main():
    parser = argparse.ArgumentParser(description='Generate a video based on script analysis')
    parser.add_argument('--model', type=str, choices=['gemini', 'claude'], default='gemini',
                       help='Model to use for scene generation (default: gemini)')
    parser.add_argument('--video_engine', type=str, choices=['luma', 'ltx', 'fal'], default='luma',
                       help='Video generation engine to use (default: luma)')
    parser.add_argument('--metadata_only', action='store_true',
                       help='Only generate scene metadata JSON without video generation')
    parser.add_argument('--script_file', type=str, default='movie_script2.txt',
                       help='Path to the movie script file (default: movie_script2.txt)')
    parser.add_argument('--enable_narration', action='store_true',
                       help='Enable narration generation (disabled by default)')
    parser.add_argument('--enable_sound_effects', action='store_true',
                       help='Enable sound effects generation (disabled by default)')
    parser.add_argument('--max_scenes', type=int, default=5,
                       help='Maximum number of scenes to generate (default: 5)')
    parser.add_argument('--max_environments', type=int, default=3,
                       help='Maximum number of unique environments to use (default: 3)')
    parser.add_argument('--initial_image_path', type=str,
                       help='Path to local image to use as starting frame for the first video')
    parser.add_argument('--initial_image_prompt', type=str,
                       help='Prompt to generate initial image using Luma AI for the first video')
    parser.add_argument('--lora_in_first_frame_mode', action='store_true',
                       help='Enable image generation at the start of each scene')
    parser.add_argument('--trigger_word', type=str,
                       help='Trigger word to include in the first frame prompt')
    args = parser.parse_args()

    if args.initial_image_path and args.initial_image_prompt:
        print("Error: Cannot provide both initial_image_path and initial_image_prompt. Please choose one.")
        return
        
    if (args.initial_image_prompt or args.lora_in_first_frame_mode) and not os.getenv("LUMAAI_API_KEY"):
        print("Error: Luma AI API key is required for image generation.")
        return

    # Generate scene metadata with LLM-determined number of scenes
    print(f"Analyzing script and generating scene metadata using {args.model}...")
    try:
        with open(args.script_file, 'r') as f:
            script = f.read()
    except FileNotFoundError:
        print(f"Error: Script file '{args.script_file}' not found")
        return
    except Exception as e:
        print(f"Error reading script file: {str(e)}")
        return

    scenes = generate_scene_metadata(
        script, 
        model=args.model,
        max_scenes=args.max_scenes,
        max_environments=args.max_environments,
        video_engine=args.video_engine,
        lora_in_first_frame_mode=args.lora_in_first_frame_mode,
        trigger_word=args.trigger_word
    )
    
    if args.metadata_only:
        print(f"Scene metadata JSON generated in: {video_dir}")
        return

    # Generate narration text and audio if enabled
    narration_audio_path = None
    if args.enable_narration:
        # Calculate total duration only if needed for narration
        total_duration = calculate_total_duration(scenes)
        print(f"Total video duration: {total_duration} seconds")
        
        print("Generating narration text...")
        narration_text, narration_text_path = generate_narration_text(scenes, total_duration, args.model)
        
        print("Generating narration audio...")
        narration_audio_path = generate_narration_audio(narration_text, total_duration)
    else:
        print("Narration generation is disabled...")

    # Generate videos and sound effects
    print("Generating videos and sound effects...")
    video_files, sound_effect_files = generate_scenes(
        scenes, 
        args.video_engine, 
        not args.enable_sound_effects,  # Invert the flag since we're using enable_ instead of skip_
        initial_image_path=args.initial_image_path,
        initial_image_prompt=args.initial_image_prompt,
        lora_in_first_frame_mode=args.lora_in_first_frame_mode
    )
    
    # Stitch videos with sound effects and narration
    print("Stitching videos together with sound effects and narration...")
    final_video = stitch_videos(video_files, sound_effect_files, narration_audio_path)
    
    print(f"Final video saved to: {final_video}")

if __name__ == "__main__":
    main()
