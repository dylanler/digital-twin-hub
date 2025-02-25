import { useState, useEffect, useRef } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";
import { AudioWaveform, Copy, MessageSquare, Play, Pause, Loader2, Mic } from "lucide-react";
import { audioService } from "@/services/audioService";
import { conversationService } from "@/services/conversationService";

const AudioInterface = () => {
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [isCloning, setIsCloning] = useState(false);
  const [cloningFinished, setCloningFinished] = useState(false);
  const [isConversationActive, setIsConversationActive] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [voiceId, setVoiceId] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const websocketRef = useRef<WebSocket | null>(null);
  const { toast } = useToast();
  const [avatarVideoUrl, setAvatarVideoUrl] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      // Cleanup WebSocket on component unmount
      if (websocketRef.current) {
        websocketRef.current.close();
      }
    };
  }, []);

  const handleAudioUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && file.type.startsWith("audio/")) {
      setAudioFile(file);
      setCloningFinished(false); // Reset cloning status when new file is uploaded
    } else {
      toast({
        title: "Invalid file type",
        description: "Please upload an audio file",
        variant: "destructive",
      });
    }
  };

  const handleCloneVoice = async () => {
    if (!audioFile) {
      toast({
        title: "No audio file",
        description: "Please upload an audio file first",
        variant: "destructive",
      });
      return;
    }

    setIsCloning(true);
    setCloningFinished(false);
    try {
      const response = await audioService.cloneVoice(audioFile);
      setVoiceId(response.voice_id);
      setCloningFinished(true);
      toast({
        title: "Success",
        description: "Voice cloned successfully",
      });
    } catch (error) {
      console.error("Error cloning voice:", error);
    } finally {
      setIsCloning(false);
    }
  };

  const toggleConversation = async () => {
    try {
      const response = await conversationService.toggleConversation(voiceId || undefined);
      setIsConversationActive(response.is_active);
      if (response.is_active) {
        const videoUrl = await audioService.loadAvatarVideo();
        setAvatarVideoUrl(videoUrl.videoUrl);
      } else {
        setAvatarVideoUrl(null);
      }
      
      toast({
        title: response.is_active ? "Conversation started" : "Conversation ended",
        description: response.message,
      });
    } catch (error) {
      console.error("Error toggling conversation:", error);
      toast({
        title: "Error",
        description: "Failed to toggle conversation",
        variant: "destructive",
      });
    }
  };

  const handleAIVideoControl = (command: "play" | "pause") => {
    const videoElement = document.querySelector("video");
    if (videoElement) {
      if (command === "play") {
        videoElement.play();
        setIsPlaying(true);
      } else {
        videoElement.pause();
        setIsPlaying(false);
      }
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-50 p-4 sm:p-8">
      <div className="max-w-7xl mx-auto space-y-8">
        <header className="text-center space-y-4">
          <h1 className="text-4xl font-bold tracking-tight">AI Avatar Interface</h1>
          <p className="text-muted-foreground">
            Upload audio to create your AI avatar and start a conversation
          </p>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <Card className="glass p-6 animate-fade-up">
            <div className="space-y-6">
              <div className="space-y-2">
                <label className="text-sm font-medium">Upload Audio File</label>
                <div className="flex items-center justify-center w-full">
                  <label className="w-full flex flex-col items-center px-4 py-6 bg-white/50 rounded-lg border-2 border-dashed border-gray-300 cursor-pointer hover:bg-white/60 transition-colors">
                    <AudioWaveform className="h-8 w-8 text-gray-500 mb-2" />
                    <span className="text-sm text-gray-500">
                      {audioFile ? audioFile.name : "Drop your audio file here"}
                    </span>
                    <input
                      type="file"
                      className="hidden"
                      accept="audio/*"
                      onChange={handleAudioUpload}
                    />
                  </label>
                </div>
              </div>

              <Button
                onClick={handleCloneVoice}
                disabled={isCloning || !audioFile}
                className="w-full"
              >
                {isCloning ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Cloning Voice...
                  </>
                ) : cloningFinished ? (
                  <>
                    <Copy className="mr-2 h-4 w-4" />
                    Cloning Finished
                  </>
                ) : (
                  <>
                    <Copy className="mr-2 h-4 w-4" />
                    Clone Voice
                  </>
                )}
              </Button>

              <Button
                onClick={toggleConversation}
                variant={isConversationActive ? "destructive" : "default"}
                className="w-full"
              >
                {isRecording ? <Mic className="mr-2 h-4 w-4 animate-pulse" /> : <MessageSquare className="mr-2 h-4 w-4" />}
                {isConversationActive ? "End Conversation" : "Start Conversation"}
              </Button>
            </div>
          </Card>

          <Card className="glass p-6 animate-fade-up">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium">AI Video Output</h3>
                {avatarVideoUrl && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    {/* {isPlaying ? (
                      <Pause className="h-4 w-4" />
                    ) : (
                      <Play className="h-4 w-4" />
                    )}
                    {isPlaying ? "Playing" : "Paused"} */}
                  </div>
                )}
              </div>
              <div className="aspect-video rounded-lg bg-black/10 flex items-center justify-center">
                {avatarVideoUrl ? (
                  <video
                    src={avatarVideoUrl}
                    className="w-full h-full rounded-lg"
                    autoPlay
                    loop
                  >
                    Your browser does not support the video tag.
                  </video>
                ) : (
                  <p className="text-muted-foreground">
                    Video will appear here during conversation
                  </p>
                )}
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default AudioInterface;
