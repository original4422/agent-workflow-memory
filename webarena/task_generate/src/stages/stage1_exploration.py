"""
Stage 1: Curious Exploration
Curiosity-driven exploration of the WebArena environment to generate triplets.
"""
import uuid
from typing import List, Dict, Any, Optional

from browsergym.experiments import EnvArgs
from browsergym.utils.obs import flatten_axtree_to_str

from ..core.api_client import APIClient
from ..core.memory_manager import MemoryManager
from ..data.models import Triplet
from ..data.storage import DataStorage
from ..prompts.exploration import ExplorationPrompts
from ..utils.logger import get_logger

logger = get_logger(__name__)


class Stage1Exploration:
    """Stage 1: Curiosity-driven exploration to generate triplets"""
    
    def __init__(
        self,
        client: APIClient,
        env_config: Dict[str, Any],
        max_steps: int = 20,
        storage: DataStorage = None,
        session_id: Optional[str] = None,
        use_memory: bool = True
    ):
        self.client = client
        self.env_config = env_config
        self.max_steps = max_steps
        self.storage = storage
        self.session_id = session_id
        self.use_memory = use_memory
        
        # Initialize memory manager
        if storage and use_memory:
            self.memory_manager = MemoryManager(storage, client)
        else:
            self.memory_manager = None
        
        # Exploration requirement
        self.exploration_requirement = None
        
        # Prompt builder
        self.prompts = ExplorationPrompts()
    
    def set_exploration_requirement(
        self,
        requirement: Optional[str] = None,
        concepts: Optional[List[str]] = None
    ):
        """Set exploration requirements and concepts"""
        self.exploration_requirement = ""
        
        if requirement:
            self.exploration_requirement = f"Focus on: {requirement}\n"
        
        if concepts:
            import random
            random.shuffle(concepts)
            chosen_concepts = concepts[:10] if len(concepts) > 10 else concepts
            self.exploration_requirement += f"Explore these concepts: {', '.join(chosen_concepts)}"
    
    def run(
        self,
        rollout_num: int = 3,
        requirement: Optional[str] = None,
        concepts: Optional[List[str]] = None
    ) -> List[Triplet]:
        """Run Stage 1 exploration"""
        # Set exploration requirement
        self.set_exploration_requirement(requirement, concepts)
        
        all_triplets = []
        
        for rollout_idx in range(rollout_num):
            logger.info(f"Starting rollout {rollout_idx + 1}/{rollout_num}")
            
            triplets = self._single_rollout(rollout_idx)
            all_triplets.extend(triplets)
            
            logger.info(f"Rollout {rollout_idx + 1} completed, generated {len(triplets)} triplets")
        
        logger.info(f"Stage 1 completed, generated {len(all_triplets)} triplets in total")
        return all_triplets
    
    def _single_rollout(self, rollout_idx: int) -> List[Triplet]:
        """Single exploration rollout"""
        triplets = []
        
        # Create environment
        env = self._create_environment()
        if env is None:
            logger.error("Failed to create environment")
            return triplets
        
        env_id = f"rollout_{rollout_idx}_{uuid.uuid4().hex[:6]}"
        exploration_memory = None
        
        try:
            # Reset environment
            obs, info = env.reset()
            
            # Get initial observation
            initial_obs = self._process_observation(obs)
            current_url = obs.get('url', '')
            
            # Load exploration memory
            if self.memory_manager:
                exploration_memory = self.memory_manager.get_exploration_memory(env_id)
            
            history = []
            
            for step in range(self.max_steps):
                # Get action from LLM
                action, llm_response = self._get_exploration_action(
                    initial_obs=initial_obs,
                    current_obs=initial_obs if step == 0 else triplets[-1].next_observation if triplets else initial_obs,
                    history=history,
                    exploration_memory=exploration_memory,
                    goal=obs.get('goal', '')
                )
                
                if not action:
                    logger.warning(f"Step {step}: No valid action generated")
                    break
                
                # Store current observation
                current_obs_text = triplets[-1].next_observation if triplets else initial_obs
                
                # Execute action
                try:
                    obs, reward, terminated, truncated, info = env.step(action)
                    done = terminated or truncated
                except Exception as e:
                    logger.warning(f"Action execution failed: {e}")
                    obs = {'axtree_object': None, 'url': current_url}
                    reward = 0.0
                    done = False
                
                # Get next observation
                next_obs = self._process_observation(obs)
                next_url = obs.get('url', '')
                
                # Create triplet
                triplet = Triplet(
                    env_id=env_id,
                    session_id=self.session_id,
                    observation=current_obs_text,
                    action=action,
                    next_observation=next_obs,
                    url=current_url,
                    reward=float(reward) if reward is not None else 0.0,
                    done=bool(done),
                    step_number=step,
                    llm_response=llm_response,
                    exploration_memory=exploration_memory
                )
                triplets.append(triplet)
                
                # Save triplet
                if self.storage:
                    self.storage.save_triplet(triplet, self.session_id)
                
                # Update history
                history.append({
                    'action': action,
                    'observation': next_obs[:500]  # Truncate for history
                })
                
                current_url = next_url
                
                if done:
                    logger.info(f"Environment done at step {step}")
                    break
                
                # Update memory periodically
                if self.memory_manager and step > 0 and step % 5 == 0:
                    self.memory_manager.invalidate_cache(env_id)
                    exploration_memory = self.memory_manager.get_exploration_memory(env_id)
            
        except Exception as e:
            logger.error(f"Rollout failed: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            try:
                env.close()
            except:
                pass
        
        return triplets
    
    def _create_environment(self):
        """Create WebArena environment using BrowserGym"""
        try:
            from browsergym.experiments import EnvArgs
            
            # Get task configuration
            website = self.env_config.get('website', 'shopping_admin')
            task_name = self.env_config.get('task_name')
            
            # If no specific task, use openended mode
            if not task_name:
                task_name = "openended"
                start_url = self._get_website_url(website)
                task_kwargs = {"start_url": start_url}
            else:
                task_kwargs = None
            
            env_args = EnvArgs(
                task_name=task_name,
                task_seed=None,
                max_steps=self.max_steps,
                headless=self.env_config.get('headless', False),
                viewport=self.env_config.get('viewport', {"width": 1500, "height": 1280}),
                slow_mo=self.env_config.get('slow_mo', 30),
                task_kwargs=task_kwargs
            )
            
            env = env_args.make_env(
                action_mapping=None,
                exp_dir=None
            )
            
            return env
            
        except Exception as e:
            logger.error(f"Failed to create environment: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _get_website_url(self, website: str) -> str:
        """Get URL for a website type"""
        urls = {
            "shopping": "http://166.111.53.249:7770",
            "shopping_admin": "http://166.111.53.249:7780/admin",
            "gitlab": "http://166.111.53.249:8023",
            "reddit": "http://166.111.53.249:9999",
            "map": "http://166.111.53.249:3000"
        }
        return urls.get(website, urls["shopping_admin"])
    
    def _process_observation(self, obs: dict) -> str:
        """Process observation to text format"""
        try:
            # Prefer AXTree
            if self.env_config.get('use_ax_tree', True) and obs.get('axtree_object'):
                return flatten_axtree_to_str(obs['axtree_object'])
            
            # Fall back to DOM
            if obs.get('dom_object'):
                from browsergym.utils.obs import flatten_dom_to_str
                return flatten_dom_to_str(obs['dom_object'])
            
            # Last resort: goal
            return str(obs.get('goal', ''))
            
        except Exception as e:
            logger.warning(f"Failed to process observation: {e}")
            return str(obs.get('goal', ''))
    
    def _get_exploration_action(
        self,
        initial_obs: str,
        current_obs: str,
        history: List[Dict[str, str]],
        exploration_memory: Optional[str],
        goal: str = ""
    ) -> tuple:
        """Get exploration action from LLM"""
        try:
            # Build prompt
            system_prompt, user_prompt = self.prompts.build_exploration_prompt(
                initial_obs=initial_obs,
                current_obs=current_obs,
                history=history,
                exploration_memory=exploration_memory,
                exploration_requirement=self.exploration_requirement,
                goal=goal
            )
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.client.chat_with_retry(messages, max_retries=2)
            
            if not response:
                return "noop", None
            
            # Parse action from response
            action = self.prompts.parse_action(response)
            
            return action if action else "noop", response
            
        except Exception as e:
            logger.error(f"Failed to get exploration action: {e}")
            return "noop", None
