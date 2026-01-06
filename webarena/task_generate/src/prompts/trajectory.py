"""
Trajectory Generation Prompts for Stage 3
Prompts for executing tasks and generating complete trajectories.
"""
import re
from typing import List, Dict, Any, Optional


class TrajectoryPrompts:
    """Prompts for Stage 3: Trajectory Generation"""
    
    def get_system_prompt(self) -> str:
        """Get system prompt for trajectory generation"""
        return """You are an expert web automation agent. Your task is to complete web-based tasks by taking appropriate actions.

## Action Format:
Use BrowserGym actions in the following format:

- click("element_id") - Click on an element by its ID
- fill("element_id", "text") - Type text into an input field
- scroll(x, y) - Scroll the page (e.g., scroll(0, 300) to scroll down)
- goto("url") - Navigate to a specific URL
- hover("element_id") - Hover over an element
- select_option("element_id", "option") - Select a dropdown option
- press("key") - Press a keyboard key (e.g., "Enter", "Tab")

## Special Actions:
- Use `<finish>` when you believe the task is complete

## Guidelines:
1. Analyze the current page state carefully
2. Take one action at a time
3. Use element IDs from the accessibility tree
4. If stuck, try alternative approaches
5. Mark task as complete when the goal is achieved

## Output Format:
First explain your reasoning, then provide your action in ```action``` code blocks:

```action
click("submit-button")
```"""
    
    def build_action_prompt(
        self,
        env_description: str,
        task_description: str,
        query: str,
        current_obs: str,
        history: List[str],
        ground_truth: Any
    ) -> List[Dict[str, str]]:
        """Build prompt for getting next action"""
        system_prompt = self.get_system_prompt()
        
        # Build user message
        sections = []
        
        sections.append(f"""## Task:
{task_description}

## Query:
{query}""")
        
        if ground_truth:
            if isinstance(ground_truth, list):
                gt_text = "\n".join([f"- {step}" for step in ground_truth[:5]])
            else:
                gt_text = str(ground_truth)
            sections.append(f"""## Hints (action sequence):
{gt_text}

Note: These are hints only. Adapt to the current page state.""")
        
        if history:
            sections.append(f"""## Previous Actions:
{chr(10).join(history)}""")
        
        sections.append(f"""## Current Page State:
{current_obs[:4000]}""")
        
        sections.append("""## Your Task:
Based on the current page state, determine the next action to complete the task.

If the task is complete, output:
```action
<finish>
```

Otherwise, provide your reasoning and the next action.""")
        
        user_prompt = "\n\n".join(sections)
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    def build_reflection_prompt(
        self,
        task_description: str,
        query: str,
        current_obs: str,
        history: List[str],
        last_action: str,
        last_result: str,
        error: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Build prompt for reflection strategy"""
        system_prompt = self.get_system_prompt()
        
        user_prompt = f"""## Task:
{task_description}

## Query:
{query}

## Previous Actions:
{chr(10).join(history) if history else "None"}

## Last Action:
{last_action}

## Result:
{last_result[:500]}

{"## Error: " + error if error else ""}

## Current Page State:
{current_obs[:3000]}

## Reflection Required:
1. What did the last action accomplish?
2. Did it bring us closer to the goal?
3. What should we try next?

Based on your reflection, provide the next action to complete the task.
If stuck, consider:
- Trying a different element
- Going back and taking a different path
- Scrolling to find more elements"""
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    def parse_action(self, response: str) -> Optional[str]:
        """Parse action from LLM response"""
        if not response:
            return None
        
        # Check for finish
        if "<finish>" in response.lower():
            return "<finish>"
        
        try:
            # Try to extract from code blocks
            patterns = [
                r'```action\s*(.*?)```',
                r'```\s*(.*?)```',
                r'<action>(.*?)</action>'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
                if match:
                    action = match.group(1).strip()
                    # Clean up
                    action = action.replace('\n', ' ').strip()
                    if action and action != "<finish>":
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
