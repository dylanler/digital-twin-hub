import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Video generation configuration
LUMA_VIDEO_GENERATION_DURATION_OPTIONS = [5, 9, 14, 18]  # Duration in seconds

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
LUMAAI_API_KEY = os.getenv("LUMAAI_API_KEY")
ELEVEN_LABS_API_KEY = os.getenv("ELEVEN_LABS_API_KEY")

# Default values
DEFAULT_MAX_SCENES = 5
DEFAULT_MAX_ENVIRONMENTS = 3
DEFAULT_MODEL = "gemini"
DEFAULT_VIDEO_ENGINE = "luma"

# Video directory format
VIDEO_DIR_FORMAT = "generated_videos/video_{timestamp}" 