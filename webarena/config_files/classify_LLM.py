#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Classify tasks using LLM and generate summary.

Usage: python classify_LLM.py <input_json_file> [--model_provider PROVIDER] [--model MODEL_NAME] [--retry RETRY_COUNT]
Example: python classify_LLM.py shopping_admin.raw.json
Example: python classify_LLM.py shopping_admin.raw.json --model_provider kimi --retry 5
Example: python classify_LLM.py shopping_admin.raw.json --model_provider kimi --model kimi-k2-thinking
"""

import argparse
import json
import sys
import time
from pathlib import Path
from openai import OpenAI

# Add parent directory to path to import cloudgpt_aoai
sys.path.insert(0, str(Path(__file__).parent.parent))
from cloudgpt_aoai import cloudgpt_aoai


def load_config(model_provider="glm"):
    """
    Load API configuration from config.json.

    Args:
        model_provider: Model provider name, e.g. "glm" or "kimi".

    Returns:
        dict: Configuration with base_url and api_key.
    """
    config_path = Path(__file__).parent.parent / "config" / "config.json"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            configs = json.load(f)
    except FileNotFoundError:
        print(f"Error: config file not found {config_path}")
        sys.exit(1)
    
    for config in configs:
        if config.get("model_provider") == model_provider:
            return config
    
    print(f"Error: model provider '{model_provider}' not found in config")
    sys.exit(1)


def call_llm_with_retry(client, model, messages, max_retries=10, stream=False, use_cloudgpt=False):
    """
    Call LLM API with retry mechanism.

    Args:
        client: OpenAI client instance (not used when use_cloudgpt=True).
        model: Model name to use.
        messages: Messages to send to the model.
        max_retries: Maximum number of retry attempts.
        stream: Whether to use streaming mode.
        use_cloudgpt: Whether to use cloudgpt_aoai instead of OpenAI client.

    Returns:
        str: Response content from the model.
    """
    for attempt in range(max_retries):
        try:
            if use_cloudgpt:
                # Use cloudgpt_aoai API
                params = {
                    "model": model,
                    "messages": messages,
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                    "stream": stream
                }
                
                if stream:
                    params["stream_options"] = {"include_usage": True}
                
                response = cloudgpt_aoai.get_chat_completion(**params)
                
                if stream:
                    # Stream mode: collect chunks and print in real-time
                    full_response = ""
                    for chunk in response:
                        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                            content = chunk.choices[0].delta.content
                            print(content, end="", flush=True)
                            full_response += content
                    print()  # New line after stream completes
                    return full_response
                else:
                    # Non-stream mode
                    return response.choices[0].message.content
            else:
                # Use standard OpenAI client
                if stream:
                    # Stream mode: collect chunks and print in real-time
                    response_stream = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=0.1,
                        response_format={"type": "json_object"},
                        stream=True
                    )
                    
                    full_response = ""
                    for chunk in response_stream:
                        if chunk.choices[0].delta.content:
                            content = chunk.choices[0].delta.content
                            print(content, end="", flush=True)
                            full_response += content
                    print()  # New line after stream completes
                    return full_response
                else:
                    # Non-stream mode
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=0.1,
                        response_format={"type": "json_object"}
                    )
                    return response.choices[0].message.content
        except Exception as e:
            print(f"\nAttempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print("Max retries reached. Exiting.")
                sys.exit(1)


def get_model_name(model_provider):
    """
    Get the default model name for the given provider.

    Args:
        model_provider: Model provider name.

    Returns:
        str: Default model name.
    """
    model_map = {
        "glm": "glm-4.5",
        "kimi": "kimi-k2-thinking",
        "cloudgpt": "gpt-4o"
    }
    return model_map.get(model_provider, "glm-4.5")


def classify_tasks_with_llm(input_file, model_provider="glm", model=None, max_retries=10):
    """
    Classify tasks using LLM and generate summary.

    Args:
        input_file: Input JSON file path, e.g. "shopping_admin.raw.json".
        model_provider: Model provider name, e.g. "glm" or "kimi".
        model: Model name to use. If None, uses default model for the provider.
        max_retries: Maximum number of retry attempts for API calls.
    """
    # Locate the script directory
    script_dir = Path(__file__).parent
    input_path = script_dir / input_file
    
    # Extract site name from input filename
    site_name = input_path.stem.replace('.raw', '')
    
    # Define output directory and file
    output_dir = script_dir / "classification" / site_name
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "summary_LLM.json"
    
    # Load the input file
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: file not found {input_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: failed to parse JSON - {e}")
        sys.exit(1)
    
    # Load API configuration and initialize client
    use_cloudgpt = (model_provider == "cloudgpt")
    
    if use_cloudgpt:
        # CloudGPT doesn't need explicit config or client
        client = None
    else:
        config = load_config(model_provider)
        client = OpenAI(
            api_key=config["api_key"],
            base_url=config["base_url"]
        )
    
    # Use custom model if provided, otherwise use default for the provider
    if model is None:
        model = get_model_name(model_provider)
    
    print(f"Using model provider: {model_provider}")
    print(f"Using model: {model}")
    print(f"Total tasks to classify: {len(data)}")
    
    # Prepare task summaries for LLM classification
    task_summaries = []
    for task in data:
        task_summaries.append({
            "task_id": task.get("task_id"),
            "intent_template": task.get("intent_template"),
            "intent": task.get("intent"),
            "sites": task.get("sites")
        })
    
    # Create classification prompt
    classification_prompt = f"""You are a task classifier. Analyze the following tasks and classify them into meaningful categories based on their intent and purpose.

