"""
Task Abstraction Prompts for Stage 2
Prompts for abstracting concrete tasks from exploration triplets.
"""
import re
import json
from typing import List, Dict, Any, Optional


class TaskAbstractionPrompts:
    """Prompts for Stage 2: Task Abstraction"""
    
    def build_task_extraction_prompt(
        self,
        triplets: List[Dict[str, Any]],
        env_description: str,
        task_memory: Optional[str],
        website: str = "shopping_admin"
    ) -> tuple:
        """Build prompt for task extraction"""
        system_prompt = self._build_system_prompt(website)
        user_prompt = self._build_user_prompt(triplets, env_description, task_memory)
        return system_prompt, user_prompt
    
    def _build_system_prompt(self, website: str) -> str:
        """Build system prompt for task abstraction"""
        return f"""You are a *Task Abstraction Expert* for web automation. Your specialty is to inspect an agent's interaction history and distill concrete, goal-oriented tasks from it.

## Your Job:
1. Inspect the interaction sequence (observation, action, next_observation)
2. Identify specific goals or tasks the agent was attempting to achieve
3. Abstract each goal into a clear task description, query, and action sequence

## Website Context:
You are analyzing interactions from a **{website}** website.

## Abstraction Rules:
• Focus on clear, goal-directed behavior; ignore purely random exploration
• Include at least 3-5 steps in each action sequence
• Group similar behavior patterns into the same task
• Each task must have a complete action sequence from start to finish
• Tasks should be specific and measurable (e.g., "Add product X to cart" not "Browse products")
• Include any necessary preconditions in the description

## Task Categories for {website}:
{self._get_category_examples(website)}

## Output Format:
For each task you identify, output in this JSON format:

```json
{{
    "tasks": [
        {{
            "description": "Detailed task description explaining what needs to be done",
            "query": "Natural language query a user might ask to accomplish this task",
            "action_sequence": ["click(\\"element1\\")", "fill(\\"input\\", \\"value\\")", "click(\\"submit\\")"],
            "ground_truth": "Expected outcome or final state",
            "confidence": 0.85,
            "difficulty": "medium",
            "category": "navigation"
        }}
    ]
}}
```

Only output valid JSON. Extract 1-5 tasks from the given interaction sequence."""
    
    def _get_category_examples(self, website: str) -> str:
        """Get category examples based on website type"""
        categories = {
            "shopping_admin": """
- Navigation: Moving between admin sections
- Product Management: Adding, editing, deleting products
- Order Management: Processing, updating orders
- Customer Management: Viewing, editing customer information
- Inventory: Stock management, price updates
- Reports: Generating and viewing reports
- Settings: Configuring store settings""",
            "shopping": """
- Search: Finding products by keyword
- Navigation: Browsing categories and pages
- Cart: Adding, removing items from cart
- Checkout: Completing purchases
- Account: Login, registration, profile management
- Wishlist: Managing saved items
- Reviews: Reading and writing reviews""",
            "gitlab": """
- Repository: Creating, cloning, managing repos
- Issues: Creating, editing, closing issues
- Merge Requests: Creating, reviewing MRs
- Code Review: Commenting, approving changes
- CI/CD: Managing pipelines
- Settings: Project and account settings""",
            "reddit": """
- Posts: Creating, voting on posts
- Comments: Writing, replying to comments
- Subreddits: Browsing, subscribing
- Profile: Managing user profile
- Search: Finding content""",
            "map": """
- Search: Finding locations
- Directions: Getting routes between places
- Navigation: Exploring the map
- Details: Viewing place information"""
        }
        return categories.get(website, categories["shopping_admin"])
    
    def _build_user_prompt(
        self,
        triplets: List[Dict[str, Any]],
        env_description: str,
        task_memory: Optional[str]
    ) -> str:
        """Build user prompt with triplet data"""
        sections = []
        
        # Environment description
        if env_description:
            sections.append(f"""## Environment Description:
{env_description[:2000]}""")
        
        # Task memory (previously generated tasks)
        if task_memory:
            sections.append(f"""## Previously Generated Tasks:
{task_memory}

Avoid generating duplicate or very similar tasks.""")
        
        # Triplet sequence
        triplet_text = ""
        for i, t in enumerate(triplets, 1):
            triplet_text += f"""
### Step {i}:
- URL: {t.get('url', 'N/A')}
- Action: {t.get('action', 'N/A')}
- Result: {t.get('next_observation', '')[:500]}
"""
        
        sections.append(f"""## Interaction Sequence:
{triplet_text}""")
        
        sections.append("""## Your Task:
Analyze this interaction sequence and extract concrete, reusable tasks.

Output your response as valid JSON with the format specified in the system prompt.""")
        
        return "\n\n".join(sections)
    
    def parse_tasks(self, response: str) -> List[Dict[str, Any]]:
        """Parse tasks from LLM response"""
        try:
            # Try to extract JSON from response
            json_patterns = [
                r'```json\s*(.*?)```',
                r'```\s*(.*?)```',
                r'\{[\s\S]*"tasks"[\s\S]*\}'
            ]
            
            for pattern in json_patterns:
                match = re.search(pattern, response, re.DOTALL)
                if match:
                    json_str = match.group(1) if '```' in pattern else match.group(0)
                    data = json.loads(json_str)
                    
                    if isinstance(data, dict) and 'tasks' in data:
                        return data['tasks']
                    elif isinstance(data, list):
                        return data
            
            # Try parsing entire response as JSON
            data = json.loads(response)
            if isinstance(data, dict) and 'tasks' in data:
                return data['tasks']
            elif isinstance(data, list):
                return data
                
        except Exception as e:
            pass
        
        return []
