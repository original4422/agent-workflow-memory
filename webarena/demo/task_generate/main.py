#!/usr/bin/env python3
"""
================================================================================
main.py - WebArena 任务自动生成工具
================================================================================
基于 CuES (Curiosity-driven and Environment-grounded Synthesis) 方法的轻量级实现。

【功能概述】
从给定的网页 (URL 或 HTML 文件) 自动生成符合 WebArena 格式的 Task 数据。

【使用方式】
1. 从 URL 生成:
   python main.py --url "http://example.com/admin"

2. 从 HTML 文件生成:
   python main.py --file "./sample.html"

3. 使用示例 HTML (演示模式):
   python main.py --demo

【输出】
生成的任务将保存到 ./generated_tasks.json
================================================================================
"""

import argparse
import sys
import os
from datetime import datetime

# 确保可以导入本地模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config, APIConfig, WebArenaConfig, GenerationConfig
from generator import TaskGenerationPipeline
from utils import JSONHandler


# ================================================================================
# 示例 HTML (用于演示模式)
# ================================================================================

DEMO_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Magento Admin - Dashboard</title>
</head>
<body>
    <div class="admin-header">
        <h1>Dashboard</h1>
        <nav>
            <a href="/admin/sales/order">Orders</a>
            <a href="/admin/catalog/product">Products</a>
            <a href="/admin/customer">Customers</a>
            <a href="/admin/reports">Reports</a>
        </nav>
    </div>
    
    <div class="dashboard-content">
        <div class="stats-widget">
            <h2>Lifetime Sales</h2>
            <p>$1,234,567.89</p>
        </div>
        
        <div class="stats-widget">
            <h2>Average Order</h2>
            <p>$125.50</p>
        </div>
        
        <div class="recent-orders">
            <h2>Recent Orders</h2>
            <table>
                <tr><th>Order ID</th><th>Customer</th><th>Total</th><th>Status</th></tr>
                <tr><td>100001</td><td>John Doe</td><td>$199.99</td><td>Complete</td></tr>
                <tr><td>100002</td><td>Jane Smith</td><td>$89.50</td><td>Processing</td></tr>
                <tr><td>100003</td><td>Bob Johnson</td><td>$450.00</td><td>Pending</td></tr>
            </table>
        </div>
        
        <div class="top-products">
            <h2>Best Selling Products (2023)</h2>
            <ol>
                <li>Impulse Duffle - 1,234 units</li>
                <li>Overnight Duffle - 987 units</li>
                <li>Quest Lumaflex Band - 876 units</li>
                <li>Sprite Yoga Companion Kit - 654 units</li>
                <li>Driven Backpack - 543 units</li>
            </ol>
        </div>
        
        <div class="customer-stats">
            <h2>Customer Statistics</h2>
            <ul>
                <li>Total Customers: 15,678</li>
                <li>New Customers (This Month): 234</li>
                <li>Top Customer: Emma Wilson ($12,345 total)</li>
            </ul>
        </div>
        
        <div class="search-section">
            <h3>Search Products</h3>
            <input type="text" placeholder="Enter product name or SKU" name="product_search">
            <button>Search</button>
        </div>
        
        <div class="quick-actions">
            <button>Add New Product</button>
            <button>Create Order</button>
            <button>View All Reports</button>
        </div>
    </div>
</body>
</html>
"""


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="WebArena 任务自动生成工具 (基于 CuES 方法)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 演示模式 (使用内置示例 HTML)
  python main.py --demo

  # 从 URL 生成任务
  python main.py --url "http://166.111.53.249:7780/admin"

  # 从本地 HTML 文件生成
  python main.py --file "./page.html"

  # 自定义生成数量和输出文件夹
  python main.py --demo --num-intents 10 --output-dir "./my_tasks"

  # 使用 OpenAI API
  python main.py --demo --api-type openai --api-key "sk-xxx"
        """
    )
    
    # 输入源 (互斥)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--url",
        type=str,
        help="目标网页 URL"
    )
    input_group.add_argument(
        "--file",
        type=str,
        help="本地 HTML 文件路径"
    )
    input_group.add_argument(
        "--demo",
        action="store_true",
        help="使用内置示例 HTML (演示模式)"
    )
    
    # 生成配置
    parser.add_argument(
        "--num-intents",
        type=int,
        default=5,
        help="生成的任务数量 (默认: 5)"
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.7,
        help="最低置信度阈值 (默认: 0.7)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./generated_task",
        help="输出文件夹路径 (默认: ./generated_task)"
    )
    
    # WebArena 配置
    parser.add_argument(
        "--site",
        type=str,
        default="shopping_admin",
        help="目标网站类型 (默认: shopping_admin)"
    )
    parser.add_argument(
        "--start-url",
        type=str,
        default="http://166.111.53.249:7780/admin",
        help="任务起始 URL"
    )
    
    # API 配置
    parser.add_argument(
        "--api-type",
        type=str,
        choices=["azure", "openai"],
        default="azure",
        help="API 类型: azure (cloudgpt) 或 openai (默认: azure)"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="OpenAI API Key (当 --api-type=openai 时需要)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-20241120-2",
        help="模型名称 (默认: gpt-4o-20241120-2)"
    )
    
    # 其他选项
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="显示详细输出"
    )
    parser.add_argument(
        "--start-id",
        type=int,
        default=0,
        help="起始任务 ID (默认: 0)"
    )
    
    return parser.parse_args()


