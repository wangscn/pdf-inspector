---
name: pdf-to-markdown
description: 本地把 PDF 分类并转成 Markdown，基于 pdf-inspector（Rust 内核，毫秒级，默认不 OCR）。当用户要求把 PDF 转 Markdown 或纯文本、提取 PDF 正文/表格/标题、判断 PDF 是文本型还是扫描件、按页提取、批量转换 PDF 目录时使用。
agent_created: true
---

# PDF to Markdown

本地 PDF 解析工具，封装 pip 包 `pdf-inspector`。默认只做文本型 PDF 的本地提取，200ms 级完成，不调用任何 OCR 服务；扫描件只做分类并给出需 OCR 的页码。

## 前置检查

首次使用先确认依赖：

```bash
python -c "import pdf_inspector; print('ok')"
```

缺失时安装（已在本机安装 1.26.0）：

```bash
python -m pip install pdf-inspector
```

## 脚本位置

```
C:\Users\wangs\.qoder\skills\pdf-to-markdown\scripts\pdf2md.py
```

以下命令中的 `pdf2md.py` 均指该路径；若当前目录就在脚本目录，可直接用 `scripts/pdf2md.py`。

## 基本用法

```bash
python pdf2md.py <PDF或目录>...
```

默认把 Markdown 打印到 stdout；警告和写入信息走 stderr，便于管道处理。

| 选项 | 说明 |
|------|------|
| `-o, --output PATH` | 单文件时写文件；多文件或已存在目录时，按输入文件名写 `.md`/`.json` |
| `--json` | 输出 JSON：分类元数据 + `markdown` 字段 |
| `--meta` | 只输出分类信息：类型、置信度、页数、耗时、表格/分栏、需 OCR 页 |
| `--pages 1,3,5-10` | 只处理指定页，**1 起**编号 |
| `--ocr` | 选择性 OCR；需另装 PDFium + ONNX Runtime |
| `-r, --recursive` | 输入为目录时递归查找 `*.pdf` |

## 典型流程

**1. 单文件转 Markdown**

```bash
python pdf2md.py "报告.pdf"
python pdf2md.py "报告.pdf" -o "报告.md"
```

**2. 先判断是否需要 OCR**

```bash
python pdf2md.py --meta "扫描件.pdf"
```

输出示例：

```
扫描件.pdf
  type=scanned confidence=0.95 pages=1 time=1ms
  tables=[] columns=[] encoding_issues=False complex_layout=False
  ocr_pages(1-based)=[1]
```

`pdf_type` 取值：`text_based` / `scanned` / `image_based` / `mixed`。
- `text_based` 且 `ocr_pages` 为空：直接提取。
- `scanned` / `image_based`：默认不识别，需 `--ocr`，或转交带 OCR 的文档管线。
- `mixed`：只对 `ocr_pages` 中的页做 OCR。

**3. 批量转换目录**

```bash
python pdf2md.py "D:\文档" -o "D:\markdown" -r
```

按原文件 stem 命名输出，已存在的同名文件会被覆盖。

**4. 按页提取**

```bash
python pdf2md.py "手册.pdf" --pages 2,5-8
```

**5. 交给下游程序**

```bash
python pdf2md.py --json "合同.pdf" | python -c "import json,sys; print(json.load(sys.stdin)['markdown'])"
```

## 关键行为与坑

- 本工具所有页码统一 **1 起**：`--pages` 输入、`ocr_pages` 输出、`--ocr` 路由。
- 若绕过脚本直接调用库：`process_pdf(pages=...)` 与 `process_pdf_with_ocr(page_numbers=...)` 也是 1 起，但 `classify_pdf()` 返回的 `pages_needing_ocr` 是 **0 起**，不要混用。
- 退出码：`0` 成功；`1` 有文件读取/解析失败；`2` 没有可提取文本（通常是扫描件）。
- 无文本时 stdout 为空，stderr 会给出 `pages needing OCR (1-based)`。
- 分类结果受抽样影响：即使部分页有文字，整体也可能被判为 `image_based`，以 `ocr_pages` 为准。
- 中文乱码通常来自 PDF 字体缺少 ToUnicode 映射（`encoding_issues=True`、`cmap_gaps` 非空），属于源文件问题，可对相应页走 OCR。
- 表格检测有矩形和启发式两路，复杂合并单元格、公式不保证还原。
- `--ocr` 只渲染被路由的页，但必须先准备 PDFium 与 ONNX Runtime；未安装时对纯文本 PDF 仍可安全使用（不会加载运行时）。
- 输出中 `confidence` 是分类置信度，不是内容准确率。

## 选型建议

适合报告、论文、财报、发票、合同等**原生文本 PDF**：阅读顺序、表格、标题层级优于多数本地工具，速度远快于 PyMuPDF4LLM / MarkItDown。扫描件与图片型 PDF 不要期待本工具识别文字，直接走 OCR 或托管服务。
