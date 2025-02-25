
import { toast } from "@/components/ui/use-toast";

const BACKEND_URL = "http://localhost:8000";

export const movieService = {
  async generateMovie(zipFile: File, prompt: string): Promise<{ video_url: string }> {
    try {
      const formData = new FormData();
      formData.append("zip_file", zipFile);
      formData.append("prompt", prompt);

      const response = await fetch(`${BACKEND_URL}/movie/generate`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Failed to generate movie");
      }

      return await response.json();
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to generate movie. Please try again.",
        variant: "destructive",
      });
      throw error;
    }
  }
};
