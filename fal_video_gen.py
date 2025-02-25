import os
import requests
import time
import fal_client
from dotenv import load_dotenv

class FalVideoGenerator:
    def __init__(self):
        load_dotenv()
        self.api_key = os.environ.get("FAL_API_KEY")
        if not self.api_key:
            raise ValueError("FAL_API_KEY environment variable is not set. Please set it in your .env file or environment.")
        fal_client.api_key = self.api_key

    def on_queue_update(self, update):
        if isinstance(update, fal_client.InProgress):
            for log in update.logs:
                print(log["message"])

    def generate_video(self, prompt, output_path, image_path=None, aspect_ratio="16:9", resolution="540p", duration="9s", loop=False):
        print(f"Starting video generation for {output_path}...")

        # Prepare arguments based on whether image is provided
        arguments = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "duration": duration,
            "loop": loop
        }

        if image_url:
            # Use provided image URL directly
            print(f"Using provided image URL: {image_url}")
            arguments["image_url"] = image_url
            model_path = "fal-ai/luma-dream-machine/ray-2/image-to-video"
        elif image_path:
            # Upload the image to FAL's server if image path is provided
            image_url = fal_client.upload_file(image_path)
            print(f"Image uploaded successfully. URL: {image_url}")
            arguments["image_url"] = image_url
            model_path = "fal-ai/luma-dream-machine/ray-2/image-to-video"
        else:
            # Use text-to-video model if no image is provided
            model_path = "fal-ai/luma-dream-machine/ray-2"

        # Create generation with appropriate Luma model
        result = fal_client.subscribe(
            model_path,
            arguments=arguments,
            with_logs=True,
            on_queue_update=self.on_queue_update,
        )
        print(f"Generation completed. Result: {result}")

        # Get video URL from the completed generation
        video_url = result.get('video', {}).get('url')
        if not video_url:
            raise Exception(f"Video URL not found in the generation response for {output_path}")

        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Download the video
        print(f"Downloading video to {output_path}...")
        response = requests.get(video_url, stream=True)
        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192
        downloaded = 0

        with open(output_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=block_size):
                file.write(chunk)
                downloaded += len(chunk)
                progress = (downloaded / total_size) * 100
                print(f"Download progress for {output_path}: {progress:.2f}%", end='\r')
        
        print(f"\nVideo generated and saved to {output_path}")

# Example usage
if __name__ == "__main__":
    generator = FalVideoGenerator()
    
    # Example 1: Text-to-video
    generator.generate_video(
        prompt="A herd of wild horses galloping across a dusty desert plain under a blazing midday sun, their manes flying in the wind; filmed in a wide tracking shot with dynamic motion, warm natural lighting, and an epic.",
        output_path="horses_video.mp4",
        aspect_ratio="16:9",
        resolution="540p",
        duration="5s"
    )

    # Example 2: Image-to-video with local file
    generator.generate_video(
        prompt="A stylish woman walks down a Tokyo street filled with warm glowing neon and animated city signage.",
        image_path="tokyo_street.jpg",
        output_path="tokyo_street_video.mp4",
        aspect_ratio="16:9",
        resolution="540p",
        duration="5s"
    )

    # Example 3: Image-to-video with URL
    generator.generate_video(
        prompt="A stylish woman walks down a Tokyo street filled with warm glowing neon and animated city signage.",
        image_url="https://example.com/tokyo_street.jpg",
        output_path="tokyo_street_url_video.mp4",
        aspect_ratio="16:9",
        resolution="540p",
        duration="5s"
    )
