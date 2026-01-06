"""
CuES-WebArena Core Pipeline
Coordinates the execution of the three stages:
- Stage 1: Curious Exploration
- Stage 2: Task Abstraction
- Stage 3: Trajectory Generation
"""
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from .api_client import APIClient
from ..data.models import Triplet, Task, Session
from ..data.storage import DataStorage
from ..utils.logger import get_logger

logger = get_logger(__name__)


class CuESPipeline:
    """Main CuES pipeline for WebArena task generation"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.base_dir = Path(__file__).parent.parent.parent
        
        # Initialize API client
        api_config = config.get('api', {})
        self.client = APIClient(
            api_key=api_config.get('api_key'),
            model_name=api_config.get('model_name', 'openai/gpt-4o'),
            temperature=api_config.get('temperature', 0.7),
            max_tokens=api_config.get('max_tokens', 4096),
            azure_endpoint=api_config.get('azure_endpoint'),
            api_version=api_config.get('api_version')
        )
        
        # Initialize data storage
        data_dir = self.base_dir / config.get('data_dir', './data')
        self.storage = DataStorage(str(data_dir))
        
        # Session ID
        self.session_id = None
        
        # Lazy initialization of stages
        self._stage1 = None
        self._stage2 = None
        self._stage3 = None
    
    @property
    def stage1(self):
        """Lazily initialize Stage 1"""
        if self._stage1 is None:
            from ..stages.stage1_exploration import Stage1Exploration
            stage1_config = self.config.get('stage1', {})
            env_config = self.config.get('environment', {})
            
            self._stage1 = Stage1Exploration(
                client=self.client,
                env_config=env_config,
                max_steps=stage1_config.get('max_steps', 20),
                storage=self.storage,
                session_id=self.session_id,
                use_memory=stage1_config.get('use_memory', True)
            )
        return self._stage1
    
    @property
    def stage2(self):
        """Lazily initialize Stage 2"""
        if self._stage2 is None:
            from ..stages.stage2_task_abstraction import Stage2TaskAbstraction
            stage2_config = self.config.get('stage2', {})
            env_config = self.config.get('environment', {})
            
            self._stage2 = Stage2TaskAbstraction(
                client=self.client,
                env_config=env_config,
                min_confidence=stage2_config.get('min_confidence', 0.6),
                min_action_length=stage2_config.get('min_action_length', 3),
                storage=self.storage,
                session_id=self.session_id
            )
        return self._stage2
    
    @property
    def stage3(self):
        """Lazily initialize Stage 3"""
        if self._stage3 is None:
            from ..stages.stage3_trajectory_generation import Stage3TrajectoryGeneration
            stage3_config = self.config.get('stage3', {})
            env_config = self.config.get('environment', {})
            
            self._stage3 = Stage3TrajectoryGeneration(
                client=self.client,
                env_config=env_config,
                max_steps=stage3_config.get('max_steps', 25),
                storage=self.storage,
                session_id=self.session_id,
                use_reflection=stage3_config.get('use_reflection', False)
            )
        return self._stage3
    
    def _init_session(self, session_name: Optional[str] = None) -> str:
        """Initialize a new session"""
        self.session_id = session_name or datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        logger.info(f"Initialized session: {self.session_id}")
        return self.session_id
    
    def extract_concepts(self, max_workers: int = 4) -> List[str]:
        """Extract concept set from the environment (Stage 0)"""
        logger.info("Extracting concept set from WebArena environment...")
        
        env_config = self.config.get('environment', {})
        website = env_config.get('website', 'shopping_admin')
        
        # Use LLM to generate relevant concepts for the website
        system_prompt = """You are an expert at understanding web applications and their functionalities.
Given a website type, generate a list of important concepts, features, and actions that an agent should explore."""
        
        user_prompt = f"""Generate a list of 20-30 key concepts and features for a {website} website that an AI agent should explore.
Focus on:
1. Common user actions (e.g., search, filter, add to cart)
2. Page types (e.g., product page, checkout page)
3. UI elements (e.g., navigation menu, forms)
4. Business functionalities (e.g., order management, inventory)

