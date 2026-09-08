# godot-local-docs-ref

为 AI 编程助手提供与项目版本匹配的本地 Godot 官方文档检索，减少 API 猜测和版本混用。

项目包含独立运行的 Python 工具和供 Agent 使用的 [SKILL.md](SKILL.md)，聚焦本地文档核实，不操作 Godot Editor。能执行脚本并读取本地文件的助手可使用这些工具；Skill 的自动识别与加载方式取决于所用助手。

## 快速开始

### 直接运行脚本

需要 Python 3.10+。首次构建需要网络连接和临时磁盘空间，会下载固定版本的上游源码。以下以 Godot 4.7 为例，请替换为项目使用的版本。

在仓库根目录构建语料并验证检索：

```bash
python3 -B scripts/build_godot_docs.py --version 4.7
python3 -B scripts/search_godot_docs.py "Node.queue_free" --version 4.7 --show-best
python3 -B scripts/search_godot_docs.py "input actions" --version 4.7
```

语料生成在 `references/godot-docs/<version>/`，不纳入 Git。重新构建已有版本时加 `--force`；遇到 GitHub API 匿名限流时，可通过环境变量提供 `GITHUB_TOKEN`。其他参数见各脚本的 `--help`。

### 作为 Skill 使用

按所用助手的 Skill 安装方式部署包含已生成语料的仓库，保留目录结构和许可证文件。若助手不支持直接加载，可让它读取 `SKILL.md` 并按其中规则调用脚本。

按需精简部署时，保留 `SKILL.md`、搜索脚本及目标版本的完整语料；使用反馈功能时还需保留反馈脚本。`agents/openai.yaml` 是 Codex 适配配置，供其展示 Skill 和配置调用策略；其他助手是否需要适配文件，以各自要求为准。

部署后，从目标目录运行上述两条检索，确认返回版本正确。替换已有部署时，验证通过后再清理旧版本。运行时 Agent 只检索已有语料，缺失时由部署者构建。

## 日志与反馈

两项功能默认关闭，按需启用，并让检索子进程继承环境变量：

```bash
# Agent 简短评价：记录遇到的问题或有用发现
export GODOT_DOCS_FEEDBACK_FILE="$HOME/.local/state/godot-local-docs-ref/feedback.jsonl"
# 自动检索日志：用于复现查询或分析耗时
export GODOT_DOCS_LOG_FILE="$HOME/.local/state/godot-local-docs-ref/usage.jsonl"
```

取消对应环境变量即可关闭，也可用 `--no-log` 关闭单次记录。日志文件需为语料目录及 `references/` 之外的 `.jsonl` 文件；记录仅本地保存，不自动上传，写入失败不会阻断检索。

查询和错误可能包含项目名称或本地路径，分享日志前应检查内容。运行测试时宜取消日志环境变量，避免混入测试记录。评价时机与调用示例见 [可选反馈](SKILL.md#可选反馈)；参数见脚本 `--help`，记录字段见下方对应实现。

## 维护

| 入口 | 内容 |
| --- | --- |
| [SKILL.md](SKILL.md) | 触发条件、版本选择、检索限制与证据应用 |
| [agents/openai.yaml](agents/openai.yaml) | Codex 适配：界面文案和隐式调用策略 |
| [构建脚本](scripts/build_godot_docs.py) | 下载、转换、校验和发布语料 |
| [搜索脚本](scripts/search_godot_docs.py) | 查询、排序、结果输出与自动日志 |
| [反馈脚本](scripts/record_godot_docs_feedback.py) | Agent 评价与记录字段 |
| [测试](tests/) | 行为契约与真实语料回归 |

修改前阅读本文件和 Skill，再按任务查看实现与测试。行为规则写在负责该行为的文件中，README 保留使用和维护入口。

语料版本与来源以生成目录的 `manifest.json` 为准。构建脚本统一生成 Markdown、manifest、来源说明与许可证；不手工修补生成物。搜索对语料只读，日志另存。

手工维护的说明、界面文案和脚本注释使用中文；机器标识、官方英文术语、引用和测试语料保留原文。

修复问题时先复现，再补针对性回归测试；调整排序时检查受影响查询，较大改动再比较代表性任务的准确性、输出量和耗时。仅修改文档时检查含义、链接和格式；修改 Skill 或界面元数据时检查 Skill 格式。

需要完整回归时运行（包含真实语料测试，需先准备语料）：

```bash
python3 -B -m unittest discover -s tests -v
```

当前真实语料回归基线为 Godot 4.7；增加版本时保持语料隔离并执行相同验证。

## 许可证

本项目的原创脚本、测试、Skill 配置与说明文件采用 [MIT License](LICENSE)，版权署名为 Cloudreverie。

Godot 生成语料保留上游许可证：普通文档采用 CC BY 3.0，类参考采用 MIT，署名为 Juan Linietsky、Ariel Manzur 和 Godot 社区。详见 [上游声明](https://github.com/godotengine/godot-docs#license)。分发语料时保留随附许可证、`SOURCE-ATTRIBUTION.md` 及页面中的来源和许可证信息。
