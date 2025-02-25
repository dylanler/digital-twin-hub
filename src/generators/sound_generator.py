import os
from typing import List, Optional
from elevenlabs import ElevenLabs
from ..models.scene_metadata import SceneMetadata
from ..config import ELEVEN_LABS_API_KEY, VIDEO_DIR_FORMAT

class SoundGenerator:
    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.video_dir = VIDEO_DIR_FORMAT.format(timestamp=self.timestamp)
        self.eleven_labs_client = ElevenLabs(api_key=ELEVEN_LABS_API_KEY)

    def generate_sound_effects(
        self,
        scenes: List[SceneMetadata]
    ) -> List[Optional[str]]:
        """
        Generate sound effects for each scene.
        Returns a list of paths to the generated sound effect files.
        """
        sound_effect_files = []
        
        for scene in scenes:
            scene_dir = f"{self.video_dir}/scene_{scene.scene_number}_all_vid_{self.timestamp}"
            os.makedirs(scene_dir, exist_ok=True)
            
            sound_effect_path = f"{scene_dir}/scene_{scene.scene_number}_sound.mp3"
            print(f"Generating sound effect for Scene {scene.scene_number}")
            
            try:
                sound_effect_generator = self.eleven_labs_client.text_to_sound_effects.convert(
                    text=scene.sound_effects_prompt,
                    duration_seconds=scene.scene_duration,
                    prompt_influence=0.5
                )
                
                with open(sound_effect_path, 'wb') as f:
                    for chunk in sound_effect_generator:
                        if chunk is not None:
                            f.write(chunk)
                
                sound_effect_files.append(sound_effect_path)
                print(f"Sound effect saved to: {sound_effect_path}")
                
            except Exception as e:
                print(f"Failed to generate sound effect: {e}")
                sound_effect_files.append(None)
        
        return sound_effect_files 