# PDF 文本/Markdown 提取工具

从 PDF 提取文本或 Markdown（含表格、标题识别、标题结构审查）。支持自动依赖安装、多种提取方法自动切换、中英文标题识别、表格→Markdown、Windows GBK 编码修复。所有阈值均可通过 CLI 参数调整。

## 功能特点

- ✅ 支持多种提取方法：pdfplumber、pypdf、pdfminer.six
- ✅ 自动选择最佳提取方法（text/md 格式不同策略）
- ✅ **Markdown 输出**（含表格 + 标题识别）⭐ 推荐
- ✅ **标题识别**：字号判断 + 中英文模式匹配，支持 H1/H2/H3 层级
- ✅ **标题结构审查**：自动修正装饰性文字、过长标题、连续同级误判等
- ✅ **表格→Markdown**：pdfplumber 提取表格转为管道表格格式，自动去重
- ✅ 自动依赖安装（含 PEP 668 处理、cryptography 依赖链修复）
- ✅ Windows 中文兼容（GBK 编码修复）
- ✅ 详细的处理日志和进度显示
- ✅ 分页标记（`=== Page N ===`）
- ✅ 错误处理和恢复机制
- ✅ 所有阈值可通过 CLI 参数调整

## 前置要求

**Python 3.8+ 必须已安装。**

使用前请先检测 Python 环境：

```bash
python --version 2>/dev/null || python3 --version 2>/dev/null
```

若输出版本号（如 `Python 3.11.5`）→ 环境就绪。若提示找不到命令 → 请先安装 Python：

- **Windows**: 访问 https://www.python.org/downloads/ 下载安装程序，安装时 **务必勾选 "Add python.exe to PATH"**
- **macOS**: `brew install python3` 或访问 https://www.python.org/downloads/
- **Linux (Debian/Ubuntu)**: `sudo apt install python3 python3-pip`
- **Linux (Fedora)**: `sudo dnf install python3 python3-pip`

## 安装依赖

脚本会在运行时自动安装缺失的依赖。如需手动安装：

```bash
python -m pip install pypdf pdfplumber pdfminer.six cffi cryptography
```

或：

```bash
python -m pip install -r requirements.txt
```

## 使用方法

### 快速开始

```bash
# 纯文本提取
python scripts/pdf_extractor.py document.pdf

# Markdown 提取（含表格+标题+结构审查）⭐ 推荐
python scripts/pdf_extractor.py document.pdf -f md

# Markdown 但不标记标题
python scripts/pdf_extractor.py document.pdf -f md --no-heading

# 保留两列表格（默认丢弃 ≤2 列的表格）
python scripts/pdf_extractor.py document.pdf -f md --table-min-cols 2
```

### 基本用法

```bash
# 默认纯文本输出 → document.txt
python scripts/pdf_extractor.py document.pdf

# Markdown 输出（含表格+标题）→ document.md
python scripts/pdf_extractor.py document.pdf -f md

# 指定输出文件
python scripts/pdf_extractor.py document.pdf -o output.md

# 指定提取方法
python scripts/pdf_extractor.py document.pdf -m pypdf
python scripts/pdf_extractor.py document.pdf -m pdfplumber -f md
python scripts/pdf_extractor.py document.pdf -m auto   # 默认

# 页分隔符
python scripts/pdf_extractor.py document.pdf -f md -p   # 输出 === Page N ===

# 详细日志
python scripts/pdf_extractor.py document.pdf --verbose
```

### 高级调参

```bash
# 标题：放宽字号阈值（适合字号差异小的 PDF）
python scripts/pdf_extractor.py doc.pdf -f md --heading-size-delta 2.0

# 标题：调整 H1/H2 层级阈值
python scripts/pdf_extractor.py doc.pdf -f md --heading-h1-ratio 1.3 --heading-h2-ratio 1.15

# 标题：禁用文本模式匹配，仅用字号判断
python scripts/pdf_extractor.py doc.pdf -f md --no-heading-pattern

# 标题：完全不标记标题，输出纯 Markdown 文本
python scripts/pdf_extractor.py doc.pdf -f md --no-heading

# 标题结构审查：放宽内容长度阈值（适合长标题文档）
python scripts/pdf_extractor.py doc.pdf -f md --heading-h1-max-len 60 --heading-h2-max-len 80

# 标题结构审查：调高连续同级标题阈值（适合多并列章节文档）
python scripts/pdf_extractor.py doc.pdf -f md --heading-consecutive-limit 5

# 标题结构审查：自定义装饰性文字正则
python scripts/pdf_extractor.py doc.pdf -f md --heading-deco-pattern "^第\d+期$;^Note:"

# 表格：保留两列表格（默认丢弃 <3 列的疑似误判表格）
python scripts/pdf_extractor.py doc.pdf -f md --table-min-cols 2

# 表格：完全禁用表格提取
python scripts/pdf_extractor.py doc.pdf -f md --no-table

# 布局：调整行间距阈值（默认 3pt）
python scripts/pdf_extractor.py doc.pdf -f md --line-spacing 5.0
```

