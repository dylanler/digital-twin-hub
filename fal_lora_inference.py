import os
import requests
import fal_client
from dotenv import load_dotenv

class FalLoraInference:
    def __init__(self):
        load_dotenv()
        self.fal_key = os.getenv('FAL_KEY')
        fal_client.api_key = self.fal_key

    def on_queue_update(self, update):
        if isinstance(update, fal_client.InProgress):
            for log in update.logs:
                print(log["message"])

    def generate_image(self, prompt, lora_path, scale=1, image_size="landscape_16_9"):
        """Generate an image using the Fal AI Flux LoRA model.

        Args:
            prompt (str): The prompt to generate an image from.
            lora_path (str): Path to the LoRA weights file.
            scale (float, optional): The scale factor for LoRA. Defaults to 1.
            image_size (str or dict, optional): The size of the generated image. 
                Can be one of: square_hd, square, portrait_4_3, portrait_16_9, 
                landscape_4_3, landscape_16_9. 
                Or a dict with width and height: {"width": 1280, "height": 720}.
                Defaults to "landscape_16_9".

        Returns:
            dict: The generation result containing the image URL and metadata.
        """
        result = fal_client.subscribe(
            "fal-ai/flux-lora",
            arguments={
                "prompt": prompt,
                "model_name": None,
                "loras": [{
                    "path": lora_path,
                    "scale": scale
                }],
                "embeddings": [],
                "enable_safety_checker": False,
                "image_size": image_size
            },
            with_logs=True,
            on_queue_update=self.on_queue_update,
        )
        return result

    def download_image(self, image_url, output_path):
        response = requests.get(image_url)
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            print(f"Image downloaded and saved to {output_path}")
        else:
            print(f"Failed to download image. Status code: {response.status_code}")

    def run_inference(self, prompt, lora_path, output_path):
        result = self.generate_image(prompt, lora_path)
        if 'images' in result and len(result['images']) > 0:
            image_url = result['images'][0]['url']
            self.download_image(image_url, output_path)
            return result
        else:
            print("No image generated in the result.")
            return None

def main():
    inference = FalLoraInference()
    prompt = "man wearing BEANIECEREBRALHACKS smiling at camera, hiking in yosemite zoomed out, camera pans outwards"
    lora_path = "https://storage.googleapis.com/fal-flux-lora/e03bb17fd82945c8a73dc40aaae65733_pytorch_lora_weights.safetensors"
    output_path = "generated_image.jpg"

    result = inference.run_inference(prompt, lora_path, output_path)
    if result:
        print("Image generation successful!")
        print(f"Seed: {result['seed']}")
        print(f"Inference time: {result['timings']['inference']} seconds")
        print(f"NSFW content detected: {result['has_nsfw_concepts'][0]}")
    else:
        print("Image generation failed.")

if __name__ == "__main__":
    main()