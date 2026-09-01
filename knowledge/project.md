# 项目速览

- 名称：Mini Agent，一个用来学 AI Agent 的脚手架。
- 语言：Python 3.13。
- 许可：MIT。
- 模型接入：OpenAI 兼容 API，默认配置 DeepSeek（https://api.deepseek.com/v1）。
- 核心模块：tools.py（工具）、llm.py（模型后端）、agent.py（主循环）、memory/（长期记忆）。
- 已实现工具：calculator、list_dir、read_file、write_file、remember、recall、run_shell、final_answer、kb_search。
- 循环上限：max_steps，默认 12 步。
- 输出约定：任务结束必须调用 final_answer。
