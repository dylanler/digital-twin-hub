#!/usr/bin/env python3
import replicate
import argparse
import requests
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Check and set Replicate API token
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
if not REPLICATE_API_TOKEN:
    print("Error: REPLICATE_API_TOKEN environment variable is not set.")
    print("Please create a .env file in the project root with your Replicate API token:")
    print("REPLICATE_API_TOKEN=your_token_here")
    print("\nYou can get your token from: https://replicate.com/account")
    sys.exit(1)

os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

def download_image(url, filename):
    """Download image from URL and save it with given filename"""
    response = requests.get(url)
    if response.status_code == 200:
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"Image saved as {filename}")
    else:
        print(f"Failed to download image: {response.status_code}")

def load_lora_config(json_path):
    """Load LoRA configuration from JSON file"""
    try:
        with open(json_path, 'r') as f:
            config = json.load(f)
            if 'diffusers_lora_file' in config:
                return config['diffusers_lora_file']['url']
            else:
                print(f"Warning: No LoRA file URL found in config {json_path}")
                return None
    except Exception as e:
        print(f"Error loading LoRA config from {json_path}: {e}")
        return None

def build_prompt_template(has_character, has_environment, has_object):
    """Build a dynamic prompt template based on available LoRAs"""
    parts = []
    if has_character:
        parts.append("{char}")
    if has_environment:
        parts.append("in a {env}" if has_character else "{env}")
    if has_object:
        parts.append("with {obj}")
    
    if not parts:
        return "pnt style image"  # Fallback template (should never happen as we require at least one LoRA)
    
    return "pnt style " + " ".join(parts)

def main():
    parser = argparse.ArgumentParser(description='Generate images using Replicate multi-LoRA model')
    parser.add_argument('--character_trigger', help='Trigger word for the character LoRA')
    parser.add_argument('--environment_trigger', help='Trigger word for the environment LoRA')
    parser.add_argument('--object_trigger', help='Trigger word for the object LoRA')
    parser.add_argument('--prompt_template', help='Custom prompt template. If provided, overrides the automatic template.')
    parser.add_argument('--output_name', required=True, help='Base name for the output image(s)')
    parser.add_argument('--num_outputs', type=int, default=1, help='Number of images to generate (max 4)')
    parser.add_argument('--aspect_ratio', default="16:9", 
                       choices=["1:1", "16:9", "21:9", "3:2", "2:3", "4:5", "5:4", "3:4", "4:3", "9:16", "9:21"],
                       help='Aspect ratio for the generated image')
    parser.add_argument('--output_format', default="jpg", choices=["webp", "jpg", "png"],
                       help='Output image format')
    parser.add_argument('--lora_character_path', help='Path to character LoRA JSON configuration')
    parser.add_argument('--lora_environment_path', help='Path to environment LoRA JSON configuration')
    parser.add_argument('--lora_object_path', help='Path to object LoRA JSON configuration')

    args = parser.parse_args()

    # Validate LoRA configurations
    lora_configs = []
    if args.lora_character_path:
        if not args.character_trigger:
            print("Error: character_trigger is required when lora_character_path is provided")
            sys.exit(1)
        lora_configs.append((args.lora_character_path, "character"))

    if args.lora_environment_path:
        if not args.environment_trigger:
            print("Error: environment_trigger is required when lora_environment_path is provided")
            sys.exit(1)
        lora_configs.append((args.lora_environment_path, "environment"))

    if args.lora_object_path:
        if not args.object_trigger:
            print("Error: object_trigger is required when lora_object_path is provided")
            sys.exit(1)
        lora_configs.append((args.lora_object_path, "object"))

    if not lora_configs:
        print("Error: At least one LoRA configuration must be provided")
        sys.exit(1)

    # Initialize empty list for LoRA URLs
    lora_urls = []

    # Load LoRA URLs from JSON configs
    for json_path, lora_type in lora_configs:
        lora_url = load_lora_config(json_path)
        if lora_url:
            lora_urls.append(lora_url)
            print(f"Added {lora_type} LoRA from config {json_path}: {lora_url}")
        else:
            raise ValueError(f"Failed to load {lora_type} LoRA URL from {json_path}")

    # Build prompt template if not provided
    if not args.prompt_template:
        template = build_prompt_template(
            args.lora_character_path is not None,
            args.lora_environment_path is not None,
            args.lora_object_path is not None
        )
    else:
        template = args.prompt_template

    # Format the prompt with available trigger words
    prompt_args = {}
    if args.character_trigger:
        prompt_args['char'] = args.character_trigger
    if args.environment_trigger:
        prompt_args['env'] = args.environment_trigger
    if args.object_trigger:
        prompt_args['obj'] = args.object_trigger

    prompt = template.format(**prompt_args)

    # Define the input parameters
    input_params = {
        "prompt": prompt,
        "num_outputs": args.num_outputs,
        "aspect_ratio": args.aspect_ratio,
        "output_format": args.output_format,
        "hf_loras": lora_urls,
        "lora_scales": [1.2] * len(lora_urls),  # LoRA scale for each model
        "disable_safety_checker": True  # Disable safety checker
    }

    print(f"Generating image(s) with prompt: {prompt}")
    print(f"Using LoRA models: {lora_urls}")
    print(f"LoRA scales: {input_params['lora_scales']}")
    print(f"Safety checker disabled: {input_params['disable_safety_checker']}")
    
    try:
        # Run the model
        output = replicate.run(
            "lucataco/flux-dev-multi-lora:2389224e115448d9a77c07d7d45672b3f0aa45acacf1c5bcf51857ac295e3aec",
            input=input_params
        )

        # Download and save each generated image
        for index, item in enumerate(output):
            if args.num_outputs == 1:
                filename = f"{args.output_name}.{args.output_format}"
            else:
                filename = f"{args.output_name}_{index}.{args.output_format}"
            download_image(item, filename)

    except Exception as e:
        print(f"Error during image generation: {e}")

if __name__ == "__main__":
    # Example usage:
    # Using just character LoRA:
    #    python multi_lora_inference.py \
    #        --character_trigger "wizard" \
    #        --output_name "wizard_scene" \
    #        --lora_character_path "CHARACTER/output.json"
    #
    # Using character and environment LoRAs:
    #    python multi_lora_inference.py \
    #        --character_trigger "wizard" \
    #        --environment_trigger "magical forest" \
    #        --output_name "wizard_in_forest" \
    #        --lora_character_path "CHARACTER/output.json" \
    #        --lora_environment_path "ENVIRONMENT/output.json"
    #
    # Using all three LoRAs with custom prompt:
    #    python multi_lora_inference.py \
    #        --character_trigger "wizard" \
    #        --environment_trigger "magical forest" \
    #        --object_trigger "crystal staff" \
    #        --output_name "wizard_scene" \
    #        --prompt_template "detailed painting of a {char} exploring a {env} while holding a {obj}" \
    #        --num_outputs 2 \
    #        --aspect_ratio "16:9" \
    #        --output_format "png" \
    #        --lora_character_path "CHARACTER/output.json" \
    #        --lora_environment_path "ENVIRONMENT/output.json" \
    #        --lora_object_path "OBJECT/output.json"
    main() 