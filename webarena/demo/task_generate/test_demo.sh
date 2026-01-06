#!/bin/bash

# 演示脚本 - 测试时间戳命名功能

echo "================================"
echo "WebArena Task Generator 测试"
echo "================================"
echo ""

cd "$(dirname "$0")"

echo "测试 1: 使用 --demo 模式生成任务"
echo "输出将保存到 ./generated_task/ 文件夹，文件名包含时间戳"
echo ""

python main.py --demo --num-intents 3

echo ""
echo "================================"
echo "查看生成的文件:"
echo "================================"
ls -lh generated_task/

echo ""
echo "完成！生成的任务文件位于 generated_task/ 文件夹中"
