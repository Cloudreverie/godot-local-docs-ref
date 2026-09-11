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

用 `--only` 做部分页面构建时，必须显式指定独立的 `--output`，不能与默认版本目录相同、嵌套或包含该目录。例如在 macOS/Linux 上：

```bash
python3 -B scripts/build_godot_docs.py --version 4.7 --only classes/class_node.rst --output /tmp/godot-docs-smoke-4.7
```

已有非空输出目录只有在 manifest 明确记录为部分语料时才能用 `--only --force` 替换；完整语料、缺少或损坏 manifest 的目录都会被拒绝。检查在下载前和发布前执行，`--force` 不会绕过保护。`--only` 仍会下载完整源码归档，只限制构建的页面。

构建子进程仅继承必要的系统、代理和证书配置，不继承 `GITHUB_TOKEN` 等 API 密钥、Python 路径或 pip 源配置，并禁用 pip 配置文件。依赖默认从公共 PyPI 安装；私有源配置不自动沿用。代理地址中的凭据仍会传入子进程，这项措施不提供沙箱隔离。

构建成功后默认清理临时工作目录。工作目录创建后发生失败或中断时，会保留该目录中的 `build.log` 并报告路径，清理其他临时产物；即使尚未启动子进程，也会记录失败原因。需要保留全部产物时使用 `--keep-workdir`。

`--reuse-workdir <目录>` 复用其中的 `godot-docs.zip` 和 `venv/`，但每次都会在新的工作目录中重新解压源码，避免使用被修改过的旧源码树。原缓存保留，后续复用仍指定含归档和虚拟环境的原缓存目录。

### 作为 Skill 使用

按所用助手的 Skill 安装方式部署包含已生成语料的仓库，保留目录结构和许可证文件。若助手不支持直接加载，可让它读取 `SKILL.md` 并按其中规则调用脚本。

按需精简部署时，保留 `SKILL.md`、搜索脚本及目标版本的完整语料；使用反馈功能时还需保留反馈脚本。`agents/openai.yaml` 是 Codex 适配配置，供其展示 Skill 和配置调用策略；其他助手是否需要适配文件，以各自要求为准。

部署后，从目标目录运行上述两条检索，确认返回版本正确。替换已有部署时，验证通过后再清理旧版本。运行时 Agent 只检索已有语料，缺失时由部署者构建。

### 检索结果与边界

`--version` 要求与 manifest 版本严格一致，即使同时使用 `--docs-root` 也会检查；只提供 `--docs-root` 时采用 manifest 版本。两者都省略时仍使用默认的 `4.7` 目录，并核对版本。脚本不自动将 `4.x.y` 映射为 `4.x`，项目与文档版本的使用约定见 [SKILL.md](SKILL.md#选择文档版本)。

JSON 保留原有字段，并补充以下证据信息；文本输出会在相关结果旁提示：

| 字段 | 含义 |
| --- | --- |
| `requested_version` / `godot_version` | 显式请求的版本（未指定为 `null`）与实际语料版本 |
| `corpus_coverage` | `full` 表示 manifest 记录为完整构建，`partial` 表示只构建了部分页面，`unknown` 表示旧 manifest 未提供此信息；不代表已检查所有文件的完整性 |
| `missing_ancestors` | 当前成员检索在找到定义前缺少的祖先页面 |
| `ambiguous` | 是否仍有多个适用候选，即使 `--show-best` 或 `--limit` 只展示一项也会报告；普通概念搜索的多个相关页面不属于此类 |
| `target_class` / `declaring_class` | 成员查询的目标类（未限定时为 `null`）与返回声明所属的类 |
| `document_default` | 属性的文档默认值（`value` 为文档字面量字符串）及其 `title`、`path`、`line`、`excerpt` 来源；按最近的覆盖取值，原声明摘要保持不变。未确认时为 `null`，`truncated` 为 `true` 时需补读 |

退出码仍为 `0`（有结果）、`1`（无匹配）、`2`（输入或语料错误）。部分语料与缺失祖先通过元数据及 `warnings` 区分，不新增退出码；搜索日志同步记录覆盖情况、缺失祖先和歧义状态。

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

快速单元测试不需要转换依赖或生成语料：

```bash
python3 -B -m unittest discover -s tests -p 'test_build_godot_docs.py'
python3 -B -m unittest discover -s tests -p 'test_search_godot_docs.py'
python3 -B -m unittest discover -s tests -p 'test_record_godot_docs_feedback.py'
```

转换回归使用 `tests/fixtures/conversion/` 中手写的 Sphinx HTML 结构样例，实际执行转换器和检索脚本，生成物全部位于临时目录。它覆盖表格、默认值覆盖、继承、重载、警告和代码块，不需要读取 `references/`，也不执行完整 Sphinx 构建。

在独立虚拟环境中安装与 `CONVERTER_REQUIREMENTS` 一致的依赖后运行（以下为 macOS/Linux 示例；Windows 使用 `.venv\Scripts\python.exe`）：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install beautifulsoup4==4.15.0 markdownify==1.2.3
.venv/bin/python -B -m unittest discover -s tests -p 'test_conversion_pipeline.py' -v
```

缺少依赖或版本不匹配时，这组测试会明确失败，不以跳过表示通过。需要完整回归时，在上述环境中准备真实语料，再运行 `.venv/bin/python -B -m unittest discover -s tests -v`。

[GitHub CI](.github/workflows/ci.yml) 在推送和 Pull Request 时，使用 Python 3.10、3.13 分别执行上述四组隔离测试。转换依赖直接采用构建脚本中的版本约束；CI 不下载 Godot 语料、不读取 `references/`、不运行完整 Sphinx 构建。真实语料回归仍由维护者在需要时单独运行。

当前真实语料回归基线为 Godot 4.7；增加版本时保持语料隔离并执行相同验证。

## 许可证

本项目的原创脚本、测试、Skill 配置与说明文件采用 [MIT License](LICENSE)，版权署名为 Cloudreverie。

Godot 生成语料保留上游许可证：普通文档采用 CC BY 3.0，类参考采用 MIT，署名为 Juan Linietsky、Ariel Manzur 和 Godot 社区。详见 [上游声明](https://github.com/godotengine/godot-docs#license)。分发语料时保留随附许可证、`SOURCE-ATTRIBUTION.md` 及页面中的来源和许可证信息。
