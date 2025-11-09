from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional
import json

@dataclass
class Job:
    """Job data model"""
    id: str
    command: str
    state: str = "pending"  # pending, processing, completed, failed, dead
    attempts: int = 0
    max_retries: int = 3
    created_at: str = None
    updated_at: str = None
    last_error: Optional[str] = None
    next_retry_at: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat() + "Z"
        if self.updated_at is None:
            self.updated_at = datetime.utcnow().isoformat() + "Z"
    
    def to_dict(self):
        """Convert job to dictionary"""
        return asdict(self)
    
    def to_json(self):
        """Convert job to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create job from dictionary"""
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str):
        """Create job from JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)
