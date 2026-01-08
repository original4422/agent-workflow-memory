import time
from typing import Dict, Any, Tuple
from urllib.parse import urlparse, parse_qs
import gymnasium as gym
import browsergym.core  # 确保安装了 browsergym
from browsergym.core.task import AbstractBrowserTask
from browsergym.core.env import BrowserEnv
from playwright.sync_api import Page

import browsergym.webarena # get registered WebArena EnvSpecs

class MySimpleSearchTask(AbstractBrowserTask):
    """
    一个自定义任务示例：在 Bing 上搜索 'WebArena' 并通过检查 URL 参数验证成功。
    """
    def __init__(self, seed: int = 42):
        super().__init__(seed=seed)
        self.target_query = "WebArena code quality"

    def setup(self, page: Page) -> Tuple[str, dict]:
        """
        环境初始化：打开目标网站，设置初始状态。
        """
        # 1. 导航到目标网站
        page.goto("https://www.bing.com")
        
        # 2. (可选) 处理一些弹窗或 Cookie 同意栏 (这是硬编码不可避免的部分)
        try:
            # 这里的 selector 需要根据实际网页调整
            reject_btn = page.query_selector("button#bnp_btn_reject")
            if reject_btn: reject_btn.click()
        except:
            pass

        # 3. 返回任务描述 (Prompt)
        goal = f"Please search for '{self.target_query}' on Bing."
        info = {} # 可以在这里放一些额外的元数据
        return goal, info

    def validate(self, page: Page, logs: list) -> Tuple[float, bool, str, dict]:
        """
        评测逻辑：这是最关键的部分。
        不要去查数据库，直接查 Page 状态。
        Returns: (reward, done, message, info)
        """
        current_url = page.url
        content = page.content().lower()

        # Prefer parsing URL query params over brittle substring checks.
        parsed = urlparse(current_url)
        query_params = parse_qs(parsed.query)
        q_value = (query_params.get("q") or [""])[0].strip().lower()

        # 逻辑 A: 检查 URL 是否包含搜索参数 (最稳健的方式)
        # 例如 bing 的搜索结果页通常包含 /search?q=...
        if "/search" in parsed.path and q_value == self.target_query.lower():
            return 1.0, True, "Success: URL query matches search query.", {}
        
        # 逻辑 B: 检查页面标题或特定元素 (作为备选)
        if f"{self.target_query}" in page.title().lower():
             return 1.0, True, "Success: Page title matches query.", {}

        # 失败或未完成
        return 0.0, False, "Task not completed yet.", {}

    def teardown(self):
        """清理工作"""
        pass

# --- 如何运行这个自定义任务 ---

def run_manual_test():
    # 1. 直接实例化 BrowserEnv。
    # 注意：不要用 gym.make("browsergym/openended", task_entrypoint=...)
    # 因为该 env id 在注册时已经固定了默认 task_entrypoint，再传一次会冲突。

    # env = gym.make(id = "browsergym/webarena.0", task_entrypoint=MySimpleSearchTask,)
    
    env = BrowserEnv(
        task_entrypoint=MySimpleSearchTask,
        headless=False,  # 设置为 False 可以看到浏览器动作
        wait_for_user_message=False,
        use_raw_page_output=True,
    )

    obs, info = env.reset()
    print(f"Goal: {obs['goal']}")

    # 3. 模拟 Agent Loop (这里用人工手动输入代替 Agent，方便调试)
    # 在真实场景中，这里就是你的 Agent 代码
    print("环境已启动。请在弹出的浏览器中手动操作，或者在代码里写死 Action。")
    print("正在监听 Reward 变化...")
    
    for _ in range(50):
        # 这里的 action 应该是 Agent 生成的代码
        # 为了演示，我们发一个空动作，只是为了触发 step() 里的 validate
        action = None
        
        obs, reward, done, truncated, info = env.step(action)
        print(f"Current Reward: {reward}, Done: {done}")
        
        if reward > 0:
            print(f"🎉 任务成功! Reward: {reward}")
            break
        
        time.sleep(1) # 轮询检查

    env.close()

if __name__ == "__main__":
    run_manual_test()