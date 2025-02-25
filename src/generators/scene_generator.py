import os
import json
from datetime import datetime
from typing import List, Tuple, Optional, Dict
from google import genai
import anthropic
from ..models.scene_metadata import SceneMetadata
from ..config import (
    GEMINI_API_KEY,
    ANTHROPIC_API_KEY,
    LUMA_VIDEO_GENERATION_DURATION_OPTIONS,
    VIDEO_DIR_FORMAT
)

class SceneGenerator:
    def __init__(self, model: str = "gemini"):
        self.model = model
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.video_dir = VIDEO_DIR_FORMAT.format(timestamp=self.timestamp)
        
        if model == "gemini":
            self.gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        elif model == "claude":
            self.claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        else:
            raise ValueError(f"Unsupported model: {model}")

    def _determine_optimal_scenes(self, script: str, max_scenes: int) -> int:
        prompt = f"""
        Analyze this movie script and determine the optimal number of scenes needed to tell the story effectively.
        Consider that:
        - Each scene is {LUMA_VIDEO_GENERATION_DURATION_OPTIONS} seconds long
        - Scenes should maintain visual continuity
        - The story should flow naturally
        - Complex actions may need multiple scenes
        - The story should be told in a way that is engaging and interesting to watch
        - Maximum number of scenes is {max_scenes}
        - Scene should not have racist, sexist elements
        - Scene should be artistically pleasing and creative
        Return only a single integer representing the optimal number of scenes. No explanation is needed.
        """
        
        if self.model == "gemini":
            response = self.gemini_client.models.generate_content(
                model="gemini-2.0-flash-001",
                contents=[script, prompt],
                config={
                    'temperature': 0.7,
                    'top_p': 0.8,
                    'top_k': 40
                }
            )
            return min(int(response.text.strip()), max_scenes)
        else:
            response = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=100,
                temperature=0.7,
                system="You are an expert at analyzing scripts and determining optimal scene counts.",
                messages=[{"role": "user", "content": f"{script}\n\n{prompt}"}]
            )
            return min(int(response.content[0].text.strip()), max_scenes)

    def generate_physical_environments(
        self,
        num_scenes: int,
        script: str,
        max_environments: int = 3,
        custom_prompt: Optional[str] = None,
        custom_environments: Optional[List[Dict[str, str]]] = None
    ) -> Tuple[List[Dict[str, str]], str]:
        if custom_environments is not None:
            json_path = os.path.join(self.video_dir, f'scene_physical_environment_{self.timestamp}.json')
            os.makedirs(os.path.dirname(json_path), exist_ok=True)
            with open(json_path, 'w') as f:
                json.dump(custom_environments, f, indent=2)
            return custom_environments, json_path

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

        if self.model == "gemini":
            response = self.gemini_client.models.generate_content(
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
        else:
            response = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=8192,
                temperature=0.7,
                system="You are an expert at describing physical environments for video scenes.",
                messages=[{
                    "role": "user",
                    "content": f"{script}\n\n{prompt}"
                }]
            )
            environments = json.loads(response.content[0].text)["environments"]

        os.makedirs(self.video_dir, exist_ok=True)
        json_path = os.path.join(self.video_dir, f'scene_physical_environment_{self.timestamp}.json')
        with open(json_path, 'w') as f:
            json.dump(environments, f, indent=2)

        return environments, json_path

    def generate_metadata_without_environment(
        self,
        num_scenes: int,
        script: str,
        video_engine: str = "luma"
    ) -> Tuple[List[Dict], str]:
        prompt = f"""
        Create a JSON array of {num_scenes} detailed scene descriptions based on the movie script. Each scene should include:
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
        6. Take into account the previous scene's movement description, emotions, camera movement, and sound effects prompt when creating the next scene's movement description, emotions, camera movement, and sound effects prompt.
        7. The first scene should have no previous scene movement description, emotions, camera movement, and sound effects prompt, enter string "none".
        8. Scene duration must be selected from these options: {LUMA_VIDEO_GENERATION_DURATION_OPTIONS if video_engine == "luma" else "[5]"} (in seconds)
        """

        if self.model == "gemini":
            response = self.gemini_client.models.generate_content(
                model="gemini-2.0-flash-001",
                contents=[script, prompt],
                config={
                    'response_mime_type': 'application/json',
                    'temperature': 0.7,
                    'top_p': 0.8,
                    'top_k': 40
                }
            )
            metadata = response.parsed
        else:
            response = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=8192,
                temperature=0.7,
                system="You are an expert at creating detailed scene descriptions.",
                messages=[{"role": "user", "content": f"{script}\n\n{prompt}"}]
            )
            metadata = json.loads(response.content[0].text)["scenes"]

        json_path = os.path.join(self.video_dir, f'scene_metadata_no_env_{self.timestamp}.json')
        with open(json_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        return metadata, json_path

    def combine_metadata_with_environment(
        self,
        num_scenes: int,
        script: str,
        metadata_path: str,
        environments_path: str
    ) -> List[SceneMetadata]:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        with open(environments_path, 'r') as f:
            environments = json.load(f)

        prompt = f"""
        Given a list of {num_scenes} scene metadata and a list of physical environments, select the most appropriate physical environment 
        for each scene to ensure scene continuity in the physical environment of the video.
        
        Return: array of complete scene descriptions, each containing all metadata fields plus the selected physical environment.
        """

        if self.model == "gemini":
            response = self.gemini_client.models.generate_content(
                model="gemini-2.0-flash-001",
                contents=[script, json.dumps(metadata), json.dumps(environments), prompt],
                config={
                    'response_mime_type': 'application/json',
                    'temperature': 0.7,
                    'top_p': 0.8,
                    'top_k': 40
                }
            )
            final_metadata = response.parsed
        else:
            response = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=8192,
                temperature=0.7,
                system="You are an expert at combining scene metadata with appropriate physical environments.",
                messages=[{
                    "role": "user",
                    "content": f"{script}\n\n{json.dumps(metadata)}\n\n{json.dumps(environments)}\n\n{prompt}"
                }]
            )
            final_metadata = json.loads(response.content[0].text)["scenes"]

        # Convert to SceneMetadata objects
        return [SceneMetadata.from_dict(scene) for scene in final_metadata]

    def generate_scenes(
        self,
        script: str,
        max_scenes: int = 5,
        max_environments: int = 3,
        custom_env_prompt: Optional[str] = None,
        custom_environments: Optional[List[Dict[str, str]]] = None,
        video_engine: str = "luma"
    ) -> List[SceneMetadata]:
        num_scenes = self._determine_optimal_scenes(script, max_scenes)
        environments, env_path = self.generate_physical_environments(
            num_scenes,
            script,
            max_environments,
            custom_env_prompt,
            custom_environments
        )
        metadata, metadata_path = self.generate_metadata_without_environment(num_scenes, script, video_engine)
        return self.combine_metadata_with_environment(num_scenes, script, metadata_path, env_path) 