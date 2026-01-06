#!/usr/bin/env python3
"""
CuES-WebArena: Curiosity-driven Task Generation for WebArena
A curiosity-driven framework for synthesizing high-quality web agent training data.

Based on CuES (Curiosity-driven and Environment-grounded Synthesis Framework)
Adapted for WebArena environment.
"""
import os
import sys
import argparse
import yaml
import traceback
from pathlib import Path
from typing import Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.pipeline import CuESPipeline
from src.utils.logger import get_logger

logger = get_logger(__name__)


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration file"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        logger.error(f"Failed to load config file: {e}")
        raise


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="CuES-WebArena: Curiosity-driven Task Generation for WebArena"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default="config/config.yaml",
        help="Configuration file path"
    )
    parser.add_argument(
        "--stage",
        type=str,
        choices=["all", "stage1", "stage2", "stage3"],
        default="all",
        help="Run stage: all, stage1 (exploration), stage2 (task abstraction), stage3 (trajectory generation)"
    )
    parser.add_argument(
        "--session-name",
        type=str,
        help="Session name for this run"
    )
    parser.add_argument(
        "--input-file",
        type=str,
        help="Input data file (for stage2/stage3 mode)"
    )
    parser.add_argument(
        "--task-name",
        type=str,
        default=None,
        help="Specific WebArena task to explore (e.g., webarena.0)"
    )
    parser.add_argument(
        "--website",
        type=str,
        choices=["shopping", "shopping_admin", "gitlab", "reddit", "map"],
        default=None,
        help="Website to explore"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--requirement",
        type=str,
        help="Specific exploration requirement (e.g., 'only explore shopping cart functionality')"
    )
    parser.add_argument(
        "--extract-concepts",
        action="store_true",
        default=False,
        help="Extract concept sets from the environment before exploration"
    )
    parser.add_argument(
        "--rewrite",
        "--query-rewrite",
        dest="rewrite",
        action="store_true",
        default=False,
        help="Enable Query Rewrite after Stage 3 to diversify queries"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config_path = Path(__file__).parent / args.config
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        return 1
    
    config = load_config(str(config_path))
    
    # Override config with command line arguments
    if args.headless:
        config['environment']['headless'] = True
    if args.website:
        config['environment']['website'] = args.website
    if args.task_name:
        config['environment']['task_name'] = args.task_name
    
    logger.info(f"Loaded configuration file: {config_path}")
    
    # Validate API key
    api_key = config.get('api', {}).get('api_key')
    if not api_key:
        # Try environment variable
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY")
        if api_key:
            config['api']['api_key'] = api_key
        else:
            logger.error("Please set API key in configuration file or environment variable")
            return 1
    
    # Create data directory
    data_dir = Path(__file__).parent / config.get('data_dir', './data')
    data_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Threading configuration: max_workers={config['threading']['max_workers']}, enabled={config['threading']['enabled']}")
    
    # Create pipeline
    pipeline = CuESPipeline(config)
    
    logger.info("=" * 60)
    logger.info("CuES-WebArena: Curiosity-driven Task Generation")
    logger.info("=" * 60)
    
    concepts = None
    
    if args.stage == "all":
        logger.info("Running full three-stage pipeline...")
        if args.requirement:
            logger.info(f"Exploration requirement: {args.requirement}")
        
        if args.extract_concepts:
            logger.info("=== Stage 0: Concept Extraction ===")
            concepts = pipeline.extract_concepts(
                max_workers=config['threading']['max_workers']
            )
            logger.info(f"Extracted concept sets: {concepts}")
        
        result = pipeline.run_full_pipeline(
            session_name=args.session_name,
            requirement=args.requirement,
            concepts=concepts
        )
        
        if result['success']:
            logger.info("🎉 Pipeline executed successfully!")
            logger.info(f"Session ID: {result['session_id']}")
            logger.info(f"Generated triplets: {result['triplets_count']}")
            logger.info(f"Abstracted tasks: {result['tasks_count']}")
            logger.info(f"Generated trajectories: {result.get('trajectories_count', 0)}")
            
            stats = result.get('statistics', {})
            if stats:
                triplet_stats = stats.get('triplets', {})
                task_stats = stats.get('tasks', {})
                trajectory_stats = stats.get('trajectories', {})
                
                logger.info("\n📊 Statistics:")
                logger.info(f"  Average triplet reward: {triplet_stats.get('avg_reward', 0):.3f}")
                logger.info(f"  Task success rate: {triplet_stats.get('success_rate', 0):.3f}")
                logger.info(f"  Average task confidence: {task_stats.get('avg_confidence', 0):.3f}")
                logger.info(f"  High confidence tasks: {task_stats.get('high_confidence_tasks', 0)}")
                logger.info(f"  Trajectory success rate: {trajectory_stats.get('success_rate', 0):.3f}")
            
            if args.rewrite:
                logger.info("=== Stage 4: Query Rewrite ===")
                rewrite_cfg = config.get('rewrite', {})
                rewrite_result = pipeline.run_query_rewrite(
                    trajectories_dir=str(data_dir / "trajectories"),
                    batch_size=rewrite_cfg.get('batch_size', 10),
                    num_variants=rewrite_cfg.get('num_variants', 3),
                    session_name=args.session_name
                )
                if rewrite_result.get('success'):
                    logger.info("📝 Query Rewrite finished.")
                    logger.info(f"Rewritten samples: {rewrite_result.get('rewritten_count', 0)}")
        else:
            logger.error(f"Pipeline failed: {result.get('error', 'Unknown error')}")
            return 1
    
    elif args.stage == "stage1":
        logger.info("=== Running Stage 1: Curious Exploration ===")
        if args.requirement:
            logger.info(f"Exploration requirement: {args.requirement}")
        
        if args.extract_concepts:
            concepts = pipeline.extract_concepts(
                max_workers=config['threading']['max_workers']
            )
            logger.info(f"Extracted concept sets: {concepts}")
        
        result = pipeline.run_stage1(
            session_name=args.session_name,
            requirement=args.requirement,
            concepts=concepts
        )
        
        if result['success']:
            logger.info(f"✅ Stage 1 completed, generated {result['triplets_count']} triplets")
            logger.info(f"Output file: {result['output_file']}")
        else:
            logger.error(f"Stage 1 failed: {result.get('error', 'Unknown error')}")
            return 1
    
    elif args.stage == "stage2":
        logger.info("=== Running Stage 2: Task Abstraction ===")
        
        input_file = args.input_file
        if not input_file:
            # Find latest triplets file
            triplets_dir = data_dir / "triplets"
            if triplets_dir.exists():
                triplet_files = list(triplets_dir.glob("*.jsonl"))
                if triplet_files:
                    input_file = str(max(triplet_files, key=lambda f: f.stat().st_mtime))
                    logger.info(f"Using latest triplets file: {input_file}")
                else:
                    logger.error("No triplets files found. Please run stage1 first.")
                    return 1
            else:
                logger.error("Triplets directory not found. Please run stage1 first.")
                return 1
        
        result = pipeline.run_stage2(
            input_file=input_file,
            session_name=args.session_name
        )
        
        if result['success']:
            logger.info(f"✅ Stage 2 completed, abstracted {result['tasks_count']} tasks")
            logger.info(f"Output file: {result['output_file']}")
        else:
            logger.error(f"Stage 2 failed: {result.get('error', 'Unknown error')}")
            return 1
    
    elif args.stage == "stage3":
        logger.info("=== Running Stage 3: Trajectory Generation ===")
        
        input_file = args.input_file
        if not input_file:
            # Find latest tasks file
            tasks_dir = data_dir / "tasks"
            if tasks_dir.exists():
                task_files = list(tasks_dir.glob("*.jsonl"))
                if task_files:
                    input_file = str(max(task_files, key=lambda f: f.stat().st_mtime))
                    logger.info(f"Using latest tasks file: {input_file}")
                else:
                    logger.error("No tasks files found. Please run stage2 first.")
                    return 1
            else:
                logger.error("Tasks directory not found. Please run stage2 first.")
                return 1
        
        result = pipeline.run_stage3(
            input_file=input_file,
            session_name=args.session_name
        )
        
        if result['success']:
            logger.info(f"✅ Stage 3 completed, generated {result['trajectories_count']} trajectories")
            logger.info(f"Success rate: {result['statistics']['success_rate']:.2%}")
        else:
            logger.error(f"Stage 3 failed: {result.get('error', 'Unknown error')}")
            return 1
        
        if args.rewrite:
            logger.info("=== Stage 4: Query Rewrite ===")
            rewrite_cfg = config.get('rewrite', {})
            rewrite_result = pipeline.run_query_rewrite(
                trajectories_dir=str(data_dir / "trajectories"),
                batch_size=rewrite_cfg.get('batch_size', 10),
                num_variants=rewrite_cfg.get('num_variants', 3),
                session_name=args.session_name
            )
            if rewrite_result.get('success'):
                logger.info("📝 Query Rewrite finished.")
                logger.info(f"Rewritten samples: {rewrite_result.get('rewritten_count', 0)}")
    
    logger.info("=" * 60)
    logger.info("CuES-WebArena execution completed")
    logger.info("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
