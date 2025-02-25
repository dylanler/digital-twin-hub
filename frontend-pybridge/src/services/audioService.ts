import { toast } from "@/components/ui/use-toast";

const BACKEND_URL = "http://localhost:8000"; // Update this in production

export interface AudioResponse {
  text_response: string;
  audio_url: string;
}

export interface VoiceCloneResponse {
  voice_id: string;
}

export const audioService = {
  async cloneVoice(audioFile: File): Promise<VoiceCloneResponse> {
    try {
      const formData = new FormData();
      formData.append("audio_file", audioFile);

      const response = await fetch(`${BACKEND_URL}/avatar/clone-voice`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Failed to clone voice");
      }

      return await response.json();
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to clone voice. Please try again.",
        variant: "destructive",
      });
      throw error;
    }
  },

  async generateAvatarVideo(images: File[]): Promise<{ video_url: string }> {
    try {
      const formData = new FormData();
      images.forEach((image) => {
        formData.append("images", image);
      });

      const response = await fetch(`${BACKEND_URL}/avatar/generate-video`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Failed to generate avatar video");
      }

      return await response.json();
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to generate avatar video. Please try again.",
        variant: "destructive",
      });
      throw error;
    }
  },

  async getAgentState(): Promise<{ listening: boolean; speaking: boolean }> {
    const response = await fetch(`${BACKEND_URL}/agent/state`);
    if (!response.ok) {
      throw new Error("Failed to fetch agent state");
    }
    return await response.json();
  },

  async loadAvatarVideo(): Promise<{ videoUrl: string }> {
    try {
      const response = await fetch(`${BACKEND_URL}/load-avatar-video`);
      if (!response.ok) {
        throw new Error("Failed to load avatar video");
      }
      const data = await response.json();
      return { videoUrl: data.videoUrl };
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load avatar video. Please try again.",
        variant: "destructive",
      });
      throw error;
    }
  },
};