## 参数说明

### 基本参数

| 参数 | 说明 |
|---|---|
| `pdf_file` | PDF 文件路径 |
| `-o, --output` | 输出文件路径（默认同名 .txt/.md） |
| `-m, --method` | 提取方法：`auto`(默认) / `pdfplumber` / `pypdf` / `pdfminer` |
| `-f, --format` | 输出格式：`text`(默认) / `md`(Markdown 含表格+标题) |
| `-p, --page-sep` | 输出页分隔符 `=== Page N ===` |
| `--verbose` | 详细日志 |

### 标题识别参数（仅 `-f md`）

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--no-heading` | off | 禁用标题识别，输出纯文本 |
| `--no-heading-pattern` | off | 禁用文本模式匹配标题（仅保留字号判断） |
| `--heading-size-delta` | 1.0 | 字号超过基准多少 pt 视为标题 |
| `--heading-h1-ratio` | 1.5 | 字号/基准 ≥ 此值标记 H1（`#`） |
| `--heading-h2-ratio` | 1.25 | 字号/基准 ≥ 此值标记 H2（`##`） |
| `--heading-max-len` | 60 | 模式匹配标题的最大行长度 |

### 标题结构审查参数（仅 `-f md`，自动执行）

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--heading-h1-max-len` | 40 | H1 标题最大字符数，超限逐级降级 |
| `--heading-h2-max-len` | 50 | H2 标题最大字符数 |
| `--heading-h3-max-len` | 50 | H3 标题最大字符数，超限降为正文 |
| `--heading-consecutive-limit` | 3 | 连续同级标题阈值，≥ 此数降为正文 |
| `--heading-deco-pattern` | (空) | 自定义装饰性文字正则（分号分隔多条） |

### 表格提取参数（仅 `-f md`）

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--no-table` | off | 禁用表格提取 |
| `--table-min-cols` | 3 | 最少列数，低于此值视为误判并丢弃 |

### 布局参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--line-spacing` | 3.0 | 行分组间距阈值（pt），影响行合并和标题识别 |

## 提取方法对比

| 方法 | 表格支持 | 标题识别 | 中文 | 稳定性 | auto 模式顺序(text/md) |
|---|---|---|---|---|---|
| **pypdf** | ❌ | 模式匹配 | ✅ | ⭐⭐⭐ 最稳定 | 第1 / 第2 |
| **pdfplumber** | ✅ | 字号+模式 | ✅ | ⭐⭐ 依赖链可能断裂 | 第2 / 第1 |
| **pdfminer.six** | ❌ | ❌ | ✅ | ⭐ 重型 | 第3 / 第3 |

## 核心特性详解

### 1. 自动依赖安装

- 缺少库时自动通过 `python -m pip install` 安装
- 自动处理 PEP 668 (`--break-system-packages`)
- 自动修复 pdfplumber 依赖链 (`cffi` → `cryptography`)

### 2. 标题识别

- **字号判断**：计算每行平均字号与基准字号（众数）的比值，超过阈值标记为 H1/H2/H3
- **模式匹配**：支持中英文标题模式
  - 中文：`一、` `二、` … `第X章/节/部分` → H2；`1.` `2.` → H3
  - 英文：`Chapter N` `Section N` `Part N` → H2；全大写短行 → H2
  - 康熙部首异体字自动映射（⼀→一）
- 可独立开关（`--no-heading` / `--no-heading-pattern`）

### 3. 标题结构审查（自动执行）

Markdown 提取时自动执行规则后审查，修正标题层级的不合理判断：

| 规则 | 说明 |
|---|---|
| **装饰性文字降级** | 纯符号序列（①②③④）、页码标记（01/02）、数字+单位（3万元/5人）→ 降为正文 |
| **内容长度降级** | H1>40字→H2，H2>50字→H3，H3>50字→正文。阈值可配置 |
| **连续同级降级** | ≥3 个同级标题无正文间隔 → 全降为正文（PDF提取常见：正文段落被误拆为多个标题） |
| **首标题升级** | 文档首个标题为 H2 → 提升为 H1 |

### 4. AI 审查标题结构

规则审查是纯启发式的，无法处理所有场景。对于标题层级结构要求较高的文档，**建议在提取后由 AI 进行二次审查**。

**审查流程：**

1. 使用本工具提取 Markdown：`python scripts/pdf_extractor.py document.pdf -f md -o output.md`
2. AI 读取输出文件，提取标题大纲
3. AI 审查以下维度并直接编辑修正输出文件：

