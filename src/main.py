import os
import json
import argparse
from typing import Tuple, Optional
from .generators.scene_generator import SceneGenerator
from .generators.narration_generator import NarrationGenerator
from .generators.sound_generator import SoundGenerator
from .generators.video_generator import VideoGenerator
from .config import (
    DEFAULT_MAX_SCENES,
    DEFAULT_MAX_ENVIRONMENTS,
    DEFAULT_MODEL,
    DEFAULT_VIDEO_ENGINE,
    LUMAAI_API_KEY
)

def generate_video(
    script_text: str,
    model_choice: str = DEFAULT_MODEL,
    video_engine: str = DEFAULT_VIDEO_ENGINE,
    metadata_only: bool = False,
    max_scenes: int = DEFAULT_MAX_SCENES,
    max_environments: int = DEFAULT_MAX_ENVIRONMENTS,
    custom_env_prompt: Optional[str] = None,
    custom_environments: Optional[list] = None,
    skip_narration: bool = False,
    skip_sound_effects: bool = False,
    initial_image_path: Optional[str] = None,
    initial_image_prompt: Optional[str] = None
) -> Tuple[str, Optional[str]]:
    """
    Generate a video based on the provided script text.
    
    Args:
        script_text (str): The input script text
        model_choice (str): The LLM model to use ("gemini" or "claude")
        video_engine (str): The video generation engine to use ("luma" or "ltx")
        metadata_only (bool): Whether to only generate scene metadata without video
        max_scenes (int): Maximum number of scenes to generate
        max_environments (int): Maximum number of unique environments to use
        custom_env_prompt (str, optional): Custom prompt for environment generation
        custom_environments (list, optional): List of predefined environments
        skip_narration (bool): Whether to skip narration generation
        skip_sound_effects (bool): Whether to skip sound effects generation
        initial_image_path (str, optional): Path to initial image file
        initial_image_prompt (str, optional): Prompt to generate initial image
    
    Returns:
        Tuple[str, Optional[str]]: (JSON metadata string, path to final video file)
    """
    try:
        if initial_image_path and initial_image_prompt:
            raise ValueError("Cannot provide both initial_image_path and initial_image_prompt")
            
        if initial_image_prompt and not LUMAAI_API_KEY:
            raise ValueError("Luma AI API key is required for image generation")

        # Generate scene metadata
        scene_generator = SceneGenerator(model=model_choice)
        scenes = scene_generator.generate_scenes(
            script_text,
            max_scenes=max_scenes,
            max_environments=max_environments,
            custom_env_prompt=custom_env_prompt,
            custom_environments=custom_environments,
            video_engine=video_engine
        )
        
        # Return early if only metadata is requested
        if metadata_only:
            return json.dumps([scene.to_dict() for scene in scenes], indent=2), None

        # Generate narration if not skipped
        narration_audio_path = None
        if not skip_narration:
            narration_generator = NarrationGenerator(model=model_choice)
            _, narration_audio_path = narration_generator.generate_narration(scenes)

        # Generate sound effects if not skipped
        sound_effect_files = None
        if not skip_sound_effects:
            sound_generator = SoundGenerator()
            sound_effect_files = sound_generator.generate_sound_effects(scenes)

        # Generate and stitch videos
        video_generator = VideoGenerator(video_engine=video_engine)
        video_files, _ = video_generator.generate_videos(
            scenes,
            initial_image_path=initial_image_path,
            initial_image_prompt=initial_image_prompt
        )
        
        # Create final video
        final_video = video_generator.stitch_final_video(
            video_files,
            sound_effect_files=sound_effect_files,
            narration_audio_path=narration_audio_path
        )

        return json.dumps([scene.to_dict() for scene in scenes], indent=2), final_video

    except Exception as e:
        return str(e), None

def main():
    parser = argparse.ArgumentParser(description='Generate a video based on script analysis')
    parser.add_argument('--model', type=str, choices=['gemini', 'claude'], default=DEFAULT_MODEL,
                       help=f'Model to use for scene generation (default: {DEFAULT_MODEL})')
    parser.add_argument('--video_engine', type=str, choices=['luma', 'ltx'], default=DEFAULT_VIDEO_ENGINE,
                       help=f'Video generation engine to use (default: {DEFAULT_VIDEO_ENGINE})')
    parser.add_argument('--metadata_only', action='store_true',
                       help='Only generate scene metadata JSON without video generation')
    parser.add_argument('--script_file', type=str, default='movie_script2.txt',
                       help='Path to the movie script file (default: movie_script2.txt)')
    parser.add_argument('--skip_narration', action='store_true',
                       help='Skip narration generation')
    parser.add_argument('--skip_sound_effects', action='store_true',
                       help='Skip sound effects generation')
    parser.add_argument('--max_scenes', type=int, default=DEFAULT_MAX_SCENES,
                       help=f'Maximum number of scenes to generate (default: {DEFAULT_MAX_SCENES})')
    parser.add_argument('--max_environments', type=int, default=DEFAULT_MAX_ENVIRONMENTS,
                       help=f'Maximum number of unique environments to use (default: {DEFAULT_MAX_ENVIRONMENTS})')
    parser.add_argument('--initial_image_path', type=str,
                       help='Path to local image to use as starting frame for the first video')
    parser.add_argument('--initial_image_prompt', type=str,
                       help='Prompt to generate initial image using Luma AI for the first video')
    args = parser.parse_args()

    try:
        with open(args.script_file, 'r') as f:
            script = f.read()
    except FileNotFoundError:
        print(f"Error: Script file '{args.script_file}' not found")
        return
    except Exception as e:
        print(f"Error reading script file: {str(e)}")
        return

    metadata, final_video = generate_video(
        script,
        model_choice=args.model,
        video_engine=args.video_engine,
        metadata_only=args.metadata_only,
        max_scenes=args.max_scenes,
        max_environments=args.max_environments,
        skip_narration=args.skip_narration,
        skip_sound_effects=args.skip_sound_effects,
        initial_image_path=args.initial_image_path,
        initial_image_prompt=args.initial_image_prompt
    )

    if args.metadata_only:
        print("Scene metadata JSON:")
        print(metadata)
    elif final_video:
        print(f"Final video saved to: {final_video}")
    else:
        print("Error generating video:", metadata)

if __name__ == "__main__":
    main() 