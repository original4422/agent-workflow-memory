"""
Memory Manager for CuES-WebArena
Manages exploration memory to guide curious exploration and avoid repetition
"""
import json
from typing import List, Dict, Any, Optional
from pathlib import Path

from ..data.models import Triplet, Task
from ..data.storage import DataStorage
from ..utils.logger import get_logger

logger = get_logger(__name__)


class MemoryManager:
    """Manages exploration memory for curiosity-driven exploration"""
    
    def __init__(self, storage: DataStorage, client):
        self.storage = storage
        self.client = client
        self.memory_cache = {}  # Cache of generated memories
        self.processed_counts = {}  # Track processed counts per environment
    
    def get_exploration_memory(self, env_id: str) -> str:
        """Get exploration memory summary for an environment"""
        # Get historical triplets for this environment
        historical_triplets = self.storage.get_triplets_by_env_id(env_id)
        
        if not historical_triplets:
            return ""
        
        current_count = len(historical_triplets)
        
        # Check if cache needs updating
        if (env_id in self.memory_cache and 
            env_id in self.processed_counts and 
            current_count <= self.processed_counts[env_id]):
            return self.memory_cache[env_id]
        
        # Compute new triplets
        previous_count = self.processed_counts.get(env_id, 0)
        new_triplets = historical_triplets[previous_count:] if previous_count > 0 else historical_triplets
        
        # Generate or update memory summary
        if env_id not in self.memory_cache or previous_count == 0:
            memory = self._generate_exploration_summary(historical_triplets)
        else:
            previous_memory = self.memory_cache[env_id]
            memory = self._update_exploration_summary(previous_memory, new_triplets)
        
        # Update cache
        self.memory_cache[env_id] = memory
        self.processed_counts[env_id] = current_count
        
        # Persist memory
        self.storage.save_memory(env_id, "exploration", memory)
        
        return memory
    
    def get_task_memory(self, env_id: str) -> str:
        """Get task abstraction memory summary for Stage 2"""
        historical_tasks = self.storage.get_tasks_by_env_id(env_id)
        
        if not historical_tasks:
            return "No previous tasks have been abstracted for this environment."
        
        return self._generate_task_summary(historical_tasks)
    
    def invalidate_cache(self, env_id: str):
        """Invalidate cache for an environment"""
        if env_id in self.memory_cache:
            del self.memory_cache[env_id]
        if env_id in self.processed_counts:
            del self.processed_counts[env_id]
    
    def _generate_exploration_summary(self, triplets: List[Triplet]) -> str:
        """Generate exploration memory summary using LLM"""
        try:
            # Extract key info
            actions_and_results = []
            for triplet in triplets[-50:]:  # Limit to recent 50 triplets
                action_result = {
                    'action': triplet.action,
                    'observation': triplet.observation[:200] if triplet.observation else '',
                    'reward': triplet.reward,
                    'done': triplet.done
                }
                actions_and_results.append(action_result)
            
            system_prompt = """You are an exploration memory summarizer for a web agent.
Your task is to summarize past exploration activities into a concise memory that helps guide future exploration.

The memory should:
1. Summarize what was explored (pages, features, actions)
2. Describe key patterns or strategies that worked
3. Note any areas that haven't been explored yet
4. Highlight anything that led to errors or poor outcomes

Keep the summary under 500 words and focused on actionable insights."""
            
            user_prompt = f"""Here are the recent exploration actions and results in this web environment:

{self._format_actions_for_llm(actions_and_results)}

Generate a structured exploration memory summarizing what was done and what was learned."""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.client.chat_with_retry(messages, max_retries=2)
            if response:
                return response.strip()
            else:
                return self._generate_fallback_summary(actions_and_results)
                
        except Exception as e:
            logger.warning(f"Failed to generate LLM exploration summary: {e}")
            return self._generate_fallback_summary(actions_and_results)
    
    def _update_exploration_summary(self, previous_memory: str, new_triplets: List[Triplet]) -> str:
        """Incrementally update exploration memory summary"""
        try:
            new_actions = []
            for triplet in new_triplets[-50:]:
                action_result = {
                    'action': triplet.action,
                    'observation': triplet.observation[:150] if triplet.observation else '',
                    'reward': triplet.reward,
                    'done': triplet.done
                }
                new_actions.append(action_result)
            
            system_prompt = """You are an exploration memory manager for a web agent.
Update the existing exploration memory with new exploration results.
Merge the new information with the existing memory, removing redundancy and keeping the most important insights."""
            
            user_prompt = f"""Existing exploration memory:
{previous_memory}

New exploration actions and results:
{self._format_actions_for_llm(new_actions)}

Update the memory to incorporate these new findings. Keep the summary under 500 words."""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.client.chat_with_retry(messages, max_retries=2)
            if response:
                return response.strip()
            else:
                return previous_memory
                
        except Exception as e:
            logger.warning(f"Failed to update exploration memory: {e}")
            return previous_memory
    
    def _generate_task_summary(self, tasks: List[Task]) -> str:
        """Generate task summary for Stage 2"""
        task_list = []
        for task in tasks[-20:]:  # Last 20 tasks
            task_list.append(f"- {task.query} (confidence: {task.confidence:.2f})")
        
        return f"""Previously abstracted tasks for this environment:
{chr(10).join(task_list)}

Avoid generating similar or duplicate tasks."""
    
    def _format_actions_for_llm(self, actions: List[Dict[str, Any]]) -> str:
        """Format actions for LLM prompt"""
        formatted = []
        for i, action in enumerate(actions, 1):
            formatted.append(f"""Step {i}:
  Action: {action['action']}
  Result: {action['observation']}
  Reward: {action['reward']}
  Done: {action['done']}""")
        return "\n".join(formatted)
    
    def _generate_fallback_summary(self, actions: List[Dict[str, Any]]) -> str:
        """Generate fallback summary without LLM"""
        if not actions:
            return ""
        
        action_types = set()
        for action in actions:
            action_str = action.get('action', '')
            if 'click' in action_str.lower():
                action_types.add('click')
            if 'type' in action_str.lower() or 'fill' in action_str.lower():
                action_types.add('type')
            if 'scroll' in action_str.lower():
                action_types.add('scroll')
        
        return f"""Exploration summary:
- Total actions: {len(actions)}
- Action types used: {', '.join(action_types) if action_types else 'various'}
- Consider exploring new areas and trying different action patterns."""
