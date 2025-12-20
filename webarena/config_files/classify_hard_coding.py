#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Classify tasks by intent_template_id and generate summary.

Usage: python classify_hard_coding.py <input_json_file>
Example: python classify_hard_coding.py shopping_admin.raw.json
"""

import json
import sys
from pathlib import Path
from collections import defaultdict


def classify_tasks(input_file):
    """
    Classify tasks by intent_template_id and generate summary.

    Args:
        input_file: Input JSON file path, e.g. "shopping_admin.raw.json".
    """
    # Locate the script directory
    script_dir = Path(__file__).parent
    input_path = script_dir / input_file
    
    # Extract site name from input filename (e.g., shopping_admin.raw.json -> shopping_admin)
    site_name = input_path.name.split('.')[0]
    
    # Define output directory and file
    output_dir = script_dir / "classification" / site_name
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "summary_hard_coding.json"
    
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
    
    # Group tasks by intent_template_id
    grouped_tasks = defaultdict(list)
    for task in data:
        template_id = task.get("intent_template_id")
        grouped_tasks[template_id].append(task)
    
    # Sort by intent_template_id
    sorted_template_ids = sorted(grouped_tasks.keys())
    
    # Build the intent_template_dict
    intent_template_dict = {}
    for template_id in sorted_template_ids:
        tasks = grouped_tasks[template_id]
        # Get the intent_template from the first task in this group
        intent_template = tasks[0].get("intent_template", "")
        intent_template_dict[template_id] = {
            "intent_template": intent_template,
            "task_nums": len(tasks)
        }
    
    # Build the all_tasks structure
    all_tasks = []
    for template_id in sorted_template_ids:
        tasks = grouped_tasks[template_id]
        all_tasks.append({
            "task_nums": len(tasks),
            "intent_template_id": template_id,
            "tasks": tasks
        })
    
    # Build the final summary structure
    summary = {
        "task_nums": len(data),
        "type_nums": len(sorted_template_ids),
        "intent_template_dict": intent_template_dict,
        "all_tasks": all_tasks
    }
    
    # Write the summary to output file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print("Classification complete!")
    print(f"Input file: {input_path}")
    print(f"Output file: {output_path}")
    print(f"Total tasks: {summary['task_nums']}")
    print(f"Total types: {summary['type_nums']}")
    print("Intent template details:")
    for template_id, template_info in intent_template_dict.items():
        print(f"  ID {template_id}: {template_info['intent_template']} ({template_info['task_nums']} tasks)")


def main():
    """Entry point for CLI execution."""
    if len(sys.argv) < 2:
        print("Usage: python classify_hard_coding.py <input_json_file>")
        print("Example: python classify_hard_coding.py shopping_admin.raw.json")
        sys.exit(1)
    
    input_file = sys.argv[1]
    classify_tasks(input_file)


if __name__ == "__main__":
    main()
