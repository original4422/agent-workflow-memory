"""
Query Rewrite Stage
Diversify task queries by generating semantically equivalent variants.
"""
import json
from typing import List, Dict, Any, Optional
from pathlib import Path

from ..core.api_client import APIClient
from ..utils.logger import get_logger

logger = get_logger(__name__)


class QueryRewriter:
    """Rewrite queries to create diverse training data"""
    
    def __init__(self, client: APIClient):
        self.client = client
    
    def run(
        self,
        trajectories_dir: str,
        batch_size: int = 10,
        num_variants: int = 3,
        output_dir: str = None
    ) -> Dict[str, Any]:
        """Run query rewrite on trajectories"""
        import time
        start_time = time.time()
        
        input_path = Path(trajectories_dir)
        if not input_path.exists():
            return {"success": False, "error": f"Directory not found: {trajectories_dir}"}
        
        # Find trajectory files
        trajectory_files = list(input_path.glob("trajectory_*.json"))
        if not trajectory_files:
            return {"success": False, "error": "No trajectory files found"}
        
        logger.info(f"Found {len(trajectory_files)} trajectory files for rewrite")
        
        # Output directory
        out_path = Path(output_dir) if output_dir else input_path / "rewrites"
        out_path.mkdir(parents=True, exist_ok=True)
        
        rewritten_count = 0
        batch = []
        batch_files = []
        
        for file_path in sorted(trajectory_files, key=lambda f: f.stat().st_mtime):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    trajectory = json.load(f)
                
                batch.append(trajectory)
                batch_files.append(file_path)
                
                if len(batch) >= batch_size:
                    count = self._process_batch(batch, batch_files, num_variants, out_path)
                    rewritten_count += count
                    batch = []
                    batch_files = []
                    
            except Exception as e:
                logger.warning(f"Skipping invalid file {file_path.name}: {e}")
        
        # Process remaining batch
        if batch:
            count = self._process_batch(batch, batch_files, num_variants, out_path)
            rewritten_count += count
        
        elapsed = time.time() - start_time
        
        return {
            "success": True,
            "rewritten_count": rewritten_count,
            "output_dir": str(out_path),
            "elapsed_time": elapsed
        }
    
    def _process_batch(
        self,
        trajectories: List[Dict[str, Any]],
        source_files: List[Path],
        num_variants: int,
        output_dir: Path
    ) -> int:
        """Process a batch of trajectories"""
        count = 0
        
        for trajectory, source_file in zip(trajectories, source_files):
            query = trajectory.get('query', '')
            messages = trajectory.get('messages', [])
            task_id = trajectory.get('task_id', source_file.stem.replace('trajectory_', ''))
            
            if not query or not messages:
                continue
            
            try:
                variants = self._generate_variants(query, messages, num_variants)
                
                for i, variant in enumerate(variants, 1):
                    # Clone trajectory with new query
                    new_trajectory = trajectory.copy()
                    new_trajectory['query'] = variant
                    new_trajectory['original_query'] = query
                    new_trajectory['variant_id'] = i
                    
                    # Save
                    output_file = output_dir / f"trajectory_{task_id}_v{i}.json"
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(new_trajectory, f, indent=2, default=str)
                    
                    count += 1
                    
            except Exception as e:
                logger.warning(f"Rewrite failed for {source_file.name}: {e}")
        
        return count
    
    def _generate_variants(
        self,
        original_query: str,
        messages: List[Dict[str, str]],
        num_variants: int
    ) -> List[str]:
        """Generate query variants using LLM"""
        # Build context from messages
        context = ""
        for msg in messages[:5]:  # First few messages for context
            role = msg.get('role', '')
            content = msg.get('content', '')[:200]
            context += f"{role}: {content}\n"
        
        prompt = f"""Generate {num_variants} semantically equivalent but differently worded versions of this task query.

Original query: {original_query}

Context (conversation excerpt):
{context}

Requirements:
1. Each variant should express the same task goal
2. Use different wording and sentence structure
3. Maintain the same level of specificity
4. Keep variants natural and grammatically correct

Output format: Return ONLY a JSON array of strings, like:
["variant 1", "variant 2", "variant 3"]"""
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            response = self.client.chat_with_retry(messages, max_retries=2)
            
            if response:
                # Parse JSON array
                import re
                json_match = re.search(r'\[.*?\]', response, re.DOTALL)
                if json_match:
                    variants = json.loads(json_match.group())
                    return variants[:num_variants]
                    
        except Exception as e:
            logger.warning(f"Failed to generate variants: {e}")
        
        return []