Tasks to classify:
{json.dumps(task_summaries, ensure_ascii=False, indent=2)}

Please classify these tasks and return a JSON object with the following structure:
{{
    "categories": [
        {{
            "type_id": 0,
            "type_description": "Description of this category",
            "task_ids": [list of task_id values that belong to this category]
        }},
        ...
    ]
}}

Requirements:
1. Group similar tasks together based on their intent_template and intent.
2. Each category should have a clear, concise description.
3. type_id should start from 0 and increment.
4. Every task_id must be assigned to exactly one category.
5. Return ONLY valid JSON, no additional text."""

    messages = [
        {"role": "system", "content": "You are a helpful assistant that classifies tasks into categories. Always respond with valid JSON only."},
        {"role": "user", "content": classification_prompt}
    ]
    
    print("\n" + "="*80)
    print("SENDING PROMPT TO LLM:")
    print("="*80)
    print(f"\nSystem Message:\n{messages[0]['content']}\n")
    print(f"User Message:\n{messages[1]['content']}\n")
    print("="*80)
    
    print("\nCalling LLM for classification (streaming)...")
    print("\n" + "="*80)
    print("LLM RESPONSE (streaming):")
    print("="*80)
    response_content = call_llm_with_retry(client, model, messages, max_retries, stream=True, use_cloudgpt=use_cloudgpt)
    print("="*80 + "\n")
    
    # Parse LLM response
    try:
        classification_result = json.loads(response_content)
    except json.JSONDecodeError as e:
        print(f"Error: failed to parse LLM response as JSON - {e}")
        print(f"Response: {response_content}")
        sys.exit(1)
    
    # Build task lookup by task_id
    task_lookup = {task["task_id"]: task for task in data}
    
    # Build the type_dict and all_tasks structure
    type_dict = {}
    all_tasks = []
    
    categories = classification_result.get("categories", [])
    for category in categories:
        type_id = category["type_id"]
        type_description = category["type_description"]
        task_ids = category["task_ids"]
        
        tasks = [task_lookup[tid] for tid in task_ids if tid in task_lookup]
        
        type_dict[type_id] = {
            "type_description": type_description,
            "task_nums": len(tasks)
        }
        
        all_tasks.append({
            "task_nums": len(tasks),
            "type_id": type_id,
            "type_description": type_description,
            "tasks": tasks
        })
    
    # Sort all_tasks by type_id
    all_tasks.sort(key=lambda x: x["type_id"])
    
    # Build the final summary structure
    summary = {
        "task_nums": len(data),
        "type_nums": len(type_dict),
        "type_dict": type_dict,
        "all_tasks": all_tasks
    }
    
    # Write the summary to output file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print("\nClassification complete!")
    print(f"Input file: {input_path}")
    print(f"Output file: {output_path}")
    print(f"Total tasks: {summary['task_nums']}")
    print(f"Total types: {summary['type_nums']}")
    print("Type descriptions:")
    for type_id, type_info in type_dict.items():
        print(f"  Type {type_id}: {type_info['type_description']} ({type_info['task_nums']} tasks)")


def main():
    """Entry point for CLI execution."""
    parser = argparse.ArgumentParser(
        description="Classify tasks using LLM and generate summary.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python classify_LLM.py shopping_admin.raw.json
  python classify_LLM.py shopping_admin.raw.json --model_provider kimi --retry 5
  python classify_LLM.py shopping_admin.raw.json --model_provider kimi --model kimi-k2-thinking
  python classify_LLM.py shopping_admin.raw.json --model_provider cloudgpt --model gpt-4o-20241120-2 --retry 3

Available model providers: glm, kimi, cloudgpt
        """
    )
    
    parser.add_argument(
        "input_file",
        help="Input JSON file path, e.g. 'shopping_admin.raw.json'"
    )
    parser.add_argument(
        "--model_provider",
        default="glm",
        choices=["glm", "kimi", "cloudgpt"],
        help="Model provider name (default: glm)"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Specific model name to use. If not provided, uses default model for the provider."
    )
    parser.add_argument(
        "--retry",
        type=int,
        default=10,
        dest="max_retries",
        help="Maximum number of retry attempts for API calls (default: 10)"
    )
    
    args = parser.parse_args()
    
    classify_tasks_with_llm(
        args.input_file,
        args.model_provider,
        args.model,
        args.max_retries
    )


if __name__ == "__main__":
    main()
