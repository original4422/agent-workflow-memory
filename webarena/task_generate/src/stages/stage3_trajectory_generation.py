"""
Stage 3: Trajectory Generation
Execute abstracted tasks and generate complete trajectories for training.
"""
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, asdict

from browsergym.utils.obs import flatten_axtree_to_str

from ..core.api_client import APIClient
from ..data.models import Task, Trajectory, TrajectoryStep
from ..data.storage import DataStorage
from ..prompts.trajectory import TrajectoryPrompts
from ..utils.logger import get_logger

logger = get_logger(__name__)


class Stage3TrajectoryGeneration:
    """Stage 3: Generate execution trajectories from tasks"""
    
    def __init__(
        self,
        client: APIClient,
        env_config: Dict[str, Any],
        max_steps: int = 25,
        storage: DataStorage = None,
        session_id: Optional[str] = None,
        use_reflection: bool = False
    ):
        self.client = client
        self.env_config = env_config
        self.max_steps = max_steps
        self.storage = storage
        self.session_id = session_id
        self.use_reflection = use_reflection
        
        # Prompt builder
        self.prompts = TrajectoryPrompts()
        
        # Output directories
        if storage:
            self.output_dir = storage.base_dir / "trajectories"
            self.failed_dir = self.output_dir / "failed"
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.failed_dir.mkdir(parents=True, exist_ok=True)
    
    def run(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run trajectory generation for all tasks"""
        logger.info(f"Starting Stage 3: Generating trajectories for {len(tasks)} tasks")
        
        results = {
            "successful_trajectories": [],
            "failed_tasks": [],
            "statistics": {
                "total_tasks": len(tasks),
                "successful": 0,
                "failed": 0
            }
        }
        
        for i, task in enumerate(tasks):
            task_id = task.get('task_id', f'task_{i}')
            logger.info(f"Processing task {i+1}/{len(tasks)}: {task_id}")
            
            # Validate task
            if not self._validate_task(task):
                logger.error(f"Invalid task structure for {task_id}")
                results["failed_tasks"].append(task)
                results["statistics"]["failed"] += 1
                self._save_failed_task(task, "invalid_structure")
                continue
            
            try:
                trajectory = self._generate_trajectory(task)
                
                if trajectory and trajectory.success:
                    results["successful_trajectories"].append(trajectory)
                    results["statistics"]["successful"] += 1
                    self._save_trajectory(trajectory, failed=False)
                    logger.info(f"Task {task_id} completed successfully")
                else:
                    results["failed_tasks"].append(task)
                    results["statistics"]["failed"] += 1
                    if trajectory:
                        self._save_trajectory(trajectory, failed=True)
                    logger.warning(f"Task {task_id} failed")
                    
            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error processing task {task_id}: {e}")
                results["failed_tasks"].append(task)
                results["statistics"]["failed"] += 1
                self._save_failed_task(task, str(e))
        
        # Calculate success rate
        total = results["statistics"]["total_tasks"]
        successful = results["statistics"]["successful"]
        results["statistics"]["success_rate"] = successful / total if total > 0 else 0
        
        logger.info(f"Stage 3 completed: {successful}/{total} successful ({results['statistics']['success_rate']:.2%})")
        
        return results
    
    def _validate_task(self, task: Dict[str, Any]) -> bool:
        """Validate task structure"""
        required_fields = ['query', 'description']
        return all(task.get(field) for field in required_fields)
    
    def _generate_trajectory(self, task: Dict[str, Any]) -> Optional[Trajectory]:
        """Generate trajectory for a single task"""
        task_id = task.get('task_id', 'unknown')
        description = task.get('description', '')
        query = task.get('query', '')
        ground_truth = task.get('ground_truth', task.get('action_sequence', []))
        env_id = task.get('env_id', '')
        
        # Create environment
        env = self._create_environment()
        if env is None:
            return None
        
        steps = []
        messages = []  # For training data
        
        try:
            # Reset environment
            obs, info = env.reset()
            
            initial_obs = self._process_observation(obs)
            goal = obs.get('goal', query)
            current_url = obs.get('url', '')
            
            # Add system message
            system_msg = self.prompts.get_system_prompt()
            messages.append({"role": "system", "content": system_msg})
            
            for step_num in range(self.max_steps):
                # Build history
                history = [
                    f"Step {s.step_number}: {s.action} -> {s.next_observation[:200]}"
                    for s in steps[-3:]  # Last 3 steps
                ]
                
                # Get action from LLM
                action, llm_response = self._get_task_action(
                    env_description=initial_obs,
                    task_description=description,
                    query=query,
                    current_obs=steps[-1].next_observation if steps else initial_obs,
                    history=history,
                    ground_truth=ground_truth
                )
                
                if not action:
                    logger.warning(f"No action generated at step {step_num}")
                    break
                
                # Check for finish action
                if "<finish>" in action.lower() or action.lower() == "finish":
                    # Task completed
                    step = TrajectoryStep(
                        step_number=step_num,
                        observation=steps[-1].next_observation if steps else initial_obs,
                        action="<finish>",
                        next_observation="Task completed",
                        reward=1.0,
                        done=True,
                        llm_response=llm_response,
                        url=current_url
                    )
                    steps.append(step)
                    
                    # Add to messages
                    messages.append({
                        "role": "user",
                        "content": f"Observation: {step.observation[:500]}"
                    })
                    messages.append({
                        "role": "assistant",
                        "content": llm_response
                    })
                    break
                
                # Execute action
                try:
                    current_obs_text = steps[-1].next_observation if steps else initial_obs
                    obs, reward, terminated, truncated, info = env.step(action)
                    done = terminated or truncated
                except Exception as e:
                    logger.warning(f"Action failed: {e}")
                    current_obs_text = steps[-1].next_observation if steps else initial_obs
                    obs = {'axtree_object': None, 'url': current_url}
                    reward = -0.1
                    done = False
                
                next_obs = self._process_observation(obs)
                next_url = obs.get('url', '')
                
                # Create step
                step = TrajectoryStep(
                    step_number=step_num,
                    observation=current_obs_text,
                    action=action,
                    next_observation=next_obs,
                    reward=float(reward) if reward else 0.0,
                    done=done,
                    llm_response=llm_response,
                    url=current_url
                )
                steps.append(step)
                
                # Add to messages
                messages.append({
                    "role": "user", 
                    "content": f"Observation: {current_obs_text[:500]}"
                })
                messages.append({
                    "role": "assistant",
                    "content": llm_response
                })
                
                current_url = next_url
                
                if done:
                    break
            
            # Evaluate success
            success, reason = self._evaluate_trajectory(steps, query, ground_truth)
            
            # Calculate final reward
            final_reward = sum(s.reward for s in steps) / len(steps) if steps else 0
            
            trajectory = Trajectory(
                task_id=task_id,
                env_id=env_id,
                session_id=self.session_id,
                description=description,
                query=query,
                ground_truth=str(ground_truth) if ground_truth else None,
                steps=[s for s in steps],
                success=success,
                final_reward=final_reward,
                reason=reason,
                total_steps=len(steps),
                strategy="reflection" if self.use_reflection else "simple",
                messages=messages
            )
            
            return trajectory
            
        except Exception as e:
            logger.error(f"Trajectory generation failed: {e}")
            import traceback
            traceback.print_exc()
            return None
        
        finally:
            try:
                env.close()
            except:
                pass
    
    def _create_environment(self):
        """Create WebArena environment"""
        try:
            from browsergym.experiments import EnvArgs
            
            website = self.env_config.get('website', 'shopping_admin')
            task_name = self.env_config.get('task_name')
            
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
            
            return env_args.make_env(action_mapping=None, exp_dir=None)
            
        except Exception as e:
            logger.error(f"Failed to create environment: {e}")
            return None
    
    def _get_website_url(self, website: str) -> str:
        """Get URL for website type"""
        urls = {
            "shopping": "http://166.111.53.249:7770",
            "shopping_admin": "http://166.111.53.249:7780/admin",
            "gitlab": "http://166.111.53.249:8023",
            "reddit": "http://166.111.53.249:9999",
            "map": "http://166.111.53.249:3000"
        }
        return urls.get(website, urls["shopping_admin"])
    
    def _process_observation(self, obs: dict) -> str:
        """Process observation to text"""
        try:
            if obs.get('axtree_object'):
                return flatten_axtree_to_str(obs['axtree_object'])
            if obs.get('dom_object'):
                from browsergym.utils.obs import flatten_dom_to_str
                return flatten_dom_to_str(obs['dom_object'])
            return str(obs.get('goal', ''))
        except Exception as e:
            return str(obs.get('goal', ''))
    
    def _get_task_action(
        self,
        env_description: str,
        task_description: str,
        query: str,
        current_obs: str,
        history: List[str],
        ground_truth: Any
    ) -> tuple:
        """Get next action for task execution"""
        try:
            messages = self.prompts.build_action_prompt(
                env_description=env_description,
                task_description=task_description,
                query=query,
                current_obs=current_obs,
                history=history,
                ground_truth=ground_truth
            )
            
            response = self.client.chat_with_retry(messages, max_retries=2)
            
            if not response:
                return None, None
            
            action = self.prompts.parse_action(response)
            return action, response
            
        except Exception as e:
            logger.error(f"Failed to get action: {e}")
            return None, None
    
    def _evaluate_trajectory(
        self,
        steps: List[TrajectoryStep],
        query: str,
        ground_truth: Any
    ) -> tuple:
        """Evaluate trajectory success"""
        if not steps:
            return False, "No steps executed"
        
        # Check if finished
        last_step = steps[-1]
        if last_step.action == "<finish>" or last_step.done:
            # Use LLM to evaluate
            try:
                eval_prompt = f"""Evaluate if this trajectory successfully completed the task.

Task: {query}
Expected outcome: {ground_truth}
Final observation: {last_step.next_observation[:500]}
Total steps: {len(steps)}

Did the agent successfully complete the task? Answer YES or NO, followed by a brief reason."""
                
                messages = [{"role": "user", "content": eval_prompt}]
                response = self.client.chat_with_retry(messages, max_retries=1)
                
                if response:
                    success = "YES" in response.upper()[:50]
                    return success, response
                    
            except Exception as e:
                logger.warning(f"Evaluation failed: {e}")
        
        return False, "Task not completed"
    
    def _save_trajectory(self, trajectory: Trajectory, failed: bool = False):
        """Save trajectory to file"""
        if self.storage:
            self.storage.save_trajectory(trajectory, failed=failed)
    
    def _save_failed_task(self, task: Dict[str, Any], reason: str):
        """Save failed task information"""
        if not self.storage:
            return
        
        failed_file = self.failed_dir / f"failed_{task.get('task_id', 'unknown')}.json"
        
        with open(failed_file, 'w', encoding='utf-8') as f:
            json.dump({
                'task': task,
                'reason': reason
            }, f, indent=2, default=str)
