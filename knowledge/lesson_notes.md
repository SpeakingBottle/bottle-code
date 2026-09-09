# 课程笔记

## 第2课：最小闭环
实现了多工具串行任务，并新增 run_shell 工具（白名单沙箱，只允许只读检查命令）。

## 第3课：提示词工程
学习了系统提示词，并用 final_answer 做结构化输出（终止工具，防死循环）。

## 第4课：记忆 + RAG
短期记忆用滑动窗口（max_context_messages 裁剪历史）；长期记忆用 remember/recall 写笔记；
最小 RAG 用词频向量 + 余弦相似度检索知识库（knowledge.py）。

## 第5课：规划 + ReAct
系统提示词加计划字段（先输出 1~3 步计划再执行）；写入后必须用 read_file 自验证。

## 第6课：多 Agent + MCP
多 Agent 分工：规划者拆步、执行者动手、评审者验证，JSON 消息协议 + 重试；
MCP 协议接入外部工具（repo-stats server：count_loc / list_files / git_status）。

## 第7课：可靠性 + 评测
- 7A 权限最小化：执行层白名单检查，越权调用返回 [SECURITY] 拦截，不执行。
- 7B 审计与轨迹：append-only JSONL 审计日志 + 内存 trace，单一漏斗 _record_trace。
- 7C 评测集：4 个任务 × 5 维判定（expect / must_use / file / no_secret / no_abuse），退出码可进 CI。

## 第8课：整合 + 打磨
Bottle Code 合成层（codeops.py）：Orchestrator + MCP repo-stats + 审计接线成一个入口；
演示 codeops_demo.py 一个任务同时考验 MCP + RAG + 写文件 + 多 Agent + 审计。

## 第9课：生产级 RAG
- 9A embedding + 向量库：fastembed（BAAI/bge-small-zh-v1.5）+ Chroma 持久化，接口与词频版一致；kb_search 优先 embedding、缺依赖回退词频。
- 9B 混合检索：手写 BM25 + 向量 RRF 排名融合（use_hybrid=False 退化为纯向量）。
- 9C 检索评估：8 查询 × hit@3 对比三方案；知识库补全（project.md 部署步骤、lesson_notes 第4~8课、新增 architecture.md / troubleshooting.md）。
- 9D 查：混合 100% > 词频 88% = embedding 88%；评测逮住两个坏评测项；语义改写查询是 embedding 强项。

### 第9课复盘（心智模型沉淀）

**Q1：为什么混合检索 > 单一方案？**
不同查询需要不同信号：精确术语（"部署步骤"）→ BM25 词面匹配强；语义改写（"怎么把服务跑起来"）→ embedding 泛化强。RRF 融合不是"两个都试取最好"，而是让两种信号互补——且 RRF 按排名取分（1/(k+rank)），天然规避两种分数量纲不同的问题，不用调权重。

**Q2：为什么词频版和 embedding 版打平（88% = 88%）？**
知识库小（10 块）、查询贴近原文，词面重叠足够，词频版已经够用；embedding 的优势只在"词面不重叠但语义相关"的查询上显现。**结论：评测结果取决于数据规模——小库上别迷信更高级的算法，先看数据。**

**Q3：评测逮住两个坏评测项说明了什么？**
你以为 project.md 有部署内容、lesson_notes.md 有第7课内容，实际没有——检索查不到，是因为数据里根本没有。**检索质量的上限由数据决定，不是由算法决定：先补数据，再谈算法。** 评测的价值正在于此：逼你验证对数据的假设。

**Q4：换个场景会怎样？**
- 知识库变大（几百上千块）：词面重叠率下降，词频版掉得厉害，embedding 优势拉开。
- 查询全是精确术语（API 名/函数名）：BM25 可能反而更好，embedding 的泛化是噪声。
- 生产实践：混合检索 + 按查询类型路由（术语查询走 BM25，自然语言走向量）。

**Q5：工程取舍**
embedding 版依赖 fastembed（首次下载模型），词频版零依赖；kb_search 的 fallback（优先 embedding、缺依赖回退词频）让系统在依赖缺失时仍可用。**依赖是成本，回退是保险。**

## 第10课：Bottle Code 网页版
- 10A 流式输出：llm.py chat_stream() + agent.py run(stream=True) 生成器，事件协议 delta/tool/result。
- 10B FastAPI 后端：POST /api/chat 把事件转 SSE，补发 done/error；session_id 会话记忆。
- 10C Vue 前端：Vite + Vue 3 消费 SSE，reactive 包裹避免流式文本静默丢失；刷新恢复历史（chat_logs 展示记录与 Agent.history 模型上下文分离）。
- 10D~10F 打磨：磨砂玻璃 + 苔藓背景、轨迹抽屉（thinking/prompt/tool）、思考动画、步数上限。
- 10G 会话历史：sessions.json 落盘持久化 + 列表/改名/删除 + 侧栏切换。

## 第11课：代码 Agent 闭环
- 11A run_python 执行工具：分层沙箱（工作目录内 + shell=False + 30s 超时 + 输出截断）。
- 11B 闭环演示：写代码 → run_python 跑测试 → 失败改到通过；"改"是闭环真正发力的地方。
- 练习11A 编码闭环评测器：隐藏测试独立验证产物，不盲信 Agent 自述。
- 11C 步数上调 + 目标锚定：滑动窗口裁掉用户问题后钉回窗口最前。
- 11D 空响应级联修复：注入失败反馈打破确定性复现 + 连空上限 + max_tokens 8192。
