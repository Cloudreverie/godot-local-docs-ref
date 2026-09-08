# godot-local-docs-ref

`godot-local-docs-ref` 是一个以本地、版本匹配的 Godot 官方文档为依据的 Codex Skill。本文件面向项目所有者和维护此仓库的 Agent，用于解释整体设计、权威边界和安全迭代流程；运行时行为以 [SKILL.md](SKILL.md) 为准。

当前验证基线是 Godot 4.7，但构建与检索接口按版本组织，不把 Skill 的能力限制在 4.7。项目范围聚焦本地文档构建与只读核实，Godot Editor 和 MCP 自动化属于其他能力。

## 语言约定

规则正文、解释与维护说明使用中文。机器解析的键名，以及已定义的角色名、模式名、字段名、状态值、接口名、文件名和路径保持原有英文拼写。一般技术叙述使用中文，不因涉及技术概念而保留整段英文。

此约定适用于手工维护的文档、界面说明、脚本注释和面向用户的说明文字。用于匹配官方文档的英文术语、原文引用、检索样例和测试语料保留原文，以维持检索与解析行为。`references/` 中的内容由工具自动生成，不纳入人工审核和修订。

## 工作原理

`Godot godot-docs` → `build_godot_docs.py` → `manifest + Markdown` → `search_godot_docs.py` → `SKILL.md` 指导 Agent 应用有来源位置的证据。

构建脚本是语料的唯一写入者。搜索脚本只读取已生成语料；启用使用日志时可在语料之外追加记录。Skill 运行时发现语料缺失时会报告缺失，由部署者决定何时构建。

## 权威来源

| 文件或目录 | 负责的事实 |
| --- | --- |
| [SKILL.md](SKILL.md) | Skill 触发条件、版本选择、检索与证据应用规则 |
| [agents/openai.yaml](agents/openai.yaml) | UI 展示文本和隐式调用策略 |
| [scripts/build_godot_docs.py](scripts/build_godot_docs.py) | 上游解析、构建、转换、校验和原子发布行为 |
| [scripts/search_godot_docs.py](scripts/search_godot_docs.py) | 查询解析、结构化提取、排序和输出格式 |
| [scripts/record_godot_docs_feedback.py](scripts/record_godot_docs_feedback.py) | 可选的 Agent 简短评价记录 |
| [tests/](tests/) | 可执行的行为契约与真实 Godot 语料回归 |
| `references/godot-docs/<version>/` | 生成物；`manifest.json` 记录版本、commit、文件与校验信息 |

生成的 Markdown、manifest、来源说明和许可证文件应由构建脚本统一重建，不在语料目录内手工修补。

新的维护 Agent 应先阅读本文件和 `SKILL.md`，再按任务读取相关脚本与测试。README 是维护地图；新增约束应写入真正负责该行为的文件，并在架构、工作流或已知限制变化时同步更新这里。

## 构建本地语料

首次构建当前基线：

```bash
python3 -B scripts/build_godot_docs.py --version 4.7
```

脚本需要 Python 3.10+、网络连接和临时磁盘空间，并会下载完整的固定版本源码。重新生成已有版本时使用 `--force`；构建器会先准备并校验新语料，再替换现有目录。GitHub API 遇到匿名限流时，可通过环境变量提供 `GITHUB_TOKEN`。其余构建与复用选项以 `python3 scripts/build_godot_docs.py --help` 为准。

## 开发与验证

按改动选择验证：修复问题时先用实际查询或最小样例复现，再补充针对性回归测试；仅修改说明文字时检查含义、链接和 Skill 格式即可。只有改动依赖官方页面结构时才需要真实语料回归，并遵循当前任务对 `references/` 的访问约束。

```bash
# 需要完整回归时运行（包含真实语料测试）
python3 -B -m unittest discover -s tests -v

# 修改 Skill 指令或界面元数据后
python3 -B ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py .

# 搜索冒烟测试
python3 -B scripts/search_godot_docs.py "Node.queue_free" --version 4.7 --show-best
python3 -B scripts/search_godot_docs.py "Vector2(1, 2)" --version 4.7 --show-best
python3 -B scripts/search_godot_docs.py "input actions" --version 4.7
```

小幅排序或摘要调整先检查受影响的查询；较大的检索算法或架构改造，再比较代表性任务的准确性、输出量和耗时。无需每次维护都开展完整任务评测。

## 日志与反馈

两项功能都默认关闭。个人使用时，可先启用简短评价，收集 Agent 遇到的具体问题或有用发现；需要复现搜索过程或分析耗时时，再开启自动日志。不必同时配置，也不要求每次调用都反馈。

```bash
# 按需选择其中一项，并让 Agent 的检索子进程继承该环境变量
export GODOT_DOCS_FEEDBACK_FILE="$HOME/.local/state/godot-local-docs-ref/feedback.jsonl"
export GODOT_DOCS_LOG_FILE="$HOME/.local/state/godot-local-docs-ref/usage.jsonl"
```

取消对应环境变量即可关闭。记录本地保存，不自动上传。文件需为语料目录及 `references/` 之外的 `.jsonl` 文件；写入失败不会阻断开发任务。

评价只需实际查询、文档版本和一句具体观察，例如“哪条查询遇到了什么，最后怎样解决”。等级、来源和任务标识均可选，调用示例见 `SKILL.md`。自动日志由搜索脚本生成，无需 Agent 手工整理。

