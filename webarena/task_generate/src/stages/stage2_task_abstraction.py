"""
Stage 2: Task Abstraction
Abstract concrete tasks from exploration triplets using LLM.
"""
from typing import List, Dict, Any, Optional
import re

from ..core.api_client import APIClient
from ..core.memory_manager import MemoryManager
from ..data.models import Triplet, Task
from ..data.storage import DataStorage
from ..prompts.task_abstraction import TaskAbstractionPrompts
from ..utils.logger import get_logger

logger = get_logger(__name__)


class Stage2TaskAbstraction:
    """Stage 2: Abstract tasks from exploration triplets"""
    
    def __init__(
        self,
        client: APIClient,
        env_config: Dict[str, Any],
        min_confidence: float = 0.6,
        min_action_length: int = 3,
        storage: DataStorage = None,
        session_id: Optional[str] = None
    ):
        self.client = client
        self.env_config = env_config
        self.min_confidence = min_confidence
        self.min_action_length = min_action_length
        self.storage = storage
        self.session_id = session_id
        
        # Initialize memory manager
        if storage:
            self.memory_manager = MemoryManager(storage, client)
        else:
            self.memory_manager = None
        
        # Prompt builder
        self.prompts = TaskAbstractionPrompts()
    
    def run(self, triplets: List[Triplet], batch_size: int = 10) -> List[Task]:
        """Run Stage 2 task abstraction"""
        if not triplets:
            logger.warning("No triplets provided for task abstraction")
            return []
        
        logger.info(f"Starting task abstraction, processing {len(triplets)} triplets")
        
        # Group triplets by env_id
        env_groups = {}
        for triplet in triplets:
            env_id = triplet.env_id
            if env_id not in env_groups:
                env_groups[env_id] = []
            env_groups[env_id].append(triplet)
        
        # Process each group
        all_tasks = []
        batch_num = 1
        
        for env_id, env_triplets in env_groups.items():
            logger.info(f"Processing {len(env_triplets)} triplets from env {env_id}")
            
            # Process in batches
            for i in range(0, len(env_triplets), batch_size):
                batch = env_triplets[i:i + batch_size]
                
                tasks = self._extract_tasks_from_batch(batch, batch_num, env_id)
                tasks = self._filter_and_deduplicate(tasks)
                
                all_tasks.extend(tasks)
                batch_num += 1
        
        logger.info(f"Stage 2 completed, abstracted {len(all_tasks)} tasks")
        return all_tasks
    
    def _extract_tasks_from_batch(
        self,
        triplets: List[Triplet],
        batch_num: int,
        env_id: str
    ) -> List[Task]:
        """Extract tasks from a batch of triplets"""
        logger.info(f"Processing batch {batch_num} with {len(triplets)} triplets")
        
        try:
            # Convert triplets to dicts for prompt
            triplet_dicts = []
            for triplet in triplets:
                triplet_dicts.append({
                    'observation': triplet.observation[:1000],  # Truncate
                    'action': triplet.action,
                    'next_observation': triplet.next_observation[:500],
                    'url': triplet.url,
                    'step_number': triplet.step_number
                })
            
            # Get environment description (first observation)
            env_description = triplets[0].observation if triplets else ""
            
            # Get task memory
            task_memory = None
            if self.memory_manager:
                task_memory = self.memory_manager.get_task_memory(env_id)
            
            # Build prompt
            website = self.env_config.get('website', 'shopping_admin')
            system_prompt, user_prompt = self.prompts.build_task_extraction_prompt(
                triplets=triplet_dicts,
                env_description=env_description,
                task_memory=task_memory,
                website=website
            )
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # Call LLM
            response = self.client.chat_with_retry(messages, max_retries=3)
            
            if not response:
                logger.warning(f"No response for batch {batch_num}")
                return []
            
            # Parse tasks from response
            task_infos = self.prompts.parse_tasks(response)
            
            # Create Task objects
            tasks = []
            for task_info in task_infos:
                # Filter by confidence and action length
                confidence = task_info.get('confidence', 0.5)
                action_sequence = task_info.get('action_sequence', [])
                
                if confidence < self.min_confidence:
                    continue
                
                if len(action_sequence) < self.min_action_length:
                    continue
                
                task = Task(
                    env_id=env_id,
                    session_id=self.session_id,
                    description=task_info.get('description', ''),
                    query=task_info.get('query', ''),
                    action_sequence=action_sequence,
                    ground_truth=task_info.get('ground_truth', ''),
                    source_triplets=[t.triplet_id for t in triplets],
                    confidence=confidence,
                    difficulty=task_info.get('difficulty', 'medium'),
                    website=website,
                    category=task_info.get('category', '')
                )
                tasks.append(task)
                
                # Save task
                if self.storage:
                    self.storage.save_task(task, self.session_id)
            
            logger.info(f"Batch {batch_num} produced {len(tasks)} valid tasks")
            return tasks
            
        except Exception as e:
            logger.error(f"Task extraction failed for batch {batch_num}: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _filter_and_deduplicate(self, tasks: List[Task]) -> List[Task]:
        """Filter and deduplicate tasks"""
        if not tasks:
            return []
        
        # Sort by confidence (descending)
        tasks.sort(key=lambda x: x.confidence, reverse=True)
        
        # Deduplicate based on query similarity
        unique_tasks = []
        seen_queries = set()
        
        for task in tasks:
            normalized_query = task.query.lower().strip()
            
            # Check for similar queries
            is_duplicate = False
            for seen_query in seen_queries:
                if self._queries_similar(normalized_query, seen_query):
                    is_duplicate = True
                    break
            
            # Skip if no query or ground truth
            if not task.query or not task.description:
                is_duplicate = True
            
            if not is_duplicate:
                unique_tasks.append(task)
                seen_queries.add(normalized_query)
        
        return unique_tasks
    
    def _queries_similar(self, query1: str, query2: str, threshold: float = 0.7) -> bool:
        """Check if two queries are similar using Jaccard similarity"""
        words1 = set(query1.split())
        words2 = set(query2.split())
        
        if not words1 or not words2:
            return False
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        similarity = intersection / union if union > 0 else 0
        return similarity >= threshold
    
    def get_statistics(self, tasks: List[Task]) -> Dict[str, Any]:
        """Get task statistics"""
        if not tasks:
            return {}
        
        confidences = [t.confidence for t in tasks]
        
        return {
            'total_tasks': len(tasks),
            'avg_confidence': sum(confidences) / len(confidences),
            'max_confidence': max(confidences),
            'min_confidence': min(confidences),
            'high_confidence_tasks': sum(1 for c in confidences if c >= 0.8),
            'by_difficulty': {
                'easy': sum(1 for t in tasks if t.difficulty == 'easy'),
                'medium': sum(1 for t in tasks if t.difficulty == 'medium'),
                'hard': sum(1 for t in tasks if t.difficulty == 'hard')
            }
        }
