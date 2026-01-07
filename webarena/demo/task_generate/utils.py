"""
================================================================================
utils.py - Utility helpers
================================================================================
Common utilities for JSON IO, prompt construction, and HTML processing.

[Mapping to CuES]
- PromptBuilder: similar to the prompt builders under CuES prompts/
- JSONHandler: similar to the persistence logic in CuES data/storage.py
- HTMLProcessor: simplified environment state extractor for static HTML
================================================================================
"""

import json
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict


# ================================================================================
# JSON utilities
# ================================================================================

class JSONHandler:
    """
    JSON file reader/writer.

    Features:
    - load an existing task file
    - save generated tasks to JSON
    - support append mode
    """
    
    @staticmethod
    def load(filepath: str) -> List[Dict[str, Any]]:
        """
        Load a JSON file.
        
        Args:
            filepath: Path to the JSON file
            
        Returns:
            Parsed data list
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else [data]
        except FileNotFoundError:
            print(f"[WARN] File not found: {filepath}")
            return []
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse JSON: {e}")
            return []
    
    @staticmethod
    def save(data: List[Dict[str, Any]], filepath: str, indent: int = 2) -> bool:
        """
        Save data to a JSON file.
        
        Args:
            data: Data to save
            filepath: Target file path
            indent: Indentation spaces
            
        Returns:
            True if saved successfully
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=indent)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save file: {e}")
            return False
    
    @staticmethod
    def append(task: Dict[str, Any], filepath: str) -> bool:
        """
        Append a single task to an existing JSON file.
        
        Args:
            task: Task to append
            filepath: Target file path
            
        Returns:
            True if appended successfully
        """
        existing = JSONHandler.load(filepath)
        existing.append(task)
        return JSONHandler.save(existing, filepath)


# ================================================================================
# HTML utilities
# ================================================================================

class HTMLProcessor:
    """
    HTML content processor.

    Extracts key information from HTML to provide a structured page description
    to the LLM.

    Mapping to CuES:
    Similar to environment observation in CuES Stage 1, but simplified to static
    HTML parsing.
    """
    
    @staticmethod
    def extract_text(html: str, max_length: int = 4000) -> str:
        """
        Extract plain text content from HTML.
        
        Args:
            html: HTML string
            max_length: Max return length
            
        Returns:
            Extracted text content
        """
        # Remove script/style tags and their contents
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove all HTML tags
        text = re.sub(r'<[^>]+>', ' ', html)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Truncate to max_length
        if len(text) > max_length:
            text = text[:max_length] + "..."
        
        return text
    
    @staticmethod
    def extract_interactive_elements(html: str) -> List[Dict[str, str]]:
        """
        Extract interactive elements on the page (buttons, links, inputs, etc.).

        Purpose:
        Help the LLM understand what actions are possible on the page, so it can
        generate more grounded tasks.
        
        Args:
            html: HTML string
            
        Returns:
            Interactive element list
        """
        elements = []
        
        # Links
        links = re.findall(r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL)
        for href, text in links[:20]:  # Limit count
            clean_text = re.sub(r'<[^>]+>', '', text).strip()
            if clean_text:
                elements.append({"type": "link", "text": clean_text[:100], "href": href})
        
        # Buttons
        buttons = re.findall(r'<button[^>]*>(.*?)</button>', html, re.IGNORECASE | re.DOTALL)
        for btn_text in buttons[:10]:
            clean_text = re.sub(r'<[^>]+>', '', btn_text).strip()
            if clean_text:
                elements.append({"type": "button", "text": clean_text[:100]})
        
        # Inputs
        inputs = re.findall(r'<input[^>]*(?:placeholder=["\']([^"\']*)["\']|name=["\']([^"\']*)["\'])[^>]*>', html, re.IGNORECASE)
        for placeholder, name in inputs[:10]:
            elements.append({"type": "input", "placeholder": placeholder, "name": name})
        
        return elements
    
    @staticmethod
    def extract_page_title(html: str) -> str:
        """Extract the page title."""
        match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else "Unknown Page"
    
    @staticmethod
    def summarize_page(html: str) -> Dict[str, Any]:
        """
        Build a page summary.

        Returns a dict with:
        - title: page title
        - text_content: extracted text (truncated)
        - interactive_elements: list of interactive elements
        """
        return {
            "title": HTMLProcessor.extract_page_title(html),
            "text_content": HTMLProcessor.extract_text(html, max_length=3000),
            "interactive_elements": HTMLProcessor.extract_interactive_elements(html)
        }


