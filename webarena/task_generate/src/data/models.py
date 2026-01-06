"""
Data Models for CuES-WebArena
Defines the core data structures used throughout the pipeline
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid


class Triplet(BaseModel):
    """Triplet data structure (observation, action, next_observation)
    
    Represents a single step in the exploration trajectory.
    """
    triplet_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    env_id: str = ""  # Environment/Task ID
    session_id: Optional[str] = None
    
    # Core triplet data
    observation: str  # Current page state (AXTree or HTML)
    action: str  # Action taken
    next_observation: str  # Resulting page state
    
    # Additional metadata
    url: str = ""  # Current URL
    reward: float = 0.0
    done: bool = False
    step_number: int = 0
    
    # LLM response
    llm_response: Optional[str] = None
    
    # Timestamp
    timestamp: datetime = Field(default_factory=datetime.now)
    
    # Exploration memory at this step
    exploration_memory: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dict"""
        if hasattr(self, 'model_dump'):
            return self.model_dump()
        else:
            return self.dict()


class Task(BaseModel):
    """Task abstracted from triplets
    
    Represents a concrete task that can be used for agent training.
    """
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    env_id: str = ""  # Environment/Task ID
    session_id: Optional[str] = None
    
    # Task definition
    description: str  # Natural language task description
    query: str  # Task query for the agent
    
    # Ground truth and action sequence
    action_sequence: List[str] = []  # Sequence of actions to complete the task
    ground_truth: Optional[str] = None  # Expected outcome
    
    # Source information
    source_triplets: List[str] = []  # IDs of source triplets
    
    # Quality metrics
    confidence: float = 1.0  # Abstraction confidence
    difficulty: str = "medium"  # easy, medium, hard
    
    # Metadata
    website: str = ""  # Website type
    category: str = ""  # Task category
    timestamp: datetime = Field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """Convert to dict"""
        if hasattr(self, 'model_dump'):
            return self.model_dump()
        else:
            return self.dict()


class TrajectoryStep(BaseModel):
    """Single step in a trajectory"""
    step_number: int
    observation: str
    action: str
    next_observation: str
    reward: float = 0.0
    done: bool = False
    llm_response: Optional[str] = None
    url: str = ""


class Trajectory(BaseModel):
    """Complete trajectory for a task
    
    Represents the full execution trace of a task.
    """
    trajectory_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    task_id: str
    env_id: str = ""
    session_id: Optional[str] = None
    
    # Task information
    description: str
    query: str
    ground_truth: Optional[str] = None
    
    # Trajectory steps
    steps: List[TrajectoryStep] = []
    
    # Outcome
    success: bool = False
    final_reward: float = 0.0
    reason: str = ""  # Success/failure reason
    
    # Metadata
    total_steps: int = 0
    strategy: str = "simple"  # simple, reflection
    timestamp: datetime = Field(default_factory=datetime.now)
    
    # Messages for training
    messages: List[Dict[str, str]] = []
    
    def to_dict(self) -> dict:
        """Convert to dict"""
        if hasattr(self, 'model_dump'):
            return self.model_dump()
        else:
            return self.dict()


class Session(BaseModel):
    """Session data for a pipeline run"""
    session_id: str = Field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3])
    
    # Configuration
    config: Dict[str, Any] = {}
    
    # Results
    triplets_count: int = 0
    tasks_count: int = 0
    trajectories_count: int = 0
    
    # Status
    status: str = "running"  # running, completed, failed
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    # Statistics
    statistics: Dict[str, Any] = {}
    
    def to_dict(self) -> dict:
        """Convert to dict"""
        if hasattr(self, 'model_dump'):
            return self.model_dump()
        else:
            return self.dict()
