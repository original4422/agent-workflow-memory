# Experience Demo 运行说明

## 环境准备
- 使用仓库自带虚拟环境：`myenv/webarena`（Python 3.10+）
- 安装依赖：
	- `myenv/webarena/bin/pip install -r webarena/demo/experience_demo/requirements.txt`
	- `myenv/webarena/bin/python -m playwright install`
- 设置 WebArena 站点环境变量（必须，示例见 plan/plan.md；核心是 `WA_SHOPPING_ADMIN` 等）
- 准备登录态：`webarena/demo/experience_demo/.auth/shopping_admin_state.json`

### storage_state 怎么生成？
本 demo 不做 auto-login。

你需要用 Playwright 先登录一次 shopping_admin，并把 context 的 `storage_state` 保存到：
`webarena/demo/experience_demo/.auth/shopping_admin_state.json`

建议方式：直接写一个一次性的本地脚本/命令在有界面模式下完成登录，然后保存 storage_state。

## 运行方式
从仓库根目录运行（推荐）：

- 单次 baseline：
	- `myenv/webarena/bin/python webarena/demo/experience_demo/run_demo.py --use_experience false`
- 单次 with-experience：
	- `myenv/webarena/bin/python webarena/demo/experience_demo/run_demo.py --use_experience true --top_k 3`
- 跑对比套件（baseline 3 次 + with-experience 3 次，并生成报告）：
	- `myenv/webarena/bin/python webarena/demo/experience_demo/run_demo.py --suite true --n_runs 3 --top_k 3`

常用参数：
- `--obs_mode axtree|html|both`（默认 axtree）
- `--headless true|false`（调试建议 false）
- `--slow_mo 0|30|200`（调试可加大）
- `--max_steps 30`

## 目录结构与产物说明

- 经验库：`webarena/demo/experience_demo/experience/experiences.jsonl`
- embedding 缓存：`webarena/demo/experience_demo/experience/.cache/`
- 运行产物：`webarena/demo/experience_demo/results/`
	- 每次 run 会生成一个 BrowserGym experiment 目录（含 `summary_info.json`、每步 screenshot 等）
	- suite 模式会额外生成 `report.json`/`report.md`

更多细节：见 plan/plan.md 与 plan/task.md
