
import { RequestPanel } from "@/components/RequestPanel";
import { Button } from "@/components/ui/button";
import { Mic } from "lucide-react";
import { useNavigate } from "react-router-dom";

const Index = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-50 p-4 sm:p-8">
      <div className="max-w-7xl mx-auto space-y-8">
        <header className="text-center space-y-4">
          <h1 className="text-4xl font-bold tracking-tight">Movie Generator</h1>
          <p className="text-muted-foreground">
            Upload a ZIP file and provide a prompt to generate your movie
          </p>
          <Button 
            onClick={() => navigate('/audio')}
            variant="outline"
            size="lg"
            className="mx-auto"
          >
            <Mic className="mr-2 h-4 w-4" />
            Try AI Avatar Interface
          </Button>
        </header>
        
        <main>
          <RequestPanel />
        </main>
      </div>
    </div>
  );
};

export default Index;
