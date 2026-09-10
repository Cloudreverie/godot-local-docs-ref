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

构建子进程仅继承必要的系统、代理和证书配置，不继承 `GITHUB_TOKEN` 等 API 密钥、Python 路径或 pip 源配置，并禁用 pip 配置文件。依赖默认从公共 PyPI 安装；私有源配置不自动沿用。代理地址中的凭据仍会传入子进程，这项措施不提供沙箱隔离。

### 作为 Skill 使用

按所用助手的 Skill 安装方式部署包含已生成语料的仓库，保留目录结构和许可证文件。若助手不支持直接加载，可让它读取 `SKILL.md` 并按其中规则调用脚本。

按需精简部署时，保留 `SKILL.md`、搜索脚本及目标版本的完整语料；使用反馈功能时还需保留反馈脚本。`agents/openai.yaml` 是 Codex 适配配置，供其展示 Skill 和配置调用策略；其他助手是否需要适配文件，以各自要求为准。

部署后，从目标目录运行上述两条检索，确认返回版本正确。替换已有部署时，验证通过后再清理旧版本。运行时 Agent 只检索已有语料，缺失时由部署者构建。

## 日志与反馈

在实际调用的 Skill 根目录创建 `config.local.json`（可复制 `config.example.json`），无需配置终端环境变量：

```json
{
  "LOG_FILE": "usage.jsonl",
  "FEEDBACK_FILE": "feedback.jsonl"
}
```

路径表示启用，`null` 或空字符串表示关闭对应功能。相对路径以 Skill 目录为准，与 Agent 工作目录无关，也支持绝对路径和 `~`。上面的配置将两种记录保存在 Skill 根目录；配置文件和这两个日志文件已被 Git 忽略。首次实际记录时才创建日志文件，反馈仍由 Agent 按需提交，启用不会自动产生评价。

命令行 `--log-file` / `--no-log` 可覆盖本地配置。没有配置文件或对应键时默认关闭；不再读取 `GODOT_DOCS_LOG_FILE` / `GODOT_DOCS_FEEDBACK_FILE`，已有环境变量无需清理也不会启用记录。配置损坏时提示并跳过记录，不影响检索。

配置不会随 Git 同步。若 Skill 安装在另一目录，请在实际安装目录创建配置；更新部署时保留它。日志需为语料目录及 `references/` 之外的 `.jsonl` 文件，仅本地保存，写入失败不会阻断检索。

评价时机与调用示例见 [可选反馈](SKILL.md#可选反馈)；其他参数见脚本 `--help`。查询和错误可能包含本地路径，分享前检查内容。

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