# ================================================================================
# Prompt builder
# ================================================================================

class PromptBuilder:
    """
    Prompt builder.

    Mapping to CuES:
    Similar to the prompt templates in CuES prompts/, but consolidated into a
    single class for the demo pipeline.

    Pipeline stages:
    1) Intent generation prompt (CuES Stage 2: Task Abstraction)
    2) Answer validation prompt (CuES Stage 3: Quality Control)
    """
    
    @staticmethod
    def build_intent_generation_prompt(
        page_summary: Dict[str, Any],
        site_name: str,
        num_intents: int = 5
    ) -> str:
        """
        Build the intent-generation prompt.

        Mapping to CuES:
        This corresponds to task abstraction (CuES Stage 2), extracting executable
        tasks from environment state.

        Key difference:
        - CuES abstracts tasks from (state, action, observation) triplets.
        - This demo infers tasks from a single static HTML page.
        
        Args:
            page_summary: Output of HTMLProcessor.summarize_page()
            site_name: Site name (e.g., "shopping_admin")
            num_intents: Number of intents to generate
            
        Returns:
            Formatted prompt string
        """
        # Format interactive elements
        elements_text = ""
        for elem in page_summary.get("interactive_elements", [])[:15]:
            if elem["type"] == "link":
                elements_text += f"  - [Link] {elem['text']}\n"
            elif elem["type"] == "button":
                elements_text += f"  - [Button] {elem['text']}\n"
            elif elem["type"] == "input":
                elements_text += f"  - [Input] {elem.get('placeholder', elem.get('name', ''))}\n"
        
        prompt = f"""You are an expert WebArena task designer. Based on the page information below, generate plausible task intents.

## Page information

**Site**: {site_name}
**Page title**: {page_summary.get('title', 'Unknown')}

**Page text summary**:
{page_summary.get('text_content', '')[:2000]}

**Interactive elements**:
{elements_text if elements_text else "  (No interactive elements recognized)"}

## Requirements

Generate {num_intents} task intents.

Each task should satisfy:
1. **Executable**: can be completed on this page (or by navigating from it).
2. **Unambiguous**: clearly stated goal.
3. **Diverse**: cover different task types (query/modification/navigation).
4. **Verifiable**: should have an objective outcome that can be checked.

## Task type examples

For **shopping_admin** (an e-commerce admin console), common tasks include:
- Query: "What is the top-1 best-selling product in 2022?"
- Statistics: "How many orders were placed in January 2023?"
- Lookup: "Find the customer with the highest total order value"
- Modification: "Update the price of product X to $99.99"

## Output format

Return a JSON array. Each item must include:
- intent: the task description (English)
- task_type: query/modification/navigation
- difficulty: easy/medium/hard
- reasoning: why this task is plausible given the page (English)

```json
[
  {{
    "intent": "What is the top-3 best-selling products in January 2023?",
    "task_type": "query",
    "difficulty": "medium",
        "reasoning": "The page includes sales-related information, enabling a ranking query"
  }},
  ...
]
```

Only output JSON. Do not add any extra prose.
"""
        return prompt
    
    @staticmethod
    def build_answer_validation_prompt(
        intent: str,
        page_summary: Dict[str, Any],
        site_name: str
    ) -> str:
        """
        Build the answer-validation / reference-answer prompt.

        Mapping to CuES:
        This corresponds to quality control (CuES Stage 3): validate executability
        and generate reference answers.

        How it works:
        Since we do not execute a real browser here, we ask the LLM to:
        1) judge whether the task is executable on (or reachable from) the page
        2) infer plausible reference answers from the page content
        3) choose an evaluation style (string_match/url_match/program_html)
        
        Args:
            intent: Task intent to validate
            page_summary: Page summary
            site_name: Site name
            
        Returns:
            Formatted prompt string
        """
        prompt = f"""You are a WebArena task validator. Evaluate whether the task can be completed on the given page (or by navigating from it), and generate reference answers.

## Task intent

**Intent**: {intent}

## Page information

**Site**: {site_name}
**Page title**: {page_summary.get('title', 'Unknown')}

**Page text summary**:
{page_summary.get('text_content', '')[:2500]}

## What to evaluate

Please complete:
1. **Executability**: can this task be completed on this page (or via navigation)?
2. **Reference answers**: if executable, infer plausible answers from the page.
3. **Evaluation type**: choose an appropriate evaluation strategy.

## Output format

Return JSON in the following format:

```json
{{
  "is_executable": true,
  "confidence": 0.85,
  "eval_type": "string_match",
  "reference_answers": {{
        "must_include": ["keyword1", "keyword2"],
        "exact_match": "full answer (if applicable)"
  }},
    "reasoning": "Explain why this task is executable and how the answers are inferred"
}}
```

**eval_type options**:
- `string_match`: the answer must contain specific strings
- `url_match`: the final URL must match a pattern
- `program_html`: requires checking HTML elements

**reference_answers fields**:
- `must_include`: list of required keywords
- `exact_match`: a string that must match exactly
- `fuzzy_match`: a string for fuzzy matching

If the task is not executable, output:
```json
{{
  "is_executable": false,
  "confidence": 0.1,
    "reasoning": "Explain why it is not executable"
}}
```

Only output JSON. Do not add any extra prose.
"""
        return prompt