def build_config(args) -> Config:
    """
    根据命令行参数构建配置对象
    
    Args:
        args: 解析后的命令行参数
        
    Returns:
        Config 对象
    """
    # API 配置
    api_config = APIConfig(
        api_type=args.api_type,
        openai_api_key=args.api_key,
        model_name=args.model
    )
    
    # WebArena 配置
    webarena_config = WebArenaConfig(
        sites=[args.site],
        base_url=args.start_url
    )
    
    # 生成配置
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
    根据输入源获取 HTML 内容
    
    Args:
        args: 解析后的命令行参数
        
    Returns:
        HTML 内容字符串
    """
    if args.demo:
        print("[INFO] 使用内置示例 HTML (演示模式)")
        return DEMO_HTML
    
    elif args.file:
        print(f"[INFO] 从文件读取: {args.file}")
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            print(f"[错误] 文件不存在: {args.file}")
            sys.exit(1)
        except Exception as e:
            print(f"[错误] 读取文件失败: {e}")
            sys.exit(1)
    
    elif args.url:
        print(f"[INFO] 从 URL 获取: {args.url}")
        try:
            import requests
            response = requests.get(args.url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"[错误] 获取 URL 失败: {e}")
            sys.exit(1)
    
    return ""


def print_banner():
    """打印程序横幅"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║           WebArena Task Generator (CuES-Lite)                                ║
║                                                                              ║
║    基于 CuES 方法的轻量级实现，自动生成 WebArena 格式的任务数据              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)


def print_summary(tasks, output_file, elapsed_time):
    """打印生成摘要"""
    print("\n" + "=" * 60)
    print("【生成完成】")
    print("=" * 60)
    print(f"  ✅ 生成任务数: {len(tasks)}")
    print(f"  📄 输出文件: {output_file}")
    print(f"  ⏱️  耗时: {elapsed_time:.2f} 秒")
    print()
    
    if tasks:
        print("【生成的任务预览】")
        print("-" * 60)
        for i, task in enumerate(tasks[:3], 1):
            intent = task.get("intent", "N/A")
            if len(intent) > 60:
                intent = intent[:57] + "..."
            print(f"  {i}. {intent}")
        if len(tasks) > 3:
            print(f"  ... 还有 {len(tasks) - 3} 个任务")
        print()


def main():
    """主函数"""
    # 解析参数
    args = parse_args()
    
    # 打印横幅
    print_banner()
    
    # 构建配置
    config = build_config(args)
    
    # 显示配置信息
    print("【配置信息】")
    print(f"  API 类型: {config.api.api_type}")
    print(f"  模型: {config.api.model_name}")
    print(f"  目标网站: {config.webarena.sites}")
    print(f"  生成数量: {config.generation.num_intents}")
    print(f"  置信度阈值: {config.generation.min_confidence}")
    print()
    
    # 获取 HTML 内容
    html_content = get_html_content(args)
    
    if not html_content:
        print("[错误] 未能获取 HTML 内容")
        sys.exit(1)
    
    print(f"[INFO] HTML 内容大小: {len(html_content)} 字节")
    print()
    
    # 开始计时
    import time
    start_time = time.time()
    
    # 创建 Pipeline 并运行
    try:
        pipeline = TaskGenerationPipeline(config)
        tasks = pipeline.run(
            html_content=html_content,
            num_intents=config.generation.num_intents,
            start_task_id=args.start_id
        )
    except Exception as e:
        print(f"\n[错误] Pipeline 执行失败: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
    
    # 计算耗时
    elapsed_time = time.time() - start_time
    
    # 保存结果
    if tasks:
        # 创建输出文件夹
        os.makedirs(config.generation.output_dir, exist_ok=True)
        
        # 生成带时间戳的文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = config.generation.output_filename.format(timestamp=timestamp)
        output_path = os.path.join(config.generation.output_dir, filename)
        
        JSONHandler.save(tasks, output_path)
        print_summary(tasks, output_path, elapsed_time)
    else:
        print("\n[警告] 未能生成任何有效任务")
        print("可能的原因:")
        print("  1. HTML 内容不足以推断任务")
        print("  2. 生成的任务置信度过低")
        print("  3. LLM API 调用失败")
    
    return 0 if tasks else 1


if __name__ == "__main__":
    sys.exit(main())
