import gradio as gr
import os
import json
import time
from datetime import datetime
from fal_train_lora import LoraTrainer
from video_generation_reference_future import generate_video
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
fal_api_key = os.getenv("FAL_API_KEY")

# Initialize our components
trainer = LoraTrainer(fal_api_key)

# Create necessary directories
os.makedirs("trained_lora_config", exist_ok=True)
os.makedirs("lora_inference_images", exist_ok=True)
os.makedirs("generated_videos", exist_ok=True)

def get_trained_loras():
    """Get list of trained LoRA configurations"""
    lora_files = []
    if os.path.exists("trained_lora_config"):
        lora_files = [f for f in os.listdir("trained_lora_config") if f.endswith('.json')]
    return lora_files

def train_lora(zip_file, trigger_word):
    """Train LoRA model with uploaded images"""
    if not zip_file or not trigger_word:
        return "Please provide both a ZIP file and a trigger word.", None, None, None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"{trigger_word}_output_{timestamp}.json"
    
    # Train the LoRA model
    result = trainer.train_lora(zip_file.name, trigger_word)
    
    # Save the result
    output_path = os.path.join("trained_lora_config", output_filename)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
    
    return f"LoRA training completed. Saved as {output_filename}", get_trained_loras(), None, None

def load_lora_config(selected_lora):
    """Load selected LoRA configuration"""
    if not selected_lora:
        return "Please select a LoRA configuration first.", None, None
    
    config_path = os.path.join("trained_lora_config", selected_lora)
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Extract trigger word from filename
    trigger_word = selected_lora.split('_output_')[0]
    
    return f"Loaded LoRA configuration: {selected_lora}", config, trigger_word

def generate_video_with_lora(script_text, max_scenes, max_environments, char_lora_config, env_lora_config, obj_lora_config, char_trigger, env_trigger, obj_trigger, video_engine, model_choice, enable_sound_effects):
    """Generate video using LoRA for first frames"""
    if not script_text or not char_lora_config or not char_trigger:
        return "Please provide script text and load a character LoRA first.", None
    
    try:
        # Get the LoRA paths from the configs
        char_lora_path = char_lora_config.get('diffusers_lora_file', {}).get('url')
        env_lora_path = env_lora_config.get('diffusers_lora_file', {}).get('url') if env_lora_config else None
        obj_lora_path = obj_lora_config.get('diffusers_lora_file', {}).get('url') if obj_lora_config else None
        
        if not char_lora_path:
            return "Character LoRA path not found in configuration.", None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Initialize MultiLoraInference for first frame generation
        from multi_lora_inference import main as multi_lora_main
        import sys
        
        # Create arguments for multi_lora_inference
        class Args:
            def __init__(self):
                self.character_trigger = char_trigger
                self.environment_trigger = env_trigger
                self.object_trigger = obj_trigger
                # Find the actual LoRA filenames from the configs
                self.lora_character_path = next((f for f in get_trained_loras() if f.startswith(f"{char_trigger}_output_")), None)
                self.lora_environment_path = next((f for f in get_trained_loras() if env_trigger and f.startswith(f"{env_trigger}_output_")), None)
                self.lora_object_path = next((f for f in get_trained_loras() if obj_trigger and f.startswith(f"{obj_trigger}_output_")), None)
                
                if not self.lora_character_path:
                    raise ValueError(f"Could not find LoRA file for character trigger word: {char_trigger}")
                
                # Add full paths
                self.lora_character_path = os.path.join("trained_lora_config", self.lora_character_path)
                if self.lora_environment_path:
                    self.lora_environment_path = os.path.join("trained_lora_config", self.lora_environment_path)
                if self.lora_object_path:
                    self.lora_object_path = os.path.join("trained_lora_config", self.lora_object_path)
                
                self.prompt_template = None  # Let the script build the template
                self.output_name = f"first_frame_{timestamp}"
                self.num_outputs = 1
                self.aspect_ratio = "16:9"
                self.output_format = "jpg"
        
        # Create a mock sys.argv for multi_lora_inference
        sys.argv = [sys.argv[0]]  # Keep script name
        
        # Create the Args instance
        args = Args()
        
        # Generate video with multi-LoRA first frame mode enabled and skip narration/sound effects
        metadata_json, final_video_path = generate_video(
            script_text=script_text,
            model_choice=model_choice,  # Use the selected model
            video_engine=video_engine,
            max_scenes=max_scenes,
            max_environments=max_environments,
            lora_in_first_frame_mode=True,
            trigger_word=char_trigger,  # Main character trigger word
            skip_narration=True,    # Skip narration by default
            skip_sound_effects=not enable_sound_effects,  # Use the checkbox value
            lora_inference=args,  # Pass the arguments object
            lora_path=char_lora_path  # Main character LoRA path
        )
        
        if not final_video_path:
            return f"Video generation failed: {metadata_json}", None
            
        return "Video generation completed successfully!", final_video_path
        
    except Exception as e:
        return f"Error during video generation: {str(e)}", None