# ================================================================================
# WebArena task formatter
# ================================================================================

@dataclass
class WebArenaTask:
    """
    WebArena task data structure.

    This is a Python representation of the standard WebArena task schema.

    Mapping to CuES fields:
    - intent: similar to the CuES task query
    - reference_answers: similar to CuES validation outputs
    """
    # Target site list
    sites: List[str]
    
    # Task ID
    task_id: int
    
    # Whether login is required
    require_login: bool
    
    # Storage state path
    storage_state: str
    
    # Start URL
    start_url: str
    
    # Task intent (core field)
    intent: str
    
    # Evaluation configuration
    eval: Dict[str, Any]
    
    # Optional fields
    geolocation: Optional[str] = None
    require_reset: bool = False
    intent_template: Optional[str] = None
    instantiation_dict: Optional[Dict[str, Any]] = None
    intent_template_id: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dict."""
        result = asdict(self)
        # Drop optional fields with None
        return {k: v for k, v in result.items() if v is not None}


class TaskFormatter:
    """
    Task formatter.

    Wrap generated intents and reference answers into the standard WebArena JSON
    schema.

    Mapping to CuES:
    Similar to data-model conversion logic in CuES data/models.py.
    """
    
    def __init__(self, config):
        """
        Initialize the formatter.
        
        Args:
            config: Config object including WebArena config
        """
        self.config = config
        self.task_counter = 0
    
    def format_task(
        self,
        intent: str,
        reference_answers: Dict[str, Any],
        eval_type: str = "string_match",
        task_id: Optional[int] = None
    ) -> WebArenaTask:
        """
        Format an intent + reference answers into a WebArena task.

        Steps:
        1) assign task_id (auto-increment or explicit)
        2) build evaluation config
        3) merge WebArena config
        
        Args:
            intent: task intent
            reference_answers: reference answers dict
            eval_type: evaluation type
            task_id: optional task id
            
        Returns:
            WebArenaTask
        """
        if task_id is None:
            task_id = self.task_counter
            self.task_counter += 1
        
        # Build evaluation config
        eval_config = {
            "eval_types": [eval_type],
            "reference_answers": reference_answers,
            "reference_url": "",
            "program_html": [],
            "string_note": ""
        }
        
        return WebArenaTask(
            sites=self.config.webarena.sites,
            task_id=task_id,
            require_login=self.config.webarena.require_login,
            storage_state=self.config.webarena.storage_state,
            start_url=self.config.webarena.base_url,
            intent=intent,
            eval=eval_config
        )
    
    def format_tasks(
        self,
        generated_data: List[Dict[str, Any]],
        start_id: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Format tasks in batch.
        
        Args:
            generated_data: list containing intent and validation results
            start_id: starting task id
            
        Returns:
            WebArena-format task list
        """
        self.task_counter = start_id
        tasks = []
        
        for item in generated_data:
            if not item.get("is_executable", False):
                continue
            
            task = self.format_task(
                intent=item["intent"],
                reference_answers=item.get("reference_answers", {}),
                eval_type=item.get("eval_type", "string_match")
            )
            tasks.append(task.to_dict())
        
        return tasks