积累几条反馈后按需集中查看，优先处理重复出现且能复现的问题。反馈是改进线索，不是正确性证明；没有固定报表、评价配额或定期清理要求，日志按需要归档或删除。

<details>
<summary>自动日志的参数和字段（仅配置或分析时阅读）</summary>

也可在单次检索中使用 `--log-file /absolute/path/usage.jsonl`。优先级为 `--no-log` 关闭本次记录、`--log-file` 指定位置、`GODOT_DOCS_LOG_FILE` 提供默认位置；两个命令行选项互斥。取消环境变量即可恢复默认关闭。建议使用绝对路径，相对路径按调用时的工作目录解释。

每次完成的检索追加一行 JSON，`schema_version` 当前为 `1`。记录包含 UTC 时间 `timestamp`、`script_version`、`query`、`requested_version`、可用时的实际 `godot_version` 和 `source_commit`、检索参数、`duration_ms`、`exit_code` 与 `status`。成功完成搜索时还包含展示的 `result_count`、`results` 中的路径、行号、类别、评分及截断标记，以及 `warnings`；失败时包含 `error`。配置任务标识后记录 `task_id`。

`status` 为 `ok`（有结果）、`no_matches`（无结果）或 `error`（参数范围或语料错误）。`ok` 不等于回答正确；本日志无法观察 Agent 的手工补读、证据应用和最终开发结果。参数解析阶段的错误（如未知选项）及进程中断不保证有记录。

日志不包含文档摘要或完整对话；查询原文上限为 2000 字符，超出时设置 `query_truncated`，错误信息上限为 1000 字符，任务标识上限为 200 字符。查询和错误仍可能带有项目名称或路径。日志仅本地追加，不自动上传或清理，部署者可按需要归档或删除；运行测试时宜取消日志环境变量，避免测试调用混入真实反馈。

日志文件必须位于语料目录及 `references/` 之外，并以 `.jsonl` 结尾。写入失败仅在 stderr 提示，保留原检索输出和退出码，不影响 JSON 输出格式。

</details>

<details>
<summary>简短评价的参数和字段（仅配置或分析时阅读）</summary>

`--outcome` 无需填写；填写时可选 `helpful`、`partial`、`unhelpful`、`uncertain`，省略时记录 `uncertain`，表示未作等级判断。`--reason` 必填，`--source`（实际结果的 `path:line`）和 `--follow-up` 可选。单条最多 10 个查询和 10 个来源，查询每项最多 2000 字符，理由、来源及补救说明每项最多 400 字符。自定义语料需通过 `--docs-root` 指定，其目录也被排除在可写范围之外。

脚本追加 JSONL，字段包含 `schema_version`（当前为 `1`）、`script_version`、`event_type=feedback`、`author=agent`、`timestamp`、`godot_version`、`queries`、`outcome`、`reason`、`sources`，以及可选的 `follow_up` 和 `task_id`。使用与检索日志相同的 `GODOT_DOCS_TASK_ID` 可结合版本、查询和来源进行任务级关联；也可通过 `--task-id` 指定，保存时最多 200 字符。脚本不读取语料，版本、来源及评价均为 Agent 提交的信息，未经自动核实。

`--log-file` 可单次指定反馈文件，`--no-log` 可禁用本次反馈；两者互斥，命令行设置优先于环境变量。未配置时跳过写入，取消 `GODOT_DOCS_FEEDBACK_FILE` 即恢复默认关闭。存储位置约束、追加方式和写入失败处理复用搜索日志机制；建议反馈与搜索日志分文件保存，按需归档，均不自动上传。

</details>

## 手动部署

完整部署建议包含 `SKILL.md`、`agents/`、`scripts/search_godot_docs.py`，以及目标版本的 `references/godot-docs/<version>/manifest.json` 和 Markdown 文件。部署构建工具和测试文件由个人维护方式决定。

需要 Agent 评价时，同时部署 `scripts/record_godot_docs_feedback.py`，与 `search_godot_docs.py` 放在同一目录，以复用日志写入逻辑。

可以把本仓库复制或软链接到个人 Skill 目录。部署后从目标目录运行一条精确 API 查询和一条概念查询，并确认输出版本与目标项目一致。替换现有部署前保留上一份可用目录或链接目标，验证通过后再清理旧版本。

## 维护不变量

- 文档版本、来源 commit 和文件清单以生成语料的 `manifest.json` 为准。
- `build_godot_docs.py` 负责所有语料下载和写入；`search_godot_docs.py` 对语料只读且不触发构建，仅在显式启用时向语料之外追加使用日志。
- 显式 `Class.member` 查询只在该类及其文档继承链中解析，不回退到无关概念结果。
- 输出保持有界：默认前三项包含摘要，其余结果仅提供索引；精确查询可使用 `--show-best`。
- 生成语料保留 Godot 文档与类参考各自的来源说明和许可证文件。

## 当前设计边界

- 构造函数调用按参数数量筛选，不进行参数类型推断。`--show-best` 隐藏其他匹配重载时会提示歧义；JSON 输出通过 `warnings` 列表提供提示，无提示时为空列表。
- 整页结果仅预览正文前 24 行；行数或字符数限制导致省略时标记 `truncated`，需按来源路径补读。
- 对没有独立构造声明的 Object 派生类，`.new()` 返回准确的类文档，不虚构签名。
- 概念搜索为保留召回可能返回词项相关结果；应用前应检查结果类别、路径和摘要。
- 当前真实语料回归以 Godot 4.7 为基线；增加版本时应保留版本隔离并重新运行相同验证。
