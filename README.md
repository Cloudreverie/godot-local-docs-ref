# godot-local-docs-ref

[中文](#中文) | [English](#english)

## 中文

为 AI 编程助手提供与项目版本匹配的本地 Godot 官方文档检索，减少 API 猜测和版本混用。

项目包含独立运行的 Python 工具和供 Agent 使用的 [SKILL.md](SKILL.md)，聚焦本地文档核实，不操作 Godot Editor。能执行脚本并读取本地文件的助手可使用这些工具；Skill 的自动识别与加载方式取决于所用助手。

### 快速开始

#### 直接运行脚本

需要 Python 3.10+。首次构建需要网络连接和临时磁盘空间，会下载固定版本的上游源码。以下以 Godot 4.7 为例，请替换为项目使用的版本。

在仓库根目录构建语料并验证检索：

```bash
python3 -B scripts/build_godot_docs.py --version 4.7
python3 -B scripts/search_godot_docs.py "Node.queue_free" --version 4.7 --show-best
python3 -B scripts/search_godot_docs.py "input actions" --version 4.7
```

语料生成在 `references/godot-docs/<version>/`，不纳入 Git。重新构建已有版本时加 `--force`。更多选项见[构建与排错](#构建与排错)及脚本 `--help`。

#### 作为 Skill 使用

按所用助手的 Skill 安装方式部署包含已生成语料的仓库，保留目录结构和许可证文件。若助手不支持直接加载，可让它读取 `SKILL.md` 并按其中规则调用脚本。

按需精简部署时，保留 `SKILL.md`、搜索脚本及目标版本的完整语料。`agents/openai.yaml` 是 Codex 适配配置，供其展示 Skill 和配置调用策略；其他助手是否需要适配文件，以各自要求为准。

部署后，从目标目录运行上述两条检索，确认返回版本正确。替换已有部署时，验证通过后再清理旧版本。运行时 Agent 只检索已有语料，缺失时由部署者构建。

### 输出说明

`--version` 要求与 manifest 版本严格一致，即使同时使用 `--docs-root` 也会检查；只提供 `--docs-root` 时采用 manifest 版本。两者都省略时仍使用默认的 `4.7` 目录，并核对版本。脚本不自动将 `4.x.y` 映射为 `4.x`，项目与文档版本的使用约定见 [SKILL.md](SKILL.md#选择文档版本)。

JSON 输出包含以下证据信息；文本输出会在相关结果旁提示：

| 字段 | 含义 |
| --- | --- |
| `requested_version` / `godot_version` | 显式请求的版本（未指定为 `null`）与实际语料版本 |
| `corpus_coverage` | `full` 表示 manifest 记录为完整构建，`partial` 表示只构建了部分页面，`unknown` 表示旧 manifest 未提供此信息；不代表已检查所有文件的完整性 |
| `missing_ancestors` | 当前成员检索在找到定义前缺少的祖先页面 |
| `ambiguous` | 是否仍有多个适用候选，即使 `--show-best` 或 `--limit` 只展示一项也会报告；普通概念搜索的多个相关页面不属于此类 |
| `target_class` / `declaring_class` | 成员查询的目标类（未限定时为 `null`）与返回声明所属的类 |
| `document_default` | 属性的文档默认值（`value` 为文档字面量字符串）及其 `title`、`path`、`line`、`excerpt` 来源；按最近的覆盖取值，原声明摘要保持不变。未确认时为 `null`，`truncated` 为 `true` 时需补读 |

退出码为 `0`（有结果）、`1`（无匹配）、`2`（输入或语料错误）。部分语料与缺失祖先通过元数据及 `warnings` 区分；搜索日志同步记录覆盖情况、缺失祖先和歧义状态。

`auto` / `member` 模式中，将 `Class.member` 与其他词项混写而无匹配时，会在文本、JSON 的 `warnings` 和检索日志中提示拆分，退出码为 `1`。概念查询以完整类名开头时，标题排序优先匹配该类，避免将 `ShaderMaterial` 的拆词前缀误当成 `Shader`。

`auto` 模式也接受按官方大小写拼写的完整类名后接单个成员名，例如 `ResourceSaver FLAG_CHANGE_PATH`；找到声明时直接返回成员证据，继承、默认值和歧义规则与 `Class.member` 一致。找不到声明时继续概念检索；返回类页面不代表已确认该成员存在。需要严格核实 API 时优先使用 `Class.member`。

综合排序保留完整类名的加分，手册页面仍按相关性参与排序。全文检索先排除不可能命中的页面，并在一次查询内复用章节解析；不创建持久索引或修改语料。

### 检索日志

在实际调用的 Skill 根目录创建 `config.local.json`（可复制 `config.example.json`），无需配置终端环境变量：

```json
{
  "LOG_FILE": "usage.jsonl"
}
```

路径表示启用，`null` 或空字符串表示关闭。配置文件中的相对路径以 Skill 目录为准，与 Agent 工作目录无关，也支持绝对路径和 `~`。上面的配置将检索日志保存在 Skill 根目录；配置文件和 `usage.jsonl` 已被 Git 忽略。启用后由搜索脚本自动记录，首次实际记录时才创建日志文件。

命令行 `--log-file` / `--no-log` 可覆盖本地配置；`--log-file` 的相对路径以执行命令时的工作目录为准。没有配置文件或 `LOG_FILE` 时默认关闭；不再读取 `GODOT_DOCS_LOG_FILE`，已有环境变量无需清理也不会启用记录。配置损坏时提示并跳过记录，不影响检索。

配置不会随 Git 同步。若 Skill 安装在另一目录，请在实际安装目录创建配置；更新部署时保留它。日志需为语料目录及 `references/` 之外的 `.jsonl` 文件，仅本地保存，写入失败不会阻断检索。

其他参数见搜索脚本的 `--help`。查询和错误可能包含本地路径，分享前检查内容。

跨项目分析时，可将各项目的 `usage.jsonl` 复制为 `usage-samples/<项目名>.jsonl`，保留原件供项目继续记录。该目录已被 Git 忽略，准备迭代时手动更新副本；有价值的问题再提炼为回归测试。

### 构建与排错

遇到 GitHub API 匿名限流时，可通过环境变量提供 `GITHUB_TOKEN`。

#### 部分构建

用 `--only` 做部分页面构建时，必须显式指定独立的 `--output`，不能与默认版本目录相同、嵌套或包含该目录。例如在 macOS/Linux 上：

```bash
python3 -B scripts/build_godot_docs.py --version 4.7 --only classes/class_node.rst --output /tmp/godot-docs-smoke-4.7
```

已有非空输出目录只有在 manifest 明确记录为部分语料时才能用 `--only --force` 替换；完整语料、缺少或损坏 manifest 的目录都会被拒绝。检查在下载前和发布前执行，`--force` 不会绕过保护。

`--only` 仅限制生成的页面；未使用 `--reuse-workdir` 时，需要下载完整源码归档。

#### 失败日志与缓存复用

构建成功后默认清理临时工作目录。工作目录创建后发生失败或中断时，会保留该目录中的 `build.log` 并报告路径，清理其他临时产物；即使尚未启动子进程，也会记录失败原因。需要保留全部产物时使用 `--keep-workdir`。

`--reuse-workdir <目录>` 复用其中的 `godot-docs.zip` 和 `venv/`，但每次都会在新的工作目录中重新解压源码，避免使用被修改过的旧源码树。原缓存保留，后续复用仍指定含归档和虚拟环境的原缓存目录。

#### 构建环境

构建子进程仅继承必要的系统、代理和证书配置，不继承 `GITHUB_TOKEN` 等 API 密钥、Python 路径或 pip 源配置，并禁用 pip 配置文件。依赖默认从公共 PyPI 安装；私有源配置不自动沿用。代理地址中的凭据仍会传入子进程，这项措施不提供沙箱隔离。

### 维护

| 入口 | 内容 |
| --- | --- |
| [SKILL.md](SKILL.md) | 触发条件、版本选择、检索限制与证据应用 |
| [agents/openai.yaml](agents/openai.yaml) | Codex 适配：界面文案和隐式调用策略 |
| [构建脚本](scripts/build_godot_docs.py) | 下载、转换、校验和发布语料 |
| [搜索脚本](scripts/search_godot_docs.py) | 查询、排序、结果输出与自动日志 |
| [测试](tests/) | 行为契约与真实语料回归 |

修改前阅读本文件和 Skill，再按任务查看实现与测试。行为规则写在负责该行为的文件中，README 保留使用和维护入口。

语料版本与来源以生成目录的 `manifest.json` 为准。构建脚本统一生成 Markdown、manifest、来源说明与许可证；不手工修补生成物。搜索对语料只读，日志另存。

README 使用中英双语，修改时同步两种语言。其他手工维护的说明、界面文案和脚本注释使用中文；机器标识、官方英文术语、引用和测试语料保留原文。

修复问题时先复现，再补针对性回归测试；调整排序时检查受影响查询，较大改动再比较代表性任务的准确性、输出量和耗时。仅修改文档时检查含义、链接和格式；修改 Skill 或界面元数据时检查 Skill 格式。

快速单元测试不需要转换依赖或生成语料：

```bash
python3 -B -m unittest discover -s tests -p 'test_build_godot_docs.py'
python3 -B -m unittest discover -s tests -p 'test_search_godot_docs.py'
```

转换回归使用 `tests/fixtures/conversion/` 中手写的 Sphinx HTML 结构样例，实际执行转换器和检索脚本，生成物全部位于临时目录。它覆盖表格、默认值覆盖、继承、重载、警告和代码块，不需要读取 `references/`，也不执行完整 Sphinx 构建。

在独立虚拟环境中安装与 `CONVERTER_REQUIREMENTS` 一致的依赖后运行（以下为 macOS/Linux 示例；Windows 使用 `.venv\Scripts\python.exe`）：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install beautifulsoup4==4.15.0 markdownify==1.2.3
.venv/bin/python -B -m unittest discover -s tests -p 'test_conversion_pipeline.py' -v
```

缺少依赖或版本不匹配时，这组测试会明确失败，不以跳过表示通过。需要完整回归时，在上述环境中准备真实语料，再运行 `.venv/bin/python -B -m unittest discover -s tests -v`。

[GitHub CI](.github/workflows/ci.yml) 在推送和 Pull Request 时，使用 Python 3.10、3.13 分别执行上述三组隔离测试。转换依赖直接采用构建脚本中的版本约束；CI 不下载 Godot 语料、不读取 `references/`、不运行完整 Sphinx 构建。真实语料回归仍由维护者在需要时单独运行。

当前真实语料回归基线为 Godot 4.7；增加版本时保持语料隔离并执行相同验证。

### 许可证

本项目的原创脚本、测试、Skill 配置与说明文件采用 [MIT License](LICENSE)，版权署名为 Cloudreverie。

Godot 生成语料保留上游许可证：普通文档采用 CC BY 3.0，类参考采用 MIT，署名为 Juan Linietsky、Ariel Manzur 和 Godot 社区。详见 [上游声明](https://github.com/godotengine/godot-docs#license)。分发语料时保留随附许可证、`SOURCE-ATTRIBUTION.md` 及页面中的来源和许可证信息。

## English

Search a local copy of the official Godot documentation that matches your project version, reducing API guesswork and version mismatches.

This project provides standalone Python tools and a [SKILL.md](SKILL.md) for Agents. It focuses on checking local documentation and does not operate the Godot Editor. Assistants that can execute scripts and read local files can use the tools; automatic Skill discovery and loading depend on the assistant.

### Quick start

#### Run the scripts directly

Requires Python 3.10+. The first build needs network access and temporary disk space to download upstream sources pinned to a commit. The examples below use Godot 4.7; replace it with your project's version.

Build the corpus and verify search from the repository root:

```bash
python3 -B scripts/build_godot_docs.py --version 4.7
python3 -B scripts/search_godot_docs.py "Node.queue_free" --version 4.7 --show-best
python3 -B scripts/search_godot_docs.py "input actions" --version 4.7
```

The generated corpus is stored in `references/godot-docs/<version>/` and excluded from Git. Add `--force` to rebuild an existing version. See [Building and troubleshooting](#building-and-troubleshooting) and the scripts' `--help` for other options.

#### Use as a Skill

Deploy the repository together with a generated corpus using your assistant's Skill installation mechanism, preserving the directory structure and license files. If the assistant cannot load Skills directly, have it read `SKILL.md` and follow its instructions to invoke the scripts.

For a minimal deployment, retain `SKILL.md`, the search script, and the complete corpus for the target version. `agents/openai.yaml` supplies Codex display metadata and invocation policy; other assistants may require their own adapter files.

After deployment, run the two search commands above from the destination directory and confirm the returned version. When replacing a deployment, validate the new copy before removing the old version. At runtime, Agents only search existing corpora; the person deploying the Skill builds any missing corpus.

### Output reference

`--version` must exactly match the manifest version, including when `--docs-root` is also provided. With only `--docs-root`, the script uses the manifest version. When both are omitted, it uses the default `4.7` directory and checks that version. The script does not automatically map `4.x.y` to `4.x`; see [SKILL.md](SKILL.md#选择文档版本) for guidance on matching project and documentation versions.

JSON output includes the following evidence metadata. Text output shows the relevant information alongside results:

| Field | Meaning |
| --- | --- |
| `requested_version` / `godot_version` | The explicitly requested version (`null` if omitted) and the actual corpus version. |
| `corpus_coverage` | `full` means the manifest records a full build; `partial` means only selected pages were built; `unknown` means an older manifest lacks this information. This does not confirm that every file has been checked for completeness. |
| `missing_ancestors` | Ancestor pages missing during the current member search before its declaration is found. |
| `ambiguous` | Whether multiple applicable candidates remain, even if `--show-best` or `--limit` displays only one. Multiple relevant pages in a normal concept search do not count as this kind of ambiguity. |
| `target_class` / `declaring_class` | The target class of a member query (`null` if unqualified) and the class containing the returned declaration. |
| `document_default` | The property's documented default (`value` is the literal value as a string), with its source `title`, `path`, `line`, and `excerpt`. The nearest override takes precedence, while the original declaration excerpt remains unchanged. `null` means unconfirmed; `truncated: true` means the source needs further reading. |

Exit codes are `0` for results, `1` for no matches, and `2` for input or corpus errors. Partial corpora and missing ancestors are reported through metadata and `warnings`. Search logs also record coverage, missing ancestors, and ambiguity.

In `auto` / `member` mode, a query that mixes `Class.member` with other terms and returns no matches receives guidance to split it. This guidance appears in text output, JSON `warnings`, and search logs; the exit code is `1`. When a concept query starts with a full class name, title ranking favors that class instead of treating a tokenized prefix of `ShaderMaterial` as an explicit reference to `Shader`.

In `auto` mode, a full class name using its official capitalization can also be followed by a single member name, such as `ResourceSaver FLAG_CHANGE_PATH`. When a declaration is found, the search returns member evidence directly, with the same inheritance, default-value, and ambiguity rules as `Class.member`. Otherwise, it continues concept search; a returned class page does not confirm that the member exists. Prefer `Class.member` when checking a specific API strictly.

Combined ranking preserves the bonus for a full class name, while manual pages still compete by relevance. Full-text search first excludes pages that cannot match and reuses section parsing within each query. It creates no persistent index and does not modify the corpus.

### Search logs

Create `config.local.json` in the root of the Skill that is actually being invoked. You can copy `config.example.json`; no shell environment configuration is needed:

```json
{
  "LOG_FILE": "usage.jsonl"
}
```

A path enables logging; `null` or an empty string disables it. Relative paths in this file are resolved against the Skill directory, independently of the Agent's working directory. Absolute paths and `~` are also supported. The example stores logs in the Skill root; both the configuration file and `usage.jsonl` are ignored by Git. Once enabled, the search script records usage automatically and creates the log file on its first write.

The `--log-file` / `--no-log` command-line options override local configuration; relative paths passed to `--log-file` are resolved against the command's working directory. Logging is disabled when the configuration file or `LOG_FILE` is absent. `GODOT_DOCS_LOG_FILE` is no longer read, so leaving an existing environment variable in place will not enable logging. Invalid configuration produces a warning and skips logging without affecting search.

Local configuration is not synchronized through Git. If the Skill is installed elsewhere, create the configuration in that installation and preserve it during updates. Logs must be `.jsonl` files outside both the corpus directory and `references/`. They are stored locally, and write failures do not interrupt search.

See the search script's `--help` for other options. Queries and errors may contain local paths; review them before sharing.

For analysis across projects, copy each project's `usage.jsonl` to `usage-samples/<project-name>.jsonl`, keeping the original so the project can continue logging. This directory is ignored by Git. Refresh the copies manually before an iteration, then turn useful findings into regression tests.

### Building and troubleshooting

If you encounter GitHub's anonymous API rate limit, provide `GITHUB_TOKEN` through an environment variable.

#### Partial builds

Partial builds using `--only` require an explicit, separate `--output`. It must not be the default version directory, a directory inside it, or a directory containing it. For example, on macOS/Linux:

```bash
python3 -B scripts/build_godot_docs.py --version 4.7 --only classes/class_node.rst --output /tmp/godot-docs-smoke-4.7
```

An existing nonempty output directory can be replaced with `--only --force` only when its manifest explicitly identifies a partial corpus. Full corpora and directories with missing or invalid manifests are rejected. Checks run before downloading and before publishing; `--force` does not bypass them.

`--only` limits the pages generated. Without `--reuse-workdir`, the build downloads the complete source archive.

#### Failure logs and cache reuse

Temporary working directories are removed after successful builds by default. If a build fails or is interrupted after its working directory has been created, the script preserves `build.log`, reports its path, and removes other temporary artifacts. It also records failures that occur before a subprocess starts. Use `--keep-workdir` to preserve all artifacts.

`--reuse-workdir <directory>` reuses `godot-docs.zip` and `venv/` from that directory, but extracts the sources into a new working directory on every run to avoid using a modified source tree. The original cache is retained. For subsequent reuse, continue pointing to the original directory containing the archive and virtual environment.

#### Build environment

Build subprocesses inherit only essential system, proxy, and certificate settings. They do not inherit API keys such as `GITHUB_TOKEN`, Python path settings, or pip index settings, and pip configuration files are disabled. Dependencies are installed from public PyPI by default; private index settings are not automatically inherited. Credentials embedded in proxy URLs are still passed to subprocesses, so this measure does not provide sandbox isolation.

### Maintenance

| Entry point | Purpose |
| --- | --- |
| [SKILL.md](SKILL.md) | When to search, version selection, search limits, and use of evidence. |
| [agents/openai.yaml](agents/openai.yaml) | Codex display metadata and implicit invocation policy. |
| [Build script](scripts/build_godot_docs.py) | Downloading, conversion, validation, and corpus publication. |
| [Search script](scripts/search_godot_docs.py) | Queries, ranking, result output, and automatic logging. |
| [Tests](tests/) | Behavioral contracts and regression tests against a real corpus. |

Read this file and the Skill before making changes, then inspect the implementation and tests relevant to the task. Keep behavior rules in the files responsible for that behavior; use the README for usage and maintenance entry points.

The generated directory's `manifest.json` records the corpus version and provenance. The build script generates Markdown, the manifest, attribution, and licenses together; do not patch generated files manually. Search treats the corpus as read-only and stores logs separately.

The README is maintained in Chinese and English; update both versions together. Other manually maintained documentation, interface text, and script comments use Chinese. Machine identifiers, official English terminology, quotations, and test corpus content retain their original form.

When fixing a bug, reproduce it first and add a focused regression test. When changing ranking, check affected queries; for larger changes, also compare accuracy, output size, and execution time across representative tasks. For documentation-only changes, check meaning, links, and formatting. Validate Skill format when changing the Skill or its interface metadata.

The fast unit tests require neither conversion dependencies nor a generated corpus:

```bash
python3 -B -m unittest discover -s tests -p 'test_build_godot_docs.py'
python3 -B -m unittest discover -s tests -p 'test_search_godot_docs.py'
```

Conversion regression tests use handwritten Sphinx HTML fixtures in `tests/fixtures/conversion/` and execute the actual converter and search script. All generated files are placed in temporary directories. These tests cover tables, default overrides, inheritance, overloads, warnings, and code blocks. They do not read `references/` or run a full Sphinx build.

Install the dependencies specified by `CONVERTER_REQUIREMENTS` in a separate virtual environment, then run the tests. The following example is for macOS/Linux; on Windows, use `.venv\Scripts\python.exe`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install beautifulsoup4==4.15.0 markdownify==1.2.3
.venv/bin/python -B -m unittest discover -s tests -p 'test_conversion_pipeline.py' -v
```

Missing dependencies or version mismatches cause this suite to fail explicitly rather than skip tests. For a full regression run, prepare a real corpus in the environment above, then run `.venv/bin/python -B -m unittest discover -s tests -v`.

[GitHub CI](.github/workflows/ci.yml) runs the three isolated suites above on Python 3.10 and 3.13 for pushes and pull requests. Conversion dependency versions come directly from the build script. CI does not download Godot corpora, read `references/`, or run a full Sphinx build. Maintainers run real-corpus regression tests separately when needed.

The current real-corpus regression baseline is Godot 4.7. Keep corpora separate when adding versions and apply the same validation.

### License

The project's original scripts, tests, Skill configuration, and documentation are licensed under the [MIT License](LICENSE), with copyright attributed to Cloudreverie.

Generated Godot corpora retain their upstream licenses: general documentation uses CC BY 3.0, while the class reference uses MIT, with attribution to Juan Linietsky, Ariel Manzur, and the Godot community. See the [upstream notice](https://github.com/godotengine/godot-docs#license). When distributing a corpus, retain the bundled license files, `SOURCE-ATTRIBUTION.md`, and the provenance and license information in each page.