# Create Gradio interface
with gr.Blocks() as app:
    gr.Markdown("# Smart Influencer Hub - Digital Identity Studio")
    
    with gr.Column():
        # Step 1: Create Digital Identity
        gr.Markdown("## Step 1: Create Your Digital Identity")
        with gr.Row():
            with gr.Column(scale=2):
                zip_input = gr.File(label="Upload ZIP file with your professional photos (10-20 images recommended)")
                trigger_word = gr.Textbox(label="Your unique identifier (e.g., @username or brand name)")
                train_btn = gr.Button("Create Digital Identity", variant="primary")
            with gr.Column(scale=1):
                train_output = gr.Textbox(label="Creation Status", interactive=False)
        
        # Step 2: Select Identity
        gr.Markdown("## Step 2: Select Digital Identity")
        with gr.Row():
            with gr.Column(scale=2):
                with gr.Row():
                    trained_loras = gr.Dropdown(choices=get_trained_loras(), label="Character LoRA", interactive=True)
                    env_loras = gr.Dropdown(choices=get_trained_loras(), label="Environment LoRA (Optional)", interactive=True)
                    obj_loras = gr.Dropdown(choices=get_trained_loras(), label="Object LoRA (Optional)", interactive=True)
                    with gr.Column():
                        refresh_btn = gr.Button("🔄 Refresh List")
                        load_btn = gr.Button("Load Selected Identity", variant="primary")
            with gr.Column(scale=1):
                load_status = gr.Textbox(label="Identity Load Status", interactive=False)
                
            # Add trigger word inputs
            with gr.Column(scale=1):
                char_trigger = gr.Textbox(label="Character Trigger Word", interactive=True)
                env_trigger = gr.Textbox(label="Environment Trigger Word (Optional)", interactive=True)
                obj_trigger = gr.Textbox(label="Object Trigger Word (Optional)", interactive=True)
        
        # Step 3: Create Content
        gr.Markdown("## Step 3: Generate Professional Content")
        with gr.Column():
            script_input = gr.Textbox(
                label="Describe your content (e.g., scene details, mood, outfit, background)",
                lines=5
            )
            with gr.Row():
                max_scenes = gr.Slider(
                    minimum=1,
                    maximum=20,
                    value=5,
                    step=1,
                    label="Number of scenes in video"
                )
                max_environments = gr.Slider(
                    minimum=1,
                    maximum=10,
                    value=3,
                    step=1,
                    label="Number of different locations"
                )
            video_engine = gr.Dropdown(
                choices=["luma", "ltx", "fal"],
                value="luma",
                label="Video Quality Preset",
                interactive=True
            )
            model_choice = gr.Dropdown(
                choices=["gemini", "claude"],
                value="gemini",
                label="Content Direction AI",
                interactive=True
            )
            enable_sound_effects = gr.Checkbox(
                label="Add Background Music & Effects",
                value=False,
                interactive=True
            )
            generate_btn = gr.Button("Create Content", variant="primary")
            generation_status = gr.Textbox(label="Creation Status", interactive=False)
            video_output = gr.Video(label="Your Generated Content")
    
    # Hidden components to store state
    char_lora_config = gr.State()
    env_lora_config = gr.State()
    obj_lora_config = gr.State()
    current_char_trigger = gr.State()
    current_env_trigger = gr.State()
    current_obj_trigger = gr.State()
    
    # Set up event handlers
    train_btn.click(
        train_lora,
        inputs=[zip_input, trigger_word],
        outputs=[train_output, trained_loras, env_loras, obj_loras]
    )
    
    refresh_btn.click(
        lambda: (gr.Dropdown(choices=get_trained_loras()), gr.Dropdown(choices=get_trained_loras()), gr.Dropdown(choices=get_trained_loras())),
        outputs=[trained_loras, env_loras, obj_loras]
    )
    
    def load_all_lora_configs(char_lora, env_lora, obj_lora):
        """Load all selected LoRA configurations"""
        # Load character LoRA (required)
        if not char_lora:
            return "Please select a character LoRA.", None, None, None, None, None, None
        
        try:
            # Load character LoRA
            char_config_path = os.path.join("trained_lora_config", char_lora)
            with open(char_config_path, 'r') as f:
                char_config = json.load(f)
            char_trigger = char_lora.split('_output_')[0]
            
            # Load environment LoRA (optional)
            env_config = None
            env_trigger = None
            if env_lora:
                env_config_path = os.path.join("trained_lora_config", env_lora)
                with open(env_config_path, 'r') as f:
                    env_config = json.load(f)
                env_trigger = env_lora.split('_output_')[0]
            
            # Load object LoRA (optional)
            obj_config = None
            obj_trigger = None
            if obj_lora:
                obj_config_path = os.path.join("trained_lora_config", obj_lora)
                with open(obj_config_path, 'r') as f:
                    obj_config = json.load(f)
                obj_trigger = obj_lora.split('_output_')[0]
            
            # Build status message
            status_parts = [f"Character LoRA: {char_lora} (trigger: {char_trigger})"]
            if env_lora:
                status_parts.append(f"Environment LoRA: {env_lora} (trigger: {env_trigger})")
            if obj_lora:
                status_parts.append(f"Object LoRA: {obj_lora} (trigger: {obj_trigger})")
            
            status = "\n".join(status_parts)
            
            return (
                status,
                char_config, env_config, obj_config,  # configs
                char_trigger, env_trigger, obj_trigger  # trigger words
            )
            
        except Exception as e:
            return f"Error loading LoRA configurations: {str(e)}", None, None, None, None, None, None
    
    load_btn.click(
        load_all_lora_configs,
        inputs=[trained_loras, env_loras, obj_loras],
        outputs=[
            load_status,
            char_lora_config, env_lora_config, obj_lora_config,
            char_trigger, env_trigger, obj_trigger
        ]
    )
    
    generate_btn.click(
        generate_video_with_lora,
        inputs=[
            script_input, max_scenes, max_environments,
            char_lora_config, env_lora_config, obj_lora_config,
            char_trigger, env_trigger, obj_trigger,
            video_engine, model_choice, enable_sound_effects
        ],
        outputs=[generation_status, video_output]
    )

if __name__ == "__main__":
    app.launch() 