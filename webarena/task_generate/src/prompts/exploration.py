"""
Exploration Prompts for Stage 1
Prompts for curiosity-driven exploration of WebArena environment.
"""
import re
from typing import List, Dict, Any, Optional


class ExplorationPrompts:
    """Prompts for Stage 1: Curious Exploration"""
    
    def build_exploration_prompt(
        self,
        initial_obs: str,
        current_obs: str,
        history: List[Dict[str, str]],
        exploration_memory: Optional[str],
        exploration_requirement: Optional[str],
        goal: str = ""
    ) -> tuple:
        """Build the full exploration prompt"""
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            initial_obs=initial_obs,
            current_obs=current_obs,
            history=history,
            exploration_memory=exploration_memory,
            exploration_requirement=exploration_requirement,
            goal=goal
        )
        return system_prompt, user_prompt
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for exploration"""
        return """You are a curious web explorer with deep interest in discovering web application functionalities. This is your first time exploring this website, and you are interested in understanding all its features and capabilities.

## Your Exploration Goals:
1. Discover new pages and features systematically
2. Try different UI elements and interactions
3. Understand the structure and navigation of the website
4. Find interesting functionalities that could be useful tasks
5. Avoid repeating actions that didn't lead anywhere useful

## Action Format:
You must respond with a valid BrowserGym action. Common actions include:

- click("element_id") - Click on an element
- fill("element_id", "text") - Type text into an input field
- scroll(0, 300) - Scroll down the page
- goto("url") - Navigate to a URL
- hover("element_id") - Hover over an element
- select_option("element_id", "option") - Select dropdown option
- press("key") - Press a keyboard key

Example actions:
```
click("12")
fill("search-input", "product name")
scroll(0, 500)
```

## Instructions:
1. Analyze the current page state
2. Consider what hasn't been explored yet
3. Choose an action that maximizes exploration value
4. Avoid repeating unsuccessful actions

First provide your reasoning, then provide your action in ```action``` blocks."""
    
    def _build_user_prompt(
        self,
        initial_obs: str,
        current_obs: str,
        history: List[Dict[str, str]],
        exploration_memory: Optional[str],
        exploration_requirement: Optional[str],
        goal: str
    ) -> str:
        """Build user prompt with context"""
        sections = []
        
        # Exploration requirement
        if exploration_requirement:
            sections.append(f"""## Exploration Requirement:
{exploration_requirement}

Prioritize this requirement while maintaining curiosity about the environment.""")
        
        # Exploration memory
        if exploration_memory:
            sections.append(f"""## Exploration Memory:
{exploration_memory}

Use this memory to avoid repeating explored areas and focus on new discoveries.""")
        
        # Recent history
        if history:
            history_text = "\n".join([
                f"- Action: {h['action']}\n  Result: {h['observation'][:200]}..."
                for h in history[-5:]  # Last 5 steps
            ])
            sections.append(f"""## Recent Actions:
{history_text}""")
        
        # Current observation
        sections.append(f"""## Current Page State:
{current_obs[:3000]}""")  # Truncate if too long
        
        # Goal if available
        if goal:
            sections.append(f"""## Website Goal (for context):
{goal}""")
        
        sections.append("""## Your Task:
Analyze the current page and choose the next exploration action. Focus on discovering new features and functionalities.

Provide your reasoning first, then your action in ```action``` code blocks.""")
        
        return "\n\n".join(sections)
    
    def parse_action(self, response: str) -> Optional[str]:
        """Parse action from LLM response"""
        if not response:
            return None
        
        try:
            # Try to extract from ```action``` or ``` blocks
            action_patterns = [
                r'```action\s*(.*?)```',
                r'```\s*(.*?)```',
                r'<action>(.*?)</action>'
            ]
            
            for pattern in action_patterns:
                match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
                if match:
                    action = match.group(1).strip()
                    # Clean up the action
                    action = action.replace('\n', ' ').strip()
                    if action:
                        return action
            
            # Try to find action patterns directly
            action_match = re.search(
                r'(click|fill|scroll|goto|hover|select_option|press)\s*\([^)]+\)',
                response,
                re.IGNORECASE
            )
            if action_match:
                return action_match.group(0).strip()
            
            return None
            
        except Exception:
            return None
