#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filter configuration entries by site names.

Usage: python filter.py <site_name1> [site_name2 ...] [--input INPUT_FILE] [--output OUTPUT_FILE]
Example: python filter.py shopping_admin
Example: python filter.py map shopping_admin
Example: python filter.py shopping_admin --output custom_output.json
"""

import json
import sys
from pathlib import Path


def filter_by_sites(site_names, input_file="test.raw.json", output_file=None):
    """
    Filter JSON records by the given site names.

    Args:
        site_names: List of site names to filter, e.g. ["shopping_admin"] or ["map", "shopping_admin"].
        input_file: Input JSON file path, defaults to "test.raw.json".
        output_file: Output JSON file path, defaults to "{site_names}.raw.json".
    """
    # Ensure site_names is a list
    if isinstance(site_names, str):
        site_names = [site_names]
    
    # Determine default output filename
    if output_file is None:
        output_file = f"{'_'.join(sorted(site_names))}.raw.json"
    
    # Locate the script directory
    script_dir = Path(__file__).parent
    input_path = script_dir / input_file
    output_path = script_dir / output_file
    
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
    
    # Keep entries that include any of the requested sites
    filtered_data = []
    for item in data:
        if "sites" in item:
            # Check if there's any intersection between item's sites and requested site_names
            if any(site in item["sites"] for site in site_names):
                filtered_data.append(item)
    
    # Persist filtered results
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(filtered_data, f, ensure_ascii=False, indent=2)
    
    print("Filter complete!")
    print(f"Input file: {input_path}")
    print(f"Output file: {output_path}")
    print(f"Filter sites: {site_names}")
    print(f"Total records: {len(filtered_data)}")


def main():
    """Entry point for CLI execution."""
    if len(sys.argv) < 2:
        print("Usage: python filter.py <site_name1> [site_name2 ...] [--input INPUT_FILE] [--output OUTPUT_FILE]")
        print("Example: python filter.py shopping_admin")
        print("Example: python filter.py map shopping_admin")
        print("Example: python filter.py shopping_admin --input test.raw.json --output shopping_admin.raw.json")
        sys.exit(1)
    
    # Parse command line arguments
    args = sys.argv[1:]
    site_names = []
    input_file = "test.raw.json"
    output_file = None
    
    i = 0
    while i < len(args):
        if args[i] == "--input" and i + 1 < len(args):
            input_file = args[i + 1]
            i += 2
        elif args[i] == "--output" and i + 1 < len(args):
            output_file = args[i + 1]
            i += 2
        else:
            site_names.append(args[i])
            i += 1
    
    if not site_names:
        print("Error: at least one site name is required")
        sys.exit(1)
    
    filter_by_sites(site_names, input_file, output_file)


if __name__ == "__main__":
    main()
