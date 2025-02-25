
import { useState } from "react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { useToast } from "./ui/use-toast";
import { Loader2, Upload } from "lucide-react";

export const RequestPanel = () => {
  const [prompt, setPrompt] = useState("");
  const [zipFile, setZipFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const { toast } = useToast();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && file.type === "application/zip") {
      setZipFile(file);
    } else {
      toast({
        title: "Invalid file type",
        description: "Please upload a .zip file",
        variant: "destructive",
      });
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || !zipFile) {
      toast({
        title: "Missing information",
        description: "Please provide both a ZIP file and a text prompt",
        variant: "destructive",
      });
      return;
    }

    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("zip", zipFile);
      formData.append("prompt", prompt);

      const response = await fetch("YOUR_API_ENDPOINT", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("Request failed");

      const data = await response.json();
      setVideoUrl(data.videoUrl); // Assuming your backend returns a video URL

      toast({
        title: "Success",
        description: "Video generated successfully",
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to process your request",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
      <Card className="glass p-6 animate-fade-up">
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <label className="text-sm font-medium">Upload ZIP File</label>
            <div className="flex items-center justify-center w-full">
              <label className="w-full flex flex-col items-center px-4 py-6 bg-white/50 rounded-lg border-2 border-dashed border-gray-300 cursor-pointer hover:bg-white/60 transition-colors">
                <Upload className="h-8 w-8 text-gray-500 mb-2" />
                <span className="text-sm text-gray-500">
                  {zipFile ? zipFile.name : "Drop your ZIP file here"}
                </span>
                <input
                  type="file"
                  className="hidden"
                  accept=".zip"
                  onChange={handleFileChange}
                />
              </label>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Enter Prompt</label>
            <Textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Enter your prompt here..."
              className="min-h-[120px] resize-none"
            />
          </div>

          <Button disabled={loading} className="w-full">
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Processing...
              </>
            ) : (
              "Generate Video"
            )}
          </Button>
        </form>
      </Card>

      <Card className="glass p-6 animate-fade-up">
        <div className="space-y-4">
          <h3 className="text-lg font-medium">Generated Video</h3>
          <div className="aspect-video rounded-lg bg-black/10 flex items-center justify-center">
            {videoUrl ? (
              <video
                src={videoUrl}
                controls
                className="w-full h-full rounded-lg"
              >
                Your browser does not support the video tag.
              </video>
            ) : (
              <p className="text-muted-foreground">
                Video will appear here after generation
              </p>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
};
