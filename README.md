# godot-local-docs-ref

`godot-local-docs-ref` 是一个以本地、版本匹配的 Godot 官方文档为依据的 Codex Skill。本文件面向项目所有者和维护此仓库的 Agent，用于解释整体设计、权威边界和安全迭代流程；运行时行为以 [SKILL.md](SKILL.md) 为准。

当前验证基线是 Godot 4.7，但构建与检索接口按版本组织，不把 Skill 的能力限制在 4.7。项目范围聚焦本地文档构建与只读核实，Godot Editor 和 MCP 自动化属于其他能力。

## 工作原理

`Godot godot-docs` → `build_godot_docs.py` → `manifest + Markdown` → `search_godot_docs.py` → `SKILL.md` 指导 Agent 应用有来源位置的证据。

构建脚本是语料的唯一写入者。搜索脚本只读取已生成语料；Skill 运行时发现语料缺失时会报告缺失，由部署者决定何时构建。

## 权威来源

| 文件或目录 | 负责的事实 |
| --- | --- |
| [SKILL.md](SKILL.md) | Skill 触发条件、版本选择、检索与证据应用规则 |
| [agents/openai.yaml](agents/openai.yaml) | UI 展示文本和隐式调用策略 |
| [scripts/build_godot_docs.py](scripts/build_godot_docs.py) | 上游解析、构建、转换、校验和原子发布行为 |
| [scripts/search_godot_docs.py](scripts/search_godot_docs.py) | 查询解析、结构化提取、排序和输出格式 |
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

修改前先用一个真实查询或最小合成样例定义失败和预期结果。解析、排序或输出机制应有独立单元测试；依赖官方页面结构或项目真实用法的行为应补充 4.7 语料回归。

```bash
# 完整测试
python3 -B -m unittest discover -s tests -v

# 修改 Skill 指令或界面元数据后
python3 -B ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py .

# 搜索冒烟测试
python3 -B scripts/search_godot_docs.py "Node.queue_free" --version 4.7 --show-best
python3 -B scripts/search_godot_docs.py "Vector2(1, 2)" --version 4.7 --show-best
python3 -B scripts/search_godot_docs.py "input actions" --version 4.7
```

排序或摘要变更应使用代表性查询比较精准度、召回率和输出字符数，并在复杂变更后进行独立前向验证。

## 手动部署

完整部署建议包含 `SKILL.md`、`agents/`、`scripts/search_godot_docs.py`，以及目标版本的 `references/godot-docs/<version>/manifest.json` 和 Markdown 文件。部署构建工具和测试文件由个人维护方式决定。

可以把本仓库复制或软链接到个人 Skill 目录。部署后从目标目录运行一条精确 API 查询和一条概念查询，并确认输出版本与目标项目一致。替换现有部署前保留上一份可用目录或链接目标，验证通过后再清理旧版本。

## 维护不变量

- 文档版本、来源 commit 和文件清单以生成语料的 `manifest.json` 为准。
- `build_godot_docs.py` 负责所有下载和写入；`search_godot_docs.py` 保持只读且不触发构建。
- 显式 `Class.member` 查询只在该类及其文档继承链中解析，不回退到无关概念结果。
- 输出保持有界：默认前三项包含摘要，其余结果仅提供索引；精确查询可使用 `--show-best`。
- 生成语料保留 Godot 文档与类参考各自的来源说明和许可证文件。

## 当前设计边界

- 构造函数调用按参数数量筛选，不进行参数类型推断。
- 对没有独立构造声明的 Object 派生类，`.new()` 返回准确的类文档，不虚构签名。
- 概念搜索为保留召回可能返回词项相关结果；应用前应检查结果类别、路径和摘要。
- 当前真实语料回归以 Godot 4.7 为基线；增加版本时应保留版本隔离并重新运行相同验证。