Output as a JSON array of strings, e.g.: ["concept1", "concept2", ...]"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = self.client.chat_with_retry(messages, max_retries=2)
            if response:
                # Parse JSON array from response
                import re
                json_match = re.search(r'\[.*?\]', response, re.DOTALL)
                if json_match:
                    concepts = json.loads(json_match.group())
                    logger.info(f"Extracted {len(concepts)} concepts")
                    return concepts
        except Exception as e:
            logger.warning(f"Failed to extract concepts: {e}")
        
        # Return default concepts based on website type
        default_concepts = {
            "shopping_admin": [
                "product management", "order processing", "customer accounts",
                "inventory control", "price management", "category browsing",
                "search functionality", "report generation", "dashboard navigation"
            ],
            "shopping": [
                "product search", "add to cart", "checkout process",
                "user login", "wishlist", "product filtering",
                "review reading", "category navigation", "order history"
            ],
            "gitlab": [
                "repository creation", "issue tracking", "merge requests",
                "code review", "project settings", "user management",
                "CI/CD pipelines", "branch management", "wiki editing"
            ],
            "reddit": [
                "post creation", "commenting", "voting",
                "subreddit browsing", "user profile", "search",
                "content filtering", "subscription management"
            ],
            "map": [
                "location search", "directions", "route planning",
                "place details", "map navigation", "distance calculation",
                "landmark finding", "address lookup"
            ]
        }
        
        return default_concepts.get(website, default_concepts["shopping_admin"])
    
    def run_full_pipeline(
        self,
        session_name: Optional[str] = None,
        requirement: Optional[str] = None,
        concepts: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run the complete three-stage pipeline"""
        start_time = time.time()
        
        # Initialize session
        self._init_session(session_name)
        
        result = {
            'success': False,
            'session_id': self.session_id,
            'triplets_count': 0,
            'tasks_count': 0,
            'trajectories_count': 0,
            'statistics': {}
        }
        
        try:
            # Stage 1: Curious Exploration
            logger.info("=== Stage 1: Curious Exploration ===")
            stage1_config = self.config.get('stage1', {})
            rollout_num = stage1_config.get('rollout_num', 3)
            
            triplets = self.stage1.run(
                rollout_num=rollout_num,
                requirement=requirement,
                concepts=concepts
            )
            result['triplets_count'] = len(triplets)
            
            if not triplets:
                result['error'] = "Stage 1 produced no triplets"
                return result
            
            logger.info(f"Stage 1 completed: {len(triplets)} triplets generated")
            
            # Stage 2: Task Abstraction
            logger.info("=== Stage 2: Task Abstraction ===")
            stage2_config = self.config.get('stage2', {})
            batch_size = stage2_config.get('batch_size', 10)
            
            tasks = self.stage2.run(triplets, batch_size=batch_size)
            result['tasks_count'] = len(tasks)
            
            if not tasks:
                result['error'] = "Stage 2 produced no tasks"
                return result
            
            logger.info(f"Stage 2 completed: {len(tasks)} tasks abstracted")
            
            # Stage 3: Trajectory Generation
            logger.info("=== Stage 3: Trajectory Generation ===")
            
            task_dicts = [task.to_dict() for task in tasks]
            stage3_result = self.stage3.run(task_dicts)
            
            result['trajectories_count'] = stage3_result['statistics']['successful']
            result['statistics'] = {
                'triplets': self._compute_triplet_stats(triplets),
                'tasks': self._compute_task_stats(tasks),
                'trajectories': {
                    'success_rate': stage3_result['statistics']['successful'] / 
                                  max(stage3_result['statistics']['total_tasks'], 1),
                    'total': stage3_result['statistics']['total_tasks'],
                    'successful': stage3_result['statistics']['successful'],
                    'failed': stage3_result['statistics']['failed']
                }
            }
            
            result['success'] = True
            result['elapsed_time'] = time.time() - start_time
            
            # Save session
            self._save_session(result)
            
            logger.info(f"Pipeline completed in {result['elapsed_time']:.2f}s")
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            logger.error(traceback.format_exc())
            result['error'] = str(e)
        
        return result
    
    def run_stage1(
        self,
        session_name: Optional[str] = None,
        requirement: Optional[str] = None,
        concepts: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run only Stage 1: Curious Exploration"""
        self._init_session(session_name)
        
        result = {
            'success': False,
            'session_id': self.session_id,
            'triplets_count': 0
        }
        
        try:
            stage1_config = self.config.get('stage1', {})
            rollout_num = stage1_config.get('rollout_num', 3)
            
            triplets = self.stage1.run(
                rollout_num=rollout_num,
                requirement=requirement,
                concepts=concepts
            )
            
            result['triplets_count'] = len(triplets)
            result['success'] = True
            result['output_file'] = str(self.storage.base_dir / "triplets" / f"triplets_{self.session_id}.jsonl")
            
        except Exception as e:
            logger.error(f"Stage 1 failed: {e}")
            result['error'] = str(e)
        
        return result
    
    def run_stage2(
        self,
        input_file: str,
        session_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run only Stage 2: Task Abstraction"""
        self._init_session(session_name)
        
        result = {
            'success': False,
            'session_id': self.session_id,
            'tasks_count': 0
        }
        
        try:
            # Load triplets from file
            triplets = self.storage.load_triplets_from_file(input_file)
            
            if not triplets:
                result['error'] = f"No triplets found in {input_file}"
                return result
            
            stage2_config = self.config.get('stage2', {})
            batch_size = stage2_config.get('batch_size', 10)
            
            tasks = self.stage2.run(triplets, batch_size=batch_size)
            
            result['tasks_count'] = len(tasks)
            result['success'] = True
            result['output_file'] = str(self.storage.base_dir / "tasks" / f"tasks_{self.session_id}.jsonl")
            
        except Exception as e:
            logger.error(f"Stage 2 failed: {e}")
            result['error'] = str(e)
        
        return result
    
    def run_stage3(
        self,
        input_file: str,
        session_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run only Stage 3: Trajectory Generation"""
        self._init_session(session_name)
        
        result = {
            'success': False,
            'session_id': self.session_id,
            'trajectories_count': 0,
            'statistics': {}
        }
        
        try:
            # Load tasks from file
            tasks = self.storage.load_tasks_from_file(input_file)
            
            if not tasks:
                result['error'] = f"No tasks found in {input_file}"
                return result
            
            task_dicts = [task.to_dict() if hasattr(task, 'to_dict') else task for task in tasks]
            stage3_result = self.stage3.run(task_dicts)
            
            result['trajectories_count'] = stage3_result['statistics']['successful']
            result['statistics'] = {
                'success_rate': stage3_result['statistics']['successful'] / 
                              max(stage3_result['statistics']['total_tasks'], 1),
                'total': stage3_result['statistics']['total_tasks'],
                'successful': stage3_result['statistics']['successful'],
                'failed': stage3_result['statistics']['failed']
            }
            result['success'] = True
            
        except Exception as e:
            logger.error(f"Stage 3 failed: {e}")
            result['error'] = str(e)
        
        return result
    
    def run_query_rewrite(
        self,
        trajectories_dir: str,
        batch_size: int = 10,
        num_variants: int = 3,
        session_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run Query Rewrite on generated trajectories"""
        from ..stages.query_rewrite import QueryRewriter
        
        rewriter = QueryRewriter(self.client)
        
        result = rewriter.run(
            trajectories_dir=trajectories_dir,
            batch_size=batch_size,
            num_variants=num_variants,
            output_dir=str(self.storage.base_dir / "rewrites")
        )
        
        result['session_name'] = session_name
        return result
    
    def _compute_triplet_stats(self, triplets: List[Triplet]) -> Dict[str, Any]:
        """Compute statistics for triplets"""
        if not triplets:
            return {}
        
        rewards = [t.reward for t in triplets]
        success_count = sum(1 for t in triplets if t.done)
        
        return {
            'count': len(triplets),
            'avg_reward': sum(rewards) / len(rewards) if rewards else 0,
            'max_reward': max(rewards) if rewards else 0,
            'success_rate': success_count / len(triplets)
        }
    
    def _compute_task_stats(self, tasks: List[Task]) -> Dict[str, Any]:
        """Compute statistics for tasks"""
        if not tasks:
            return {}
        
        confidences = [t.confidence for t in tasks]
        high_conf_count = sum(1 for c in confidences if c >= 0.8)
        
        return {
            'count': len(tasks),
            'avg_confidence': sum(confidences) / len(confidences),
            'max_confidence': max(confidences),
            'min_confidence': min(confidences),
            'high_confidence_tasks': high_conf_count
        }
    
    def _save_session(self, result: Dict[str, Any]):
        """Save session information"""
        session_file = self.storage.base_dir / "sessions" / f"session_{self.session_id}.json"
        session_file.parent.mkdir(parents=True, exist_ok=True)
        
        session_data = {
            'session_id': self.session_id,
            'timestamp': datetime.now().isoformat(),
            'config': self.config,
            'result': result
        }
        
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, indent=2, default=str)
        
        logger.info(f"Session saved to {session_file}")


import traceback
