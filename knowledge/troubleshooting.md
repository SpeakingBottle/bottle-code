# 常见问题排查

## 越权调用被拦截

现象：Agent 调用工具时返回 `[SECURITY] 越权调用已拦截`。
原因：执行层"职责边界"裁决生效——模型报出的工具不在 allowed_tools 里，直接拒绝执行。
注意：`read` 类工具豁免这条边界（读从不越权），所以 `read_file`/`grep` 不会因此被拦；
只有职责外的 `write`/`execute` 才会。
处理：检查该角色的 allowed_tools 是否漏配；或让模型下一轮自纠（拒绝消息里带了允许列表）。

## 危险操作未获批准

现象：Agent 调用工具时返回 `[APPROVAL] 操作未获批准: xxx（risk=write）`。
原因：该工具是 `write`/`execute` 级，且审批者拒绝了它。
  用 `DenyAllApprover` 时必然如此（严格模式）；用 `TerminalApprover` 时可能是
  你输了 n，或**运行环境读不到 stdin**（被重定向/非交互）——后者一律按拒绝处理
  （fail-closed：不能因为"问不到人"就默认放行）。
处理：换 `AllowAllApprover`，或交互式运行时输 y / a（a = 本次会话内同类风险全批准）。

## 修改前必须先读取

现象：`edit_file` 返回 `[PRECONDITION] 修改前必须先 read_file 读取: xxx`。
原因：`edit_file` 的前置条件是"这个文件在本会话里被见过内容"。
  登记来源有两个：`read_file` 读过，或 `write_file` 亲手写过。
处理：先 `read_file` 读一遍再改。这不是找麻烦——`old_string` 要和磁盘内容逐字符
  一致（含缩进、空行），不先看原文基本一定会"未找到"。

## edit_file 报 old_string 不唯一

现象：`edit_file` 返回 `old_string 在 xxx 中出现 N 次，不唯一`。
原因：要替换的那段文本在文件里出现了多次，工具无法确定改哪一处。
处理：扩大 `old_string` 的范围（多带几行上下文）使它唯一；确实要全改就传 `replace_all=true`。
设计意图：自动挑第一个出现看着方便，实际是**静默猜意图**，猜错的代价远大于多问一轮。

## 审计日志没写盘

现象：跑了 Agent 但 logs/agent.jsonl 没有新事件。
原因：AuditLogger 的 enabled=False，或 Agent 构造时没传 audit 参数。
处理：`Agent(llm, audit=AuditLogger())` 即可；enabled=False 用于评测等不想污染日志的场景。

## 评测任务失败

现象：eval_harness 里某个任务判定 ✗。
处理：看判定明细——expect 是结果不对，must_use 是没用对工具，
no_abuse 是"出现了被拦截的调用"（`[SECURITY]`/`[APPROVAL]`/`[PRECONDITION]` 任一）。
注意：`no_abuse` 判的是"越权**尝试**"而不是"越权成功"——执行层已保证后者不可能发生，
所以真正有信息量的是模型有没有试图越界。也不能用「用到的工具 ⊆ allowed_tools」来判：
read 类工具已豁免职责边界，合法放行却会出现在 trace 里，那样判会误伤 no_leak 这类
"写入 + 自验证"任务。

## 权限最小化 vs "写入后验证"的张力（已解决）

现象：角色白名单只给了 `write_file`，模型想按规则 10 用 `read_file` 自验证，却被执行层拦下。

这曾经是设计张力（7C 评测的 no_leak 任务就是踩在这里），现已由 **read 豁免**解决：
执行层的职责边界裁决对 `read` 类工具放行——读从不越权，而"写入后自验证"需要它。
`write`/`execute` 才同时受职责边界与审批约束。

read 豁免带来的暴露面（任何角色都能读 `BASE_DIR` 内的文件，含 `.env`）另由
**敏感路径拒绝**堵上：见下条。

## 敏感路径不允许读取

现象：`read_file` 或 `grep` 返回 `[SENSITIVE] 敏感路径不允许读取: .env`。
原因：这条拒绝与**危险等级无关**，是**内容级**的——路径本身就是机密，读都不该读。
  起因是 read 类工具豁免了职责边界，任何角色的 Agent 都能读 `BASE_DIR` 内的文件，
  包括仓库根那个装着真实 key 的 `.env`；旧模型下 `allowed_tools` 能挡住，豁免之后挡不住了。
被拒的路径：`.env*`（含 `.env.local` 等）、`.git/` `.ssh/` `.aws/` `.gnupg/` 等目录下、
  `*.key` `*.pem` `*.p12` `*.pfx` `*.keystore` `*.jks`、以及名字含
  `secret` / `credential` / `password` / `id_rsa` / `id_ed25519` 的文件。
不受影响：**写路径照旧**（`write_file` 到敏感路径仍可用，仍走职责边界 + 审批）。
  `grep` **走查目录时静默跳过**敏感文件（仓库里有 `.env` 是常态，为它让整次搜索
  报错不可接受）；只有**显式指定**敏感文件为搜索起点时才报 `[SENSITIVE]`。
注意：`edit_file` 到敏感路径会直接报 `[SENSITIVE]` 而不是"先 read_file"——
  否则模型会照做、又被拒、来回空转。

## 知识库检索不到内容

现象：kb_search 返回空或无关结果。
处理：先跑 examples/build_kb.py 重建索引；确认 knowledge/ 下有 .md 文件；
如果用了 embedding 版，确认 chroma/ 目录存在且 build_index 成功。
