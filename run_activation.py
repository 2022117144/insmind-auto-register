"""从 token_input.txt 读取 token 激活 tenant"""
import asyncio, json, sys
sys.path.insert(0, "E:/视频生成/dreamina-auto-register-main")
from activate_account import activate_and_test

with open("E:/视频生成/dreamina-auto-register-main/token_input.txt") as f:
    token = f.read().strip()

asyncio.run(activate_and_test(token, "5haq6ju07m@bwmyga.com"))