import gradio as gr
import os
import json
import time
from datetime import datetime
from fal_train_lora import LoraTrainer
from fal_lora_inference import FalLoraInference
from video_generation_reference import generate_video
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
fal_api_key = os.getenv("FAL_API_KEY")

# Initialize our components
trainer = LoraTrainer(fal_api_key)
inference = FalLoraInference()

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
        return "Please provide both a ZIP file and a trigger word.", None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"{trigger_word}_output_{timestamp}.json"
    
    # Train the LoRA model
    result = trainer.train_lora(zip_file.name, trigger_word)
    
    # Save the result
    output_path = os.path.join("trained_lora_config", output_filename)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
    
    return f"LoRA training completed. Saved as {output_filename}", get_trained_loras()

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

def generate_video_with_lora(script_text, max_scenes, max_environments, lora_config, trigger_word, video_engine, model_choice, enable_sound_effects):
    """Generate video using LoRA for first frames"""
    if not script_text or not lora_config or not trigger_word:
        return "Please provide script text and load a LoRA configuration first.", None
    
    try:
        # Get the LoRA path from the config
        lora_path = lora_config.get('diffusers_lora_file', {}).get('url')
        if not lora_path:
            return "LoRA path not found in configuration.", None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Initialize FalLoraInference for first frame generation
        inference = FalLoraInference()
        
        # Generate video with LoRA first frame mode enabled and skip narration/sound effects
        metadata_json, final_video_path = generate_video(
            script_text=script_text,
            model_choice=model_choice,  # Use the selected model
            video_engine=video_engine,
            max_scenes=max_scenes,
            max_environments=max_environments,
            lora_in_first_frame_mode=True,
            trigger_word=trigger_word,
            skip_narration=True,    # Skip narration by default
            skip_sound_effects=not enable_sound_effects,  # Use the checkbox value
            lora_inference=inference,
            lora_path=lora_path
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
                    trained_loras = gr.Dropdown(choices=get_trained_loras(), label="Available Digital Identities", interactive=True)
                    with gr.Column():
                        refresh_btn = gr.Button("🔄 Refresh List")
                        load_btn = gr.Button("Load Selected Identity", variant="primary")
            with gr.Column(scale=1):
                load_status = gr.Textbox(label="Identity Load Status", interactive=False)
        
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
    lora_config = gr.State()
    current_trigger_word = gr.State()
    
    # Set up event handlers
    train_btn.click(
        train_lora,
        inputs=[zip_input, trigger_word],
        outputs=[train_output, trained_loras]
    )
    
    refresh_btn.click(
        lambda: gr.Dropdown(choices=get_trained_loras()),
        outputs=[trained_loras]
    )
    
    load_btn.click(
        load_lora_config,
        inputs=[trained_loras],
        outputs=[load_status, lora_config, current_trigger_word]
    )
    
    generate_btn.click(
        generate_video_with_lora,
        inputs=[script_input, max_scenes, max_environments, lora_config, current_trigger_word, video_engine, model_choice, enable_sound_effects],
        outputs=[generation_status, video_output]
    )

if __name__ == "__main__":
    app.launch() 