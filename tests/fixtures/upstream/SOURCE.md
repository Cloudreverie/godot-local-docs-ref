# 官方 HTML 回归样本

这三个样本取自 Godot 4.7 官方英文文档，供离线转换与检索回归使用。采集日期、来源链接、完整下载文件及保存片段的 SHA-256 见 [provenance.json](provenance.json)。文档作者为 Godot Engine contributors；类参考采用 [MIT](LICENSE-GODOT.txt)，手册采用 [CC-BY-3.0](LICENSE-GODOT-DOCS.txt)。

保存时只提取实际页面的 `h1` 和指定章节，并添加最小 HTML 外壳；选中节点的内容保持原样，导航和其他章节已省略：

- `classes/class_vector2.html`：完整的 `Constructor Descriptions` 章节，覆盖四个构造重载。
- `classes/class_@globalscope.html`：`Enumerations` 标题与完整的 `Variant.Type` 枚举及枚举值。
- `tutorials/animation/introduction.html`：完整的 `Computer animation relies on keyframes` 章节。

`reference_source_commit` 固定用于对照的 `godot-docs` 源码版本。文档站点未提供 HTML 的构建 commit，因此不能认定该源码 commit 就是快照的渲染来源；HTML 样本本身由哈希固定。测试使用占位 `.rst`，直接转换 HTML，不执行 Sphinx，也不读写 `references/`。

这些样本不包含 `.article-status`；页面状态与继承默认值仍由相邻 `conversion/` 中明确标为手写的结构样例覆盖。样本只验证所保留内容，不能代替完整官方语料的正确性或性能基准。更新样本时重新核对来源、选择范围、许可证和哈希，并运行 `test_conversion_pipeline.py`。
