import axios from 'axios';

const API_URL = 'http://localhost:8000';
const AGENT_ID = 'XOpQx4GrwSHb7DHolt46';
const DEFAULT_VOICE_ID = 'yk6z5D05U7ccflgendsD';

export const conversationService = {
  toggleConversation: async (voiceId?: string) => {
    try {
      const response = await axios.post(`${API_URL}/toggle-conversation/`, {
        agent_id: AGENT_ID,
        voice_id: voiceId || DEFAULT_VOICE_ID
      });
      return response.data;
    } catch (error) {
      console.error('Error toggling conversation:', error);
      throw error;
    }
  }
}; 