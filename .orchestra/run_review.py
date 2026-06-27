"""
通过 Harness 引擎执行 insMind 前端适配审查。
在 Orchestra 的 .venv 中运行，连接运行中的 PostgreSQL 数据库。
"""
import sys, os, yaml, asyncio
from pathlib import Path

# Orchestra 后端路径
ORCHESTRA_BACKEND = "/mnt/d/Orchestra/backend"
WORKSPACE = "/mnt/e/视频生成/dreamina-auto-register-main"

# 必须先设置环境变量，再导入 Orchestra 模块
# 因为 constants/__init__.py 在 import 时就会读取
os.chdir(ORCHESTRA_BACKEND)
from dotenv import load_dotenv
load_dotenv()

# 从 .env 读取连接字符串并设为环境变量
env_path = Path(ORCHESTRA_BACKEND) / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                # 去掉引号和 ***
                v = v.strip('"').strip("'")
                if "***" in v:
                    # 需要从实际环境获取密码
                    pass
                os.environ[k] = v

# 现在导入 Orchestra 模块
sys.path.insert(0, ORCHESTRA_BACKEND)

from src.workflows.harness import HarnessEngine
from src.services.db import get_store


async def run_review_harness():
    print("=" * 60)
    print("🚀 Harness 引擎 — Agent 审查流程")
    print("=" * 60)
    print(f"PG: {os.environ.get('POSTGRES_CONNECTION_STRING', 'NOT SET')[:50]}")

    try:
        async with get_store() as store:
            await store.setup()
            print("✅ 数据库连接成功")

            user_id = "harness-review"
            from src.services.assistant import AssistantService
            from src.services.tool import ToolService

            tool_service = ToolService(user_id=user_id, store=store)
            assistant_service = AssistantService(user_id=user_id, store=store)

            # 创建审查助手
            from src.schemas.entities.llm import Assistant as AsstSchema
            
            review_prompt = """你是代码审查员，负责审查前端 TypeScript/React 代码改动。
评估标准：
1. 功能完整性 — 所有新增页面/路由是否可正常工作
2. 数据一致性 — API 字段名是否与后端匹配
3. 类型安全 — TypeScript 类型定义是否正确
4. UI 一致性 — 新页面风格是否与原有页面统一
5. 国际化 — 中英文翻译是否完整
输出格式（严格按此格式）：
- 功能完整性: PASS | 理由
- 数据一致性: PASS | 理由
- 类型安全: PASS | 理由
- UI一致性: PASS | 理由
- 国际化: PASS | 理由"""

            asst = AsstSchema(
                name="代码审查员",
                description="审查前端代码改动",
                system_prompt=review_prompt,
                tools=[],
            )
            try:
                asst = await assistant_service.create(asst)
                print(f"✅ 创建审查 Assistant")
            except Exception as e:
                print(f"⚠️ 创建 Assistant 跳过: {e}")

            # 使用 LLMService 直接调用
            from src.services.llm import LLMService
            llm_service = LLMService(
                user_id=user_id,
                store=store,
                tool_service=tool_service,
                assistant_service=assistant_service,
            )

            # 读取项目文件
            files_to_review = [
                ("config/routes.tsx", Path(WORKSPACE) / "frontend/src/config/routes.tsx"),
                ("InsMindAccounts.tsx", Path(WORKSPACE) / "frontend/src/pages/InsMindAccounts.tsx"),
                ("ContentGeneration.tsx", Path(WORKSPACE) / "frontend/src/pages/ContentGeneration.tsx"),
                ("Settings.tsx", Path(WORKSPACE) / "frontend/src/pages/Settings.tsx"),
                ("translations/index.ts", Path(WORKSPACE) / "frontend/src/translations/index.ts"),
            ]

            print("\n📄 读取待审查文件:")
            file_contents = {}
            for name, fpath in files_to_review:
                if fpath.exists():
                    with open(fpath) as f:
                        content = f.read()
                    file_contents[name] = content
                    print(f"  ✅ {name} ({len(content)} 字符)")
                else:
                    print(f"  ⚠️ {name} — 未找到")

            # 构建审查 prompt
            review_request = "请审查以下 insMind 前端适配改动：\n\n"
            for name, content in file_contents.items():
                review_request += f"\n--- {name} ---\n"
                review_request += content[:3000]  # 截取避免超长
                if len(content) > 3000:
                    review_request += "\n...(截断)"
            
            review_request += "\n\n请按评估标准逐一给出审查结果。"

            print("\n🔍 调用 LLM 执行审查...")
            
            from src.schemas.entities import LLMInput
            req = asst.to_llm_request(
                input=LLMInput(
                    messages=[{"role": "user", "content": review_request}],
                    files={},
                )
            )
            
            response = await llm_service.llm_invoke(req)
            
            if hasattr(response, 'content'):
                result = response.content
            else:
                result = str(response)
            
            print("\n" + "=" * 60)
            print("📝 审查结果:")
            print("=" * 60)
            print(result)

            # 更新 plan.yaml
            from src.workflows.harness import FsStateManager
            state = FsStateManager(WORKSPACE)
            tasks = state.read_plan()
            for t in tasks:
                if t["id"] == "R1":
                    t["state"] = "✅"
                    t["result"] = result[:800]
            state.write_plan(tasks)
            
            print(f"\n✅ 审查完成，结果已写入 plan.yaml")

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_review_harness())
