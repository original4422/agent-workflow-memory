#!/usr/bin/env python3
""" 
================================================================================
main.py - WebArena Task Generator
================================================================================
A lightweight implementation inspired by CuES (Curiosity-driven and
Environment-grounded Synthesis).

[Overview]
Generate WebArena-format tasks from a web page (URL) or an HTML file.

[Usage]
1) Generate from URL:
    python main.py --url "http://example.com/admin"

2) Generate from local HTML:
    python main.py --file "./sample.html"

3) Demo mode (built-in HTML):
    python main.py --demo

[Output]
Outputs are saved under `./generated_task/` (optionally with a timestamp
subfolder), typically including `tasks.json` and `conversation_history.json`.
================================================================================
"""

import argparse
import sys
import os
from datetime import datetime

# Ensure local modules are importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config, APIConfig, WebArenaConfig, GenerationConfig
from generator import TaskGenerationPipeline
from utils import JSONHandler

from src.demo_html import DEMO_HTML



def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="WebArena Task Generator (CuES-Lite)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Demo mode (built-in HTML)
  python main.py --demo

  # Generate tasks from a URL
  python main.py --url "http://166.111.53.249:7780/admin"

  # Generate from a local HTML file
  python main.py --file "./page.html"

  # Customize count and output directory
  python main.py --demo --num-intents 10 --output-dir "./my_tasks"

  # Use OpenAI API
  python main.py --demo --api-type openai --api-key "sk-xxx"
        """
    )
    
    # Input source (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--url",
        type=str,
        help="Target page URL"
    )
    input_group.add_argument(
        "--file",
        type=str,
        help="Path to a local HTML file"
    )
    input_group.add_argument(
        "--demo",
        action="store_true",
        help="Use built-in sample HTML (demo mode)"
    )
    
    # Generation settings
    parser.add_argument(
        "--num-intents",
        type=int,
        default=5,
        help="Number of tasks to generate (default: 5)"
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.7,
        help="Minimum confidence threshold (default: 0.7)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./generated_task",
        help="Output directory (default: ./generated_task)"
    )
    
    # WebArena settings
    parser.add_argument(
        "--site",
        type=str,
        default="shopping_admin",
        help="Target site name (default: shopping_admin)"
    )
    parser.add_argument(
        "--start-url",
        type=str,
        default="http://166.111.53.249:7780/admin",
        help="Task start URL"
    )
    
    # API settings
    parser.add_argument(
        "--api-type",
        type=str,
        choices=["azure", "openai"],
        default="azure",
        help="API type: azure (cloudgpt) or openai (default: azure)"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="OpenAI API key (required when --api-type=openai)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-20241120-2",
        help="Model name (default: gpt-4o-20241120-2)"
    )
    
    # Other options
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show verbose output"
    )
    parser.add_argument(
        "--start-id",
        type=int,
        default=0,
        help="Starting task ID (default: 0)"
    )
    
    return parser.parse_args()


def build_config(args) -> Config:
    """
    Build Config from CLI arguments.

    Args:
        args: Parsed CLI args

    Returns:
        Config
    """
    # API
    api_config = APIConfig(
        api_type=args.api_type,
        openai_api_key=args.api_key,
        model_name=args.model
    )
    
    # WebArena
    webarena_config = WebArenaConfig(
        sites=[args.site],
        base_url=args.start_url
    )
    
    # Generation
    generation_config = GenerationConfig(
        num_intents=args.num_intents,
        min_confidence=args.min_confidence,
        output_dir=args.output_dir
    )
    
    return Config(
        api=api_config,
        webarena=webarena_config,
        generation=generation_config
    )


def get_html_content(args) -> str:
    """
    Get HTML content based on the selected input source.

    Args:
        args: Parsed CLI args

    Returns:
        HTML content string
    """
    if args.demo:
        print("[INFO] Using built-in sample HTML (demo mode)")
        return DEMO_HTML
    
    elif args.file:
        print(f"[INFO] Reading from file: {args.file}")
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            print(f"[ERROR] File not found: {args.file}")
            sys.exit(1)
        except Exception as e:
            print(f"[ERROR] Failed to read file: {e}")
            sys.exit(1)
    
    elif args.url:
        print(f"[INFO] Fetching from URL: {args.url}")
        try:
            import requests
            response = requests.get(args.url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"[ERROR] Failed to fetch URL: {e}")
            sys.exit(1)
    
    return ""


def print_banner():
    """Print a banner."""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║           WebArena Task Generator (CuES-Lite)                                ║
║                                                                              ║
║    A lightweight CuES-inspired tool to generate WebArena-format tasks         ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)


def print_summary(tasks, output_file, elapsed_time):
    """Print a run summary."""
    print("\n" + "=" * 60)
    print("[Done]")
    print("=" * 60)
    print(f"  Tasks generated: {len(tasks)}")
    print(f"  Output file: {output_file}")
    print(f"  Elapsed: {elapsed_time:.2f} seconds")
    print()
    
    if tasks:
        print("[Preview]")
        print("-" * 60)
        for i, task in enumerate(tasks[:3], 1):
            intent = task.get("intent", "N/A")
            if len(intent) > 60:
                intent = intent[:57] + "..."
            print(f"  {i}. {intent}")
        if len(tasks) > 3:
            print(f"  ... and {len(tasks) - 3} more")
        print()


def main():
    """Main entry point."""
    # Parse args
    args = parse_args()
    
    # Banner
    print_banner()
    
    # Config
    config = build_config(args)
    
    # Show config
    print("[Config]")
    print(f"  API type: {config.api.api_type}")
    print(f"  Model: {config.api.model_name}")
    print(f"  Sites: {config.webarena.sites}")
    print(f"  Num intents: {config.generation.num_intents}")
    print(f"  Min confidence: {config.generation.min_confidence}")
    print()
    
    # Get HTML
    html_content = get_html_content(args)
    
    if not html_content:
        print("[ERROR] Failed to get HTML content")
        sys.exit(1)
    
    print(f"[INFO] HTML size: {len(html_content)} bytes")
    print()
    
    # Timer
    import time
    start_time = time.time()
    
    # Run pipeline
    try:
        pipeline = TaskGenerationPipeline(config)
        tasks = pipeline.run(
            html_content=html_content,
            num_intents=config.generation.num_intents,
            start_task_id=args.start_id
        )
    except Exception as e:
        print(f"\n[ERROR] Pipeline failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
    
    # Elapsed
    elapsed_time = time.time() - start_time
    
    # Save
    if tasks:
        # Create output directory
        if config.generation.use_timestamp_folder:
            # Timestamp subfolder
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join(config.generation.output_dir, timestamp)
        else:
            output_dir = config.generation.output_dir
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Save tasks.json
        tasks_filename = config.generation.output_filename
        tasks_output_path = os.path.join(output_dir, tasks_filename)
        JSONHandler.save(tasks, tasks_output_path)
        
        # Save conversation_history.json
        history_filename = config.generation.conversation_history_filename
        history_output_path = os.path.join(output_dir, history_filename)
        pipeline.save_conversation_history(history_output_path)
        
        print_summary(tasks, tasks_output_path, elapsed_time)
    else:
        print("\n[WARN] No valid tasks were generated")
        print("Possible reasons:")
        print("  1) HTML content is insufficient to infer tasks")
        print("  2) Generated tasks have low confidence")
        print("  3) LLM API call failed")
    
    return 0 if tasks else 1


if __name__ == "__main__":
    sys.exit(main())
