import os
import requests
import time
from dotenv import load_dotenv
from lumaai import LumaAI

class LumaVideoGenerator:
    def __init__(self):
        load_dotenv()
        self.api_key = os.environ.get("LUMAAI_API_KEY")
        if not self.api_key:
            raise ValueError("LUMAAI_API_KEY environment variable is not set. Please set it in your .env file or environment.")
        self.client = LumaAI(auth_token=self.api_key)

    def generate_video(self, prompt, output_path, image_path=None, image_url=None, aspect_ratio="16:9", resolution="540p", duration="5s"):
        """
        Generate a video using Luma AI.
        
        Args:
            prompt (str): Text prompt describing the video
            output_path (str): Path where the generated video will be saved
            image_path (str, optional): Path to local image file to use as starting frame
            image_url (str, optional): URL of image to use as starting frame
            aspect_ratio (str, optional): Aspect ratio of the video (default: "16:9")
            resolution (str, optional): Video resolution (default: "540p")
            duration (str, optional): Video duration in seconds with 's' suffix (default: "5s")
        
        Returns:
            dict: Generation result containing video URL and other metadata
        """
        print(f"Starting video generation for {output_path}...")

        # Ensure output directory exists first
        if not output_path:
            raise ValueError("output_path cannot be empty")
            
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Prepare generation parameters
        generation_params = {
            "prompt": prompt,
            "model": "ray-2", 
            "resolution": resolution,
            "duration": duration
        }

        # Handle image input
        if image_url:
            print(f"Using provided image URL: {image_url}")
            generation_params["keyframes"] = {
                "frame0": {
                    "type": "image",
                    "url": image_url
                }
            }
        elif image_path:
            # Upload the image to Luma's server if image path is provided
            try:
                with open(image_path, 'rb') as f:
                    # Use GCP uploader to get image URL
                    uploader = GCPImageUploader()
                    image_url = uploader.upload_image(image_path)
                    if not image_url:
                        raise ValueError("Failed to get URL from GCP upload")
                    
                    print(f"Image uploaded successfully to GCP. URL: {image_url}")
                    generation_params["keyframes"] = {
                        "frame0": {
                            "type": "image",
                            "url": image_url
                        }
                    }
            except Exception as e:
                print(f"Failed to upload image: {str(e)}")
                # Continue without image if upload fails

        # Create generation
        try:
            generation = self.client.generations.create(**generation_params)
            
            # Wait for completion with timeout
            start_time = time.time()
            timeout = 300  # 5 minutes timeout
            
            while True:
                if time.time() - start_time > timeout:
                    raise TimeoutError("Video generation timed out after 5 minutes")
                
                generation = self.client.generations.get(id=generation.id)
                if generation.state == "completed":
                    break
                elif generation.state == "failed":
                    raise RuntimeError(f"Generation failed: {generation.failure_reason}")
                print("Dreaming...")
                time.sleep(3)
            
            # Download the video
            print(f"Downloading video to {output_path}...")
            response = requests.get(generation.assets.video, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            
            print(f"Video generated and saved to {output_path}")
            return {
                "video_url": generation.assets.video,
                "state": generation.state,
                "id": generation.id
            }
            
        except Exception as e:
            raise RuntimeError(f"Failed to generate video: {str(e)}")

# Example usage
if __name__ == "__main__":
    generator = LumaVideoGenerator()
    
    # Example 1: Text-to-video
    generator.generate_video(
        prompt="A beautiful sunset over a calm ocean, with gentle waves lapping at a sandy beach.",
        output_path="generated_videos/ocean_video.mp4",
        duration="5s"
    )
    
    # # Example 2: Image-to-video with local file
    # generator.generate_video(
    #     prompt="A serene mountain landscape transforming through the seasons.",
    #     image_path="mountain.jpg",
    #     output_path="mountain_video.mp4",
    #     duration="5s"
    # )
    
    # # Example 3: Image-to-video with URL
    # generator.generate_video(
    #     prompt="A bustling cityscape coming to life as day turns to night.",
    #     image_url="https://example.com/city.jpg",
    #     output_path="city_video.mp4",
    #     duration="5s"
    # ) 