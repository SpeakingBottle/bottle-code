# 项目速览

- 名称：Mini Agent，一个用来学 AI Agent 的脚手架。
- 语言：Python 3.13。
- 许可：MIT。
- 模型接入：OpenAI 兼容 API，默认配置 DeepSeek（https://api.deepseek.com/v1）。
- 核心模块：tools.py（工具）、llm.py（模型后端）、agent.py（主循环）、memory/（长期记忆）。
- 已实现工具：calculator、list_dir、read_file、write_file、remember、recall、run_shell、final_answer、kb_search。
- 循环上限：max_steps，默认 12 步。
- 输出约定：任务结束必须调用 final_answer。

# 部署步骤

1. 安装依赖：`pip install -r requirements.txt`。
2. 配置环境变量：复制 `.env.example` 为 `.env`，填入 `OPENAI_API_KEY`（或 `ANTHROPIC_AUTH_TOKEN`）。
3. 离线验证：`python -m mini_agent.main --provider mock`，不需要 key 就能看到 Agent 循环。
4. 接真实模型：`python -m mini_agent.main --provider openai --model gpt-4o-mini`。
5. 建知识库索引：`python examples/build_kb.py`（词频版）或 `python examples/rag_eval.py`（embedding 版）。
6. 跑 CodeOps 演示：`python examples/codeops_demo.py --provider anthropic`。