| 审查维度 | 说明 |
|---|---|
| **标题 vs 正文** | 结合上下文语义判断该行是否为结构性章节标题，而非正文段落、口号、描述文字 |
| **层级一致性** | 避免跳跃（如 H1→H3 跳过 H2）、避免过多顶级标题、子标题层级应递进 |
| **装饰性识别** | 序号标注、金额数字、时间日期等非结构性强调文字不应作为标题 |
| **文档结构** | 整体大纲应形成合理的树状结构，主标题→章节→子节层次分明 |

**审查示例：**

```markdown
# 提取后可能的结果（不合理）：
## 企 业 内 训
# 让财务团队真正把 AI 用进日常工作
# 不是听一堂课，而是建一套能力
### 让公司财务团队都能熟练使用 AI，把 AI 真正用到日常工作里...
### 队掌握 AI，谁就先拿到效率红利。

# AI 审查修正后（合理）：
# 企业内训
## 让财务团队真正把 AI 用进日常工作
让公司财务团队都能熟练使用 AI，把 AI 真正用到日常工作里...队掌握 AI，谁就先拿到效率红利。
```

### 5. 表格 → Markdown

- 使用 pdfplumber 提取表格，转为 Markdown 管道表格格式
- 自动去重：表格区域文本不会在纯文本部分重复出现（bbox 排除法）
- 误判过滤：列数过少的表格自动丢弃（阈值可配置 `--table-min-cols`）

### 6. Windows 中文兼容

- 强制 `PYTHONIOENCODING=utf-8`
- `sys.stdout/stderr` 重编码为 UTF-8
- 解决 GBK codec 编码错误

### 7. 智能方法选择

- **text 格式**：pypdf 优先（最稳定，无依赖链问题）
- **md 格式**：pdfplumber 优先（表格支持），pypdf 后备
- 3 行以上有效内容即视为成功

## 在 Python 代码中使用

```python
from scripts.pdf_extractor import extract_pdf_text, save_output, MdOptions

# 使用默认选项
text = extract_pdf_text("document.pdf", method="auto", fmt="md")
if text:
    save_output(text, "output.md")

# 自定义选项
opts = MdOptions(
    heading=True,
    heading_size_delta=2.0,    # 放宽字号阈值
    heading_h1_ratio=1.3,      # 降低 H1 阈值
    heading_h1_max_len=60,     # 放宽 H1 内容长度
    heading_h2_max_len=80,     # 放宽 H2 内容长度
    heading_consecutive_limit=5,  # 放宽连续同级阈值
    table_min_cols=2,           # 保留两列表格
    line_spacing=5.0,           # 增大行间距阈值
    page_sep="===",             # 启用页分隔符
)
text = extract_pdf_text("document.pdf", method="auto", fmt="md", opts=opts)
```

## 输出格式

### 纯文本

提取的文本文件包含分页标记：

```
=== Page 1 ===
这里是第一页的文本内容...

=== Page 2 ===
这里是第二页的文本内容...
```

### Markdown

Markdown 输出包含标题层级和表格：

```markdown
# 文档标题

## 第一章 概述

这是正文内容...

| 列1 | 列2 | 列3 |
|---|---|---|
| 数据1 | 数据2 | 数据3 |

### 1. 子节标题

更多内容...
```

## 错误处理

| 错误场景 | 处理方式 |
|---|---|
| **Python 未安装** | 调用前 shell 检测，给出各平台安装指引 |
| **Python 版本过低**（< 3.8） | 脚本内检测，提示下载新版 |
| **pip 不可用** | 脚本内检测，提示修复方式 |
| **文件不存在** | 明确提示 |
| **非 PDF 文件** | 检查 `%PDF` 签名 |
| **依赖缺失** | 自动安装，失败后给出手动命令 |
| **扫描件 PDF** | 所有方法失败后建议 OCR |
| **加密 PDF** | 报告失败并建议解密 |

## 日志文件

脚本会生成 `pdf_extraction.log` 文件，记录详细的处理过程。使用 `--verbose` 可输出调试级别日志。

## 处理扫描件 PDF

如果 PDF 是扫描件（图片格式），上述工具可能无法提取文本。建议：
1. 使用 OCR 工具（如 Tesseract）配合 pdf2image 先转换
2. 使用在线 OCR 服务

## 注意事项

1. 确保已安装 Python 3.8+
2. 对于大型 PDF 文件（>100MB），提取可能需要较长时间
3. 加密的 PDF 需要先解密
4. 扫描件 PDF 需要 OCR 处理
5. 推荐使用 `-f md` 格式提取，可获取更丰富的结构信息

## 项目结构

```
pdf2txt/
├── README.md
├── SKILL.md                    # Claude Code Skill 定义
├── requirements.txt
└── scripts/
    └── pdf_extractor.py        # 主提取脚本
```

## 许可证

MIT
