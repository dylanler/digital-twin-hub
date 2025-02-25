import os
import shutil
import time
import cv2
import requests
from typing import List, Tuple, Optional
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip, CompositeVideoClip
from lumaai import LumaAI
from ..models.scene_metadata import SceneMetadata
from ..config import (
    LUMAAI_API_KEY,
    LUMA_VIDEO_GENERATION_DURATION_OPTIONS,
    VIDEO_DIR_FORMAT
)
from img_bucket import GCPImageUploader
from ltx_video_generation import generate_ltx_video
from luma_image_gen import generate_image

class VideoGenerator:
    def __init__(self, video_engine: str = "luma"):
        self.video_engine = video_engine
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.video_dir = VIDEO_DIR_FORMAT.format(timestamp=self.timestamp)
        self.uploader = GCPImageUploader()
        
        if video_engine == "luma":
            self.luma_client = LumaAI(auth_token=LUMAAI_API_KEY)

    def _get_video_durations(self, scene_duration: int) -> List[int]:
        """Determine video durations based on scene duration"""
        if self.video_engine == "ltx":
            return [5]
        elif scene_duration == 5 or scene_duration == 9:
            return [scene_duration]
        elif scene_duration == 14:
            return [5, 9]
        elif scene_duration == 18:
            return [9, 9]
        else:
            raise ValueError(f"Invalid scene duration: {scene_duration}")

    def _extract_last_frame(self, video_path: str, frame_path: str) -> bool:
        """Extract the last frame from a video file"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video file: {video_path}")
        
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_count-1)
        ret, frame = cap.read()
        
        if ret:
            cv2.imwrite(frame_path, frame)
            print(f"Successfully extracted last frame to: {frame_path}")
            success = True
        else:
            print(f"Failed to extract last frame from video: {video_path}")
            success = False
        
        cap.release()
        return success

    def generate_videos(
        self,
        scenes: List[SceneMetadata],
        initial_image_path: Optional[str] = None,
        initial_image_prompt: Optional[str] = None
    ) -> Tuple[List[str], List[str]]:
        """
        Generate videos for each scene.
        Returns a tuple of (list of video file paths, list of scene directories).
        """
        scene_video_files = []
        scene_dirs = []
        last_frame_url = None
        first_frame_of_first_scene_url = None

        # Handle initial image if provided
        if initial_image_path or initial_image_prompt:
            if initial_image_path and os.path.exists(initial_image_path):
                # Copy the provided image to video directory
                os.makedirs(self.video_dir, exist_ok=True)
                shutil.copy2(initial_image_path, self.video_dir)
                first_frame_of_first_scene_url = self.uploader.upload_image(initial_image_path)
                
            elif initial_image_prompt:
                # Generate image using Luma AI
                try:
                    image_url, _ = generate_image(initial_image_prompt, self.video_dir)
                    if image_url:
                        first_frame_of_first_scene_url = image_url
                except Exception as e:
                    print(f"Warning: Failed to generate initial image: {str(e)}")

        for i, scene in enumerate(scenes):
            print(f"Generating videos for Scene {scene.scene_number}")
            scene_dir = f"{self.video_dir}/scene_{scene.scene_number}_all_vid_{self.timestamp}"
            os.makedirs(scene_dir, exist_ok=True)
            scene_dirs.append(scene_dir)
            
            scene_videos = []
            video_durations = self._get_video_durations(scene.scene_duration)
            segment_last_frame_url = None

            for vid_idx, duration in enumerate(video_durations, 1):
                # Use different naming convention based on number of videos in scene
                if len(video_durations) == 1:
                    video_path = f"{scene_dir}/scene_{scene.scene_number}_{self.timestamp}.mp4"
                else:
                    video_path = f"{scene_dir}/scene_{scene.scene_number}_vid_{vid_idx}_{self.timestamp}.mp4"

                if self.video_engine == "ltx":
                    # For LTX, use last frame URL as image input if available
                    ltx_args = {
                        "prompt": scene.get_video_prompt(),
                        "output_path": video_path
                    }
                    if vid_idx == 1 and i == 0 and first_frame_of_first_scene_url:
                        ltx_args["image_url"] = first_frame_of_first_scene_url
                    elif vid_idx == 1 and i > 0 and last_frame_url:
                        ltx_args["image_url"] = last_frame_url
                    elif vid_idx > 1 and segment_last_frame_url:
                        ltx_args["image_url"] = segment_last_frame_url

                    try:
                        generate_ltx_video(**ltx_args)
                        if not os.path.exists(video_path):
                            raise RuntimeError("LTX video generation failed to save the video file")
                    except Exception as e:
                        raise RuntimeError(f"LTX video generation failed: {str(e)}")

                else:  # Luma
                    generation_params = {
                        "prompt": scene.get_video_prompt(),
                        "model": "ray-2",
                        "resolution": "720p",
                        "duration": f"{duration}s"
                    }

                    # Add keyframe parameters based on available frames
                    if vid_idx == 1 and i == 0 and first_frame_of_first_scene_url:
                        generation_params["keyframes"] = {
                            "frame0": {"type": "image", "url": first_frame_of_first_scene_url}
                        }
                    elif vid_idx == 1 and i > 0 and last_frame_url:
                        generation_params["keyframes"] = {
                            "frame0": {"type": "image", "url": last_frame_url}
                        }
                    elif vid_idx > 1 and segment_last_frame_url:
                        generation_params["keyframes"] = {
                            "frame0": {"type": "image", "url": segment_last_frame_url}
                        }

                    # Generate video
                    generation = self.luma_client.generations.create(**generation_params)

                    # Wait for completion
                    while True:
                        generation = self.luma_client.generations.get(id=generation.id)
                        if generation.state == "completed":
                            break
                        elif generation.state == "failed":
                            raise RuntimeError(f"Generation failed: {generation.failure_reason}")
                        print("Dreaming...")
                        time.sleep(3)

                    # Download video
                    response = requests.get(generation.assets.video, stream=True)
                    with open(video_path, 'wb') as file:
                        file.write(response.content)

                scene_videos.append(video_path)

                # Extract and upload last frame
                if len(video_durations) == 1:
                    frame_path = f"{scene_dir}/scene_{scene.scene_number}_last_frame.jpg"
                else:
                    frame_path = f"{scene_dir}/scene_{scene.scene_number}_vid_{vid_idx}_last_frame.jpg"

                if self._extract_last_frame(video_path, frame_path):
                    # Upload frame and get URL
                    max_retries = 3
                    retry_count = 0
                    while retry_count < max_retries:
                        new_frame_url = self.uploader.upload_image(frame_path)
                        if new_frame_url != segment_last_frame_url:
                            if vid_idx == len(video_durations):  # If this is the last video in the scene
                                last_frame_url = new_frame_url  # Save for next scene
                            else:
                                segment_last_frame_url = new_frame_url  # Save for next video in this scene
                            break
                        print(f"Got duplicate URL, retrying... (attempt {retry_count + 1}/{max_retries})")
                        time.sleep(2)
                        retry_count += 1

                    if retry_count == max_retries:
                        raise RuntimeError(f"Failed to get unique frame URL for video {vid_idx} in scene {scene.scene_number}")

            # Stitch videos for this scene if there are multiple
            if len(scene_videos) > 1:
                scene_clips = [VideoFileClip(video) for video in scene_videos]
                scene_final = concatenate_videoclips(scene_clips)
                scene_final_path = f"{self.video_dir}/scene_{scene.scene_number}_{self.timestamp}.mp4"
                scene_final.write_videofile(scene_final_path)
                
                # Close clips
                for clip in scene_clips:
                    clip.close()
                
                scene_video_files.append(scene_final_path)
            else:
                # Copy the single video to the main directory
                single_video_path = scene_videos[0]
                final_video_path = f"{self.video_dir}/scene_{scene.scene_number}_{self.timestamp}.mp4"
                shutil.copy2(single_video_path, final_video_path)
                scene_video_files.append(final_video_path)

            time.sleep(2)

        return scene_video_files, scene_dirs

    def stitch_final_video(
        self,
        video_files: List[str],
        sound_effect_files: Optional[List[str]] = None,
        narration_audio_path: Optional[str] = None
    ) -> str:
        """
        Stitch together all video files with sound effects and narration.
        Returns the path to the final video file.
        """
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
                
                final_clips.append(video_clip)
            except Exception as e:
                print(f"Warning: Failed to process video {video_file}: {str(e)}")
                continue
        
        if not final_clips:
            raise RuntimeError("No video clips were successfully processed")
        
        # Concatenate all clips
        final_clip = concatenate_videoclips(final_clips)
        
        # Add narration audio if provided
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
        output_path = f"{self.video_dir}/final_video_{self.timestamp}.mp4"
        final_clip.write_videofile(output_path)
        
        # Close all clips
        for clip in final_clips:
            clip.close()
        
        return output_path 