# PDF 文本提取工具

一个健壮的 Python 脚本，用于从 PDF 文件中提取文本，支持多种提取方法。

## 功能特点

- ✅ 支持多种提取方法：pdfplumber、pypdf、pdfminer.six
- ✅ 自动选择最佳提取方法
- ✅ 详细的处理日志和进度显示
- ✅ 支持中文PDF
- ✅ 分页标记（Page 1, Page 2...）
- ✅ 错误处理和恢复机制
- ✅ 自动检查PDF文件有效性

## 安装依赖

```bash
# 安装所有依赖
pip install pdfplumber pypdf pdfminer.six

# 或使用 requirements.txt
pip install -r requirements.txt
```

## 使用方法

### 基本用法
```bash
python pdf_extractor.py 你的文件.pdf
```

### 指定输出文件
```bash
python pdf_extractor.py 你的文件.pdf -o 输出文件.txt
```

### 指定提取方法
```bash
# 使用 pdfplumber（推荐）
python pdf_extractor.py 文件.pdf -m pdfplumber

# 使用 pypdf
python pdf_extractor.py 文件.pdf -m pypdf

# 使用 pdfminer
python pdf_extractor.py 文件.pdf -m pdfminer

# 自动选择（默认）
python pdf_extractor.py 文件.pdf -m auto
```

### 详细输出
```bash
python pdf_extractor.py 文件.pdf --verbose
```

## 示例

```bash
# 提取当前目录下的PDF
python pdf_extractor.py 你的文件.pdf

# 提取并指定输出路径
python pdf_extractor.py 你的文件.pdf -o 调研文本.txt

# 使用特定方法提取
python pdf_extractor.py 你的文件.pdf -m pdfplumber --verbose
```

## 输出格式

提取的文本文件包含分页标记：
```
=== Page 1 ===
这里是第一页的文本内容...

=== Page 2 ===
这里是第二页的文本内容...
```

## 处理扫描件PDF

如果PDF是扫描件（图片格式），上述工具可能无法提取文本。建议：
1. 使用OCR工具（如 Tesseract）配合 pdf2image 先转换
2. 使用在线OCR服务

## 错误处理

- **文件不存在**：显示错误信息
- **无效PDF**：检查文件签名
- **提取失败**：尝试其他方法
- **权限问题**：检查文件读写权限

## 日志文件

脚本会生成 `pdf_extraction.log` 文件，记录详细的处理过程。

## 在Python代码中使用

```python
from pdf_extractor import extract_pdf_text

# 提取文本
text = extract_pdf_text("文件.pdf", method="auto")

if text:
    print(f"提取到 {len(text)} 字符")
    with open("输出.txt", "w", encoding="utf-8") as f:
        f.write(text)
else:
    print("提取失败")
```

## 注意事项

1. 确保已安装所需的Python库
2. 对于大型PDF文件（>100MB），提取可能需要较长时间
3. 加密的PDF需要先解密
4. 扫描件PDF需要OCR处理

## 许可证

MIT