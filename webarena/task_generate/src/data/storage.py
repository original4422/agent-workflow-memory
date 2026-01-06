"""
Data Storage for CuES-WebArena
Handles persistence and retrieval of triplets, tasks, and trajectories
"""
import json
import jsonlines
import os
from typing import List, Dict, Set, Optional
from datetime import datetime
from pathlib import Path

from .models import Triplet, Task, Trajectory
from ..utils.logger import get_logger

logger = get_logger(__name__)


class DataStorage:
    """Manages data persistence for the CuES pipeline"""
    
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        
        # Create directories
        for subdir in ["triplets", "tasks", "trajectories", "sessions", "memories"]:
            (self.base_dir / subdir).mkdir(parents=True, exist_ok=True)
        
        # Indices for fast lookup
        self.env_triplet_index: Dict[str, Set[Path]] = {}
        self.env_task_index: Dict[str, Set[Path]] = {}
        
        # Build indices on initialization
        self._build_indices()
    
    def _build_indices(self):
        """Build indices from env_id to file paths"""
        # Triplet index
        triplets_dir = self.base_dir / "triplets"
        if triplets_dir.exists():
            for file_path in triplets_dir.glob("*.jsonl"):
                self._index_triplet_file(file_path)
        
        # Task index
        tasks_dir = self.base_dir / "tasks"
        if tasks_dir.exists():
            for file_path in tasks_dir.glob("*.jsonl"):
                self._index_task_file(file_path)
    
    def _index_triplet_file(self, file_path: Path):
        """Index a triplet file by env_id"""
        try:
            with jsonlines.open(file_path, mode='r') as reader:
                for obj in reader:
                    env_id = obj.get('env_id')
                    if env_id:
                        if env_id not in self.env_triplet_index:
                            self.env_triplet_index[env_id] = set()
                        self.env_triplet_index[env_id].add(file_path)
        except Exception as e:
            logger.error(f"Error indexing triplet file {file_path}: {e}")
    
    def _index_task_file(self, file_path: Path):
        """Index a task file by env_id"""
        try:
            with jsonlines.open(file_path, mode='r') as reader:
                for obj in reader:
                    env_id = obj.get('env_id')
                    if env_id:
                        if env_id not in self.env_task_index:
                            self.env_task_index[env_id] = set()
                        self.env_task_index[env_id].add(file_path)
        except Exception as e:
            logger.error(f"Error indexing task file {file_path}: {e}")
    
    # ==================== Triplet Operations ====================
    
    def save_triplet(self, triplet: Triplet, session_id: Optional[str] = None):
        """Save a single triplet"""
        session_id = session_id or triplet.session_id or "default"
        filename = f"triplets_{session_id}.jsonl"
        filepath = self.base_dir / "triplets" / filename
        
        triplet_dict = triplet.to_dict()
        triplet_dict['timestamp'] = str(triplet_dict['timestamp'])
        
        with jsonlines.open(filepath, mode='a') as writer:
            writer.write(triplet_dict)
        
        # Update index
        env_id = triplet.env_id
        if env_id:
            if env_id not in self.env_triplet_index:
                self.env_triplet_index[env_id] = set()
            self.env_triplet_index[env_id].add(filepath)
    
    def save_triplets(self, triplets: List[Triplet], session_id: str):
        """Save multiple triplets"""
        for triplet in triplets:
            self.save_triplet(triplet, session_id)
    
    def get_triplets_by_env_id(self, env_id: str) -> List[Triplet]:
        """Get all triplets for an environment"""
        triplets = []
        
        file_paths = self.env_triplet_index.get(env_id, set())
        for file_path in file_paths:
            try:
                with jsonlines.open(file_path, mode='r') as reader:
                    for obj in reader:
                        if obj.get('env_id') == env_id:
                            if 'timestamp' in obj and isinstance(obj['timestamp'], str):
                                obj['timestamp'] = datetime.fromisoformat(obj['timestamp'])
                            triplets.append(Triplet(**obj))
            except Exception as e:
                logger.error(f"Error reading triplet file {file_path}: {e}")
        
        return triplets
    
    def load_triplets_from_file(self, file_path: str) -> List[Triplet]:
        """Load triplets from a specific file"""
        triplets = []
        path = Path(file_path)
        
        if not path.exists():
            logger.error(f"Triplet file not found: {file_path}")
            return triplets
        
        try:
            with jsonlines.open(path, mode='r') as reader:
                for obj in reader:
                    if 'timestamp' in obj and isinstance(obj['timestamp'], str):
                        obj['timestamp'] = datetime.fromisoformat(obj['timestamp'])
                    triplets.append(Triplet(**obj))
        except Exception as e:
            logger.error(f"Error loading triplets from {file_path}: {e}")
        
        return triplets
    
    # ==================== Task Operations ====================
    
    def save_task(self, task: Task, session_id: Optional[str] = None):
        """Save a single task"""
        session_id = session_id or task.session_id or "default"
        filename = f"tasks_{session_id}.jsonl"
        filepath = self.base_dir / "tasks" / filename
        
        task_dict = task.to_dict()
        task_dict['timestamp'] = str(task_dict['timestamp'])
        
        with jsonlines.open(filepath, mode='a') as writer:
            writer.write(task_dict)
        
        # Update index
        env_id = task.env_id
        if env_id:
            if env_id not in self.env_task_index:
                self.env_task_index[env_id] = set()
            self.env_task_index[env_id].add(filepath)
    
    def save_tasks(self, tasks: List[Task], session_id: str):
        """Save multiple tasks"""
        for task in tasks:
            self.save_task(task, session_id)
    
    def get_tasks_by_env_id(self, env_id: str) -> List[Task]:
        """Get all tasks for an environment"""
        tasks = []
        
        file_paths = self.env_task_index.get(env_id, set())
        for file_path in file_paths:
            try:
                with jsonlines.open(file_path, mode='r') as reader:
                    for obj in reader:
                        if obj.get('env_id') == env_id:
                            if 'timestamp' in obj and isinstance(obj['timestamp'], str):
                                obj['timestamp'] = datetime.fromisoformat(obj['timestamp'])
                            tasks.append(Task(**obj))
            except Exception as e:
                logger.error(f"Error reading task file {file_path}: {e}")
        
        return tasks
    
    def load_tasks_from_file(self, file_path: str) -> List[Task]:
        """Load tasks from a specific file"""
        tasks = []
        path = Path(file_path)
        
        if not path.exists():
            logger.error(f"Task file not found: {file_path}")
            return tasks
        
        try:
            with jsonlines.open(path, mode='r') as reader:
                for obj in reader:
                    if 'timestamp' in obj and isinstance(obj['timestamp'], str):
                        obj['timestamp'] = datetime.fromisoformat(obj['timestamp'])
                    tasks.append(Task(**obj))
        except Exception as e:
            logger.error(f"Error loading tasks from {file_path}: {e}")
        
        return tasks
    
    # ==================== Trajectory Operations ====================
    
    def save_trajectory(self, trajectory: Trajectory, failed: bool = False):
        """Save a trajectory"""
        if failed:
            output_dir = self.base_dir / "trajectories" / "failed"
        else:
            output_dir = self.base_dir / "trajectories"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"trajectory_{trajectory.task_id}.json"
        filepath = output_dir / filename
        
        traj_dict = trajectory.to_dict()
        traj_dict['timestamp'] = str(traj_dict['timestamp'])
        
        # Convert TrajectoryStep objects to dicts
        if 'steps' in traj_dict:
            traj_dict['steps'] = [
                s.to_dict() if hasattr(s, 'to_dict') else s 
                for s in traj_dict['steps']
            ]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(traj_dict, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved trajectory to {filepath}")
    
    def load_trajectories(self, include_failed: bool = False) -> List[Trajectory]:
        """Load all trajectories"""
        trajectories = []
        
        # Load successful trajectories
        traj_dir = self.base_dir / "trajectories"
        for filepath in traj_dir.glob("trajectory_*.json"):
            if "failed" not in str(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if 'timestamp' in data and isinstance(data['timestamp'], str):
                        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
                    trajectories.append(Trajectory(**data))
                except Exception as e:
                    logger.error(f"Error loading trajectory {filepath}: {e}")
        
        # Load failed trajectories if requested
        if include_failed:
            failed_dir = self.base_dir / "trajectories" / "failed"
            if failed_dir.exists():
                for filepath in failed_dir.glob("trajectory_*.json"):
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        if 'timestamp' in data and isinstance(data['timestamp'], str):
                            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
                        trajectories.append(Trajectory(**data))
                    except Exception as e:
                        logger.error(f"Error loading trajectory {filepath}: {e}")
        
        return trajectories
    
    # ==================== Memory Operations ====================
    
    def save_memory(self, env_id: str, memory_type: str, content: str):
        """Save exploration memory"""
        memory_dir = self.base_dir / "memories"
        memory_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{env_id}_{memory_type}.txt"
        filepath = memory_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def load_memory(self, env_id: str, memory_type: str) -> Optional[str]:
        """Load exploration memory"""
        filepath = self.base_dir / "memories" / f"{env_id}_{memory_type}.txt"
        
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        
        return None
