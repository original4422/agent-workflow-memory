#!/bin/bash

# Demo script - test timestamped output folder

echo "================================"
echo "WebArena Task Generator Test"
echo "================================"
echo ""

cd "$(dirname "$0")"

echo "Test 1: generate tasks in --demo mode"
echo "Output will be saved under ./generated_task/ (timestamped subfolder)"
echo ""

python main.py --demo --num-intents 3

echo ""
echo "================================"
echo "Generated files:"
echo "================================"
ls -lh generated_task/

echo ""
echo "Done! Generated task files are under generated_task/"
