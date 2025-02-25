from dataclasses import dataclass
from typing import List, Optional

@dataclass
class SceneMetadata:
    scene_number: int
    scene_name: str
    scene_physical_environment: str
    scene_movement_description: str
    scene_emotions: str
    scene_camera_movement: str
    scene_duration: int
    sound_effects_prompt: str
    previous_scene_movement_description: Optional[str] = None
    previous_scene_emotions: Optional[str] = None
    previous_scene_camera_movement: Optional[str] = None
    previous_scene_duration: Optional[int] = None
    previous_scene_sound_effects_prompt: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> 'SceneMetadata':
        return cls(**data)

    def to_dict(self) -> dict:
        return {
            key: value for key, value in self.__dict__.items()
            if value is not None
        }

    def get_video_prompt(self) -> str:
        return f"""
        {self.scene_physical_environment}
        
        Movement and Action:
        {self.scene_movement_description}
        
        Emotional Atmosphere:
        {self.scene_emotions}
        
        Camera Instructions:
        {self.scene_camera_movement}
        """ 