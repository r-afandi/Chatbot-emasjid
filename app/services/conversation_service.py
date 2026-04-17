from typing import List, Dict, Optional
from datetime import datetime
import json
import os
from uuid import uuid4
from app.models.schemas import Conversation
from app.core.config import settings

class ConversationService:
    def __init__(self):
        # Create conversations directory if it doesn't exist
        self.conversations_dir = os.path.join(settings.FILE_STORAGE_PATH, "conversations")
        if not os.path.exists(self.conversations_dir):
            os.makedirs(self.conversations_dir)
    
    def create_conversation(self, user_id: str) -> str:
        """Create a new conversation and return its ID"""
        conversation_id = str(uuid4())
        
        conversation = Conversation(
            id=conversation_id,
            user_id=user_id,
            messages=[],
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        self._save_conversation(conversation)
        return conversation_id
    
    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Retrieve a conversation by ID"""
        file_path = os.path.join(self.conversations_dir, f"{conversation_id}.json")
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                data = json.load(f)
                # Convert datetime strings back to datetime objects
                data["created_at"] = datetime.fromisoformat(data["created_at"])
                data["updated_at"] = datetime.fromisoformat(data["updated_at"])
                return Conversation(**data)
        return None
    
    def add_message(self, conversation_id: str, message: Dict[str, str]) -> bool:
        """Add a message to a conversation"""
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return False
        
        conversation.messages.append(message)
        conversation.updated_at = datetime.now()
        self._save_conversation(conversation)
        return True
    
    def get_conversation_history(self, conversation_id: str, limit: int = 10) -> List[Dict[str, str]]:
        """Get recent messages from a conversation"""
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return []
        
        # Return last N messages
        return conversation.messages[-limit:] if conversation.messages else []
    
    def _save_conversation(self, conversation: Conversation):
        """Save conversation to file"""
        file_path = os.path.join(self.conversations_dir, f"{conversation.id}.json")
        
        # Convert datetime objects to strings for JSON serialization
        data = conversation.dict()
        data["created_at"] = data["created_at"].isoformat()
        data["updated_at"] = data["updated_at"].isoformat()
        
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

# Initialize the conversation service
conversation_service = ConversationService()