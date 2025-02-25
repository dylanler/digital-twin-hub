import os
import json
from typing import List, Tuple, Optional
from google import genai
import anthropic
from moviepy.editor import AudioFileClip
from eleven_labs_tts import generate_speech
from ..models.scene_metadata import SceneMetadata
from ..config import (
    GEMINI_API_KEY,
    ANTHROPIC_API_KEY,
    VIDEO_DIR_FORMAT
)

class NarrationGenerator:
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

    def calculate_total_duration(self, scenes: List[SceneMetadata]) -> int:
        """Calculate total duration of all scenes in seconds"""
        return sum(scene.scene_duration for scene in scenes)

    def generate_narration_text(
        self,
        scenes: List[SceneMetadata],
        total_duration: int
    ) -> Tuple[str, str]:
        """
        Generate narration text based on the scene metadata and desired duration.
        Returns the narration text and the path to the saved text file.
        """
        scene_descriptions = []
        for scene in scenes:
            description = f"""
            {scene.scene_name}:
            Environment: {scene.scene_physical_environment}
            Action: {scene.scene_movement_description}
            Emotional Atmosphere: {scene.scene_emotions}
            Camera Movement: {scene.scene_camera_movement}
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
        
        if self.model == "gemini":
            response = self.gemini_client.models.generate_content(
                model="gemini-2.0-flash-001",
                contents=[combined_description, prompt],
                config={
                    'temperature': 0.7,
                    'top_p': 0.8,
                    'top_k': 40
                }
            )
            narration = response.text
        else:
            response = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=8192,
                temperature=0.7,
                system="You are an expert at writing engaging narration scripts.",
                messages=[{"role": "user", "content": f"{combined_description}\n\n{prompt}"}]
            )
            narration = response.content[0].text
        
        # Save narration text
        os.makedirs(self.video_dir, exist_ok=True)
        narration_path = os.path.join(self.video_dir, f'narration_text_{self.timestamp}.txt')
        with open(narration_path, 'w') as f:
            f.write(narration)
        
        return narration, narration_path

    def generate_narration_audio(
        self,
        narration_text: str,
        target_duration: int
    ) -> Optional[str]:
        """
        Generate audio narration from text and adjust its speed to match target duration.
        Returns the path to the processed audio file.
        """
        try:
            # Generate initial audio using ElevenLabs
            audio_path = os.path.join(self.video_dir, f'narration_audio_{self.timestamp}.mp3')
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
            adjusted_audio_path = os.path.join(self.video_dir, f'narration_audio_adjusted_{self.timestamp}.mp3')
            adjusted_audio.write_audiofile(adjusted_audio_path, fps=44100)  # Use standard sample rate
            
            # Clean up
            audio.close()
            adjusted_audio.close()
            
            return adjusted_audio_path
            
        except Exception as e:
            print(f"Error generating narration audio: {str(e)}")
            return None

    def generate_narration(
        self,
        scenes: List[SceneMetadata]
    ) -> Tuple[str, Optional[str]]:
        """
        Generate both narration text and audio.
        Returns the narration text and the path to the audio file.
        """
        total_duration = self.calculate_total_duration(scenes)
        narration_text, text_path = self.generate_narration_text(scenes, total_duration)
        audio_path = self.generate_narration_audio(narration_text, total_duration)
        return narration_text, audio_path 