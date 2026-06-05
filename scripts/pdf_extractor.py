#!/usr/bin/env python3
"""
PDF 文本/Markdown 提取工具
支持多种提取方法，自动安装依赖，表格提取为 Markdown 格式，标题自动识别
"""

import os
import sys
import subprocess
import argparse
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from collections import Counter

# ── 强制 UTF-8 输出（Windows 兼容） ──────────────────────────────
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── 日志 ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("pdf_extraction.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
#  Markdown 提取选项（统一配置）
# ═══════════════════════════════════════════════════════════════════

@dataclass
class MdOptions:
    """Markdown 输出的所有可调参数，集中管理"""
    # ── 标题识别 ──
    heading: bool = True              # 是否启用标题识别
    heading_size_delta: float = 1.0   # 字号超过基准多少 pt 视为标题
    heading_h1_ratio: float = 1.5     # ratio >= 此值 → H1
    heading_h2_ratio: float = 1.25    # ratio >= 此值 → H2（其余 → H3）
    heading_pattern: bool = True       # 是否启用文本模式匹配标题
    heading_max_len: int = 60         # 模式匹配标题的最大行长度
    heading_sub_max_len: int = 50     # 数字编号子标题最大长度

    # ── 标题结构审查（规则后处理） ──
    heading_h1_max_len: int = 40      # H1 标题最大字符数（超限逐级降级）
    heading_h2_max_len: int = 50      # H2 标题最大字符数
    heading_h3_max_len: int = 50      # H3 标题最大字符数（超限降为正文）
    heading_consecutive_limit: int = 3  # 连续同级标题阈值（≥ 此数降为正文）
    heading_deco_patterns: str = ""   # 自定义装饰性文字正则（分号分隔多条）

    # ── 表格 ──
    table: bool = True                # 是否提取表格
    table_min_cols: int = 3           # 最少列数（<= 此值的表格丢弃）

    # ── 布局 ──
    line_spacing: float = 3.0         # 行分组间距阈值（pt）
    page_sep: str = ""                # 页分隔符，空=不输出


# 康熙部首异体字 → 标准汉字
_VARIANT_MAP = str.maketrans(
    '⼀⼆三四五六七八九十',
    '一二三四五六七八九十'
)


# ═══════════════════════════════════════════════════════════════════
#  依赖管理
# ═══════════════════════════════════════════════════════════════════

def _pip_install(package: str) -> bool:
    """通过 python -m pip 安装包，自动处理 --break-system-packages"""
    cmd = [sys.executable, "-m", "pip", "install", package, "--quiet"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            cmd.append("--break-system-packages")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.returncode == 0
    except Exception as e:
        logger.warning(f"安装 {package} 失败: {e}")
        return False


def _ensure_import(module_name: str, pip_name: str = None) -> bool:
    try:
        __import__(module_name)
        return True
    except ImportError:
        pip_name = pip_name or module_name
        logger.info(f"依赖缺失，正在安装 {pip_name} ...")
        ok = _pip_install(pip_name)
        if ok:
            logger.info(f"✅ {pip_name} 安装成功")
        else:
            logger.error(f"❌ {pip_name} 安装失败")
        return ok


def _ensure_cryptography_backend():
    try:
        import cryptography  # noqa: F401
    except ImportError:
        _ensure_import("cryptography", "cryptography")
    try:
        import _cffi_backend  # noqa: F401
    except ImportError:
        _ensure_import("_cffi_backend", "cffi")


# ═══════════════════════════════════════════════════════════════════
#  标题识别
# ═══════════════════════════════════════════════════════════════════

def _is_heading_by_pattern(text: str, opts: MdOptions) -> Tuple[bool, int]:
    """
    通过文本模式判断是否为标题。
    返回 (is_heading, level) — level: 2=章节, 3=子节, 0=非标题
    """
    text = text.strip()
    if not text or len(text) > opts.heading_max_len:
        return False, 0
    norm = text.translate(_VARIANT_MAP)
    # 中文数字章节标题 → H2
    if re.match(r'^[一二三四五六七八九十百]+[、．.]', norm):
        return True, 2
    if re.match(r'^第[一二三四五六七八九十百\d]+[章节部分]', norm):
        return True, 2
    # 英文章节标题 → H2（Chapter/Section/Part 开头，或全大写短行）
    if re.match(r'^(Chapter|Section|Part|Appendix)\s+\d', text, re.I):
        return True, 2
    if text.isupper() and len(text) <= 40 and ' ' in text:
        return True, 2
    # 数字编号子标题 → H3
    if len(text) <= opts.heading_sub_max_len and re.match(r'^\d+[.\s]', text):
        return True, 3
    return False, 0


def _detect_heading_level(avg_size: float, base_size: float, opts: MdOptions) -> int:
    """
    根据字号判断标题层级。
    返回 1/2/3 或 0（非标题）
    """
    if avg_size <= base_size + opts.heading_size_delta:
        return 0
    ratio = avg_size / base_size if base_size > 0 else 1.0
    if ratio >= opts.heading_h1_ratio:
        return 1
    elif ratio >= opts.heading_h2_ratio:
        return 2
    else:
        return 3


def _mark_heading(text: str, level: int) -> str:
    """添加 Markdown # 前缀"""
    return f"{'#' * level} {text}"


def _ensure_heading_blanklines(text: str) -> str:
    """确保所有 # 标题行前至少有一个空行"""
    lines = text.split("\n")
    result: List[str] = []
    for idx, line in enumerate(lines):
        if idx > 0 and line.startswith("#") and result and result[-1].strip() != "":
            result.append("")
        result.append(line)
    return "\n".join(result)


# ═══════════════════════════════════════════════════════════════════
#  标题结构审查（规则后处理）
# ═══════════════════════════════════════════════════════════════════

# 内置装饰性文字模式（中英文通用）
_BUILTIN_DECO_PATTERNS = [
    r'^[①②③④⑤⑥⑧⑨⑩⑪⑫★☆◆◇○●◎]+$',                  # 纯符号序列
    r'^0?[1-9]\d?$',                                      # 页码标记（01-99）
    r'^\d+(\.\d+)?\s*(万元|元|万|%|个|人|天|月|年'         # 数字+中文单位
    r'|小时|分钟|页|名|项|份|次|套|期|轮|批|组|类)$',
    r'^\$?\d+[\d,.]*\s*([A-Z]{1,3}|万|元)?$',             # 数字+英文单位/货币
]


def _validate_heading_structure(text: str, opts: MdOptions) -> str:
    """
    后处理：基于规则审查标题层级结构的合理性。

    两阶段执行：
    Phase 1: 所有规则基于原始标题列表判断（避免规则间相互干扰）
    Phase 2: 统一应用修改

    规则：
    1. 装饰性文字降级 — 纯符号/页码/数字+单位 → 正文
    2. 内容长度降级 — 超过层级阈值 → 逐级降级，H3 超限 → 正文
    3. 连续同级降级 — ≥N 个同级标题无正文间隔 → 全降为正文
    4. 首标题升级 — 文档首个标题为 H2 → 提升为 H1（Phase 2 后执行）
    """
    if not opts.heading:
        return text

    lines = text.split("\n")

    # ── 扫描标题行 ──
    def _scan_headings(line_list):
        entries = []
        for idx, line in enumerate(line_list):
            m = re.match(r'^(#{1,6})\s+(.+)$', line.strip())
            if m:
                entries.append((idx, len(m.group(1)), m.group(2).strip()))
        return entries

    heading_entries = _scan_headings(lines)
    if not heading_entries:
        return text

    # ══════════════════════════════════════════════════════════════
    #  Phase 1: 基于原始标题列表判断所有修改（不修改 lines）
    # ══════════════════════════════════════════════════════════════
    demote_to_body = set()   # 降为正文的行索引
    relevel_map = {}         # 行索引 → 新层级

    # ── 规则 1: 装饰性文字 → 正文 ──
    deco_patterns = list(_BUILTIN_DECO_PATTERNS)
    if opts.heading_deco_patterns:
        for p in opts.heading_deco_patterns.split(";"):
            p = p.strip()
            if p:
                deco_patterns.append(p)

    for idx, level, heading_text in heading_entries:
        for pat in deco_patterns:
            try:
                if re.match(pat, heading_text.strip()):
                    demote_to_body.add(idx)
                    logger.debug(f"结构审查 R1(装饰): H{level} → 正文: {heading_text.strip()}")
                    break
            except re.error:
                logger.warning(f"装饰性正则无效，已跳过: {pat}")

    # ── 规则 2: 内容长度 → 逐级降级或正文 ──
    max_len_map = {1: opts.heading_h1_max_len, 2: opts.heading_h2_max_len, 3: opts.heading_h3_max_len}

    for idx, level, heading_text in heading_entries:
        if idx in demote_to_body or level > 3:
            continue
        text_len = len(heading_text)
        current_level = level
        while current_level <= 3 and text_len > max_len_map.get(current_level, 80):
            current_level += 1
        if current_level > 3:
            demote_to_body.add(idx)
            logger.debug(f"结构审查 R2(长度): H{level} → 正文 (len={text_len}): {heading_text[:40]}...")
        elif current_level > level:
            relevel_map[idx] = current_level
            logger.debug(f"结构审查 R2(长度): H{level} → H{current_level} (len={text_len}): {heading_text[:40]}...")

    # ── 规则 3: 连续同级 → 正文（基于原始标题列表，不受 R1/R2 影响）──
    i = 0
    while i < len(heading_entries):
        current_level = heading_entries[i][1]
        group = [i]  # heading_entries 中的索引

        for j in range(i + 1, len(heading_entries)):
            if heading_entries[j][1] != current_level:
                break
            # 检查两个标题之间是否有正文行（使用原始 lines，此时未修改）
            prev_line_idx = heading_entries[j - 1][0]
            curr_line_idx = heading_entries[j][0]
            has_body = any(
                lines[k].strip() and not re.match(r'^#{1,6}\s', lines[k].strip())
                for k in range(prev_line_idx + 1, curr_line_idx)
            )
            if has_body:
                break
            group.append(j)

        if len(group) >= opts.heading_consecutive_limit:
            for gi in group:
                line_idx = heading_entries[gi][0]
                if line_idx not in demote_to_body:  # 避免重复日志
                    demote_to_body.add(line_idx)
                    logger.debug(
                        f"结构审查 R3(连续): H{heading_entries[gi][1]} → 正文: "
                        f"{heading_entries[gi][2][:40]}..."
                    )

        i = group[-1] + 1 if len(group) > 1 else i + 1

    # ══════════════════════════════════════════════════════════════
    #  Phase 2: 统一应用所有修改
    # ══════════════════════════════════════════════════════════════

    # 降为正文
    for idx in demote_to_body:
        m = re.match(r'^#{1,6}\s+(.+)$', lines[idx].strip())
        if m:
            lines[idx] = m.group(1).strip()

    # 层级调整（未被降为正文的才调整）
    for idx, new_level in relevel_map.items():
        if idx not in demote_to_body:
            m = re.match(r'^#{1,6}\s+(.+)$', lines[idx].strip())
            if m:
                lines[idx] = f"{'#' * new_level} {m.group(1).strip()}"

    # ── 规则 4: 首标题 H2 → H1（Phase 2 后执行，基于修改后的标题列表）──
    heading_entries = _scan_headings(lines)
    if heading_entries and heading_entries[0][1] == 2:
        idx, _, heading_text = heading_entries[0]
        lines[idx] = f"# {heading_text}"
        logger.debug(f"结构审查 R4(首标题): H2 → H1: {heading_text[:40]}")

    return _ensure_heading_blanklines("\n".join(lines))


# ═══════════════════════════════════════════════════════════════════
#  表格 → Markdown
# ═══════════════════════════════════════════════════════════════════

def _table_to_md(table: List[List[str]]) -> str:
    if not table or not table[0]:
        return ""
    col_count = max(len(row) for row in table)
    for row in table:
        while len(row) < col_count:
            row.append("")
    lines = []
    header = [str(c).replace("\n", " ").strip() or " " for c in table[0]]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * col_count) + "|")
    for row in table[1:]:
        cells = [str(c).replace("\n", " ").strip() or " " for c in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
#  字符 → 文本（含标题标记）
# ═══════════════════════════════════════════════════════════════════

def _chars_to_text(chars: List[Dict], opts: MdOptions) -> str:
    """将 pdfplumber chars 还原为文本，md 模式下自动标记标题"""
    if not chars:
        return ""
    is_md = opts.heading
    sorted_chars = sorted(chars, key=lambda c: (round(c["top"], 0), c["x0"]))

    # 基准字号（众数）
    font_sizes = [c.get("size", 12) for c in sorted_chars]
    size_counts = Counter(round(s, 1) for s in font_sizes if s > 0)
    base_size = size_counts.most_common(1)[0][0] if size_counts else 12.0

    # 按行分组
    lines_raw: List[Tuple[float, List[Dict]]] = []
    current_line_chars = []
    current_top = round(sorted_chars[0]["top"], 0)

    for ch in sorted_chars:
        ch_top = round(ch["top"], 0)
        if abs(ch_top - current_top) > opts.line_spacing:
            if current_line_chars:
                avg_sz = sum(c.get("size", base_size) for c in current_line_chars) / len(current_line_chars)
                lines_raw.append((avg_sz, current_line_chars))
            current_line_chars = []
            current_top = ch_top
        current_line_chars.append(ch)
    if current_line_chars:
        avg_sz = sum(c.get("size", base_size) for c in current_line_chars) / len(current_line_chars)
        lines_raw.append((avg_sz, current_line_chars))

    # 生成输出
    result = []
    for avg_size, line_chars in lines_raw:
        text = "".join(c["text"] for c in line_chars).strip()
        if not text:
            continue
        if is_md:
            # 1) 字号判断
            level = _detect_heading_level(avg_size, base_size, opts)
            if level > 0:
                result.append(_mark_heading(text, level))
                continue
            # 2) 模式匹配
            if opts.heading_pattern:
                is_h, h_level = _is_heading_by_pattern(text, opts)
                if is_h:
                    result.append(_mark_heading(text, h_level))
                    continue
        result.append(text)
    return _ensure_heading_blanklines("\n".join(result))


def _apply_md_headings(text: str, opts: MdOptions) -> str:
    """后处理：对 extract_text() 输出的纯文本行标记标题"""
    if not opts.heading or not opts.heading_pattern:
        return text
    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append(line)
            continue
        is_h, level = _is_heading_by_pattern(stripped, opts)
        if is_h:
            result.append(_mark_heading(stripped, level))
        else:
            result.append(line)
    return _ensure_heading_blanklines("\n".join(result))


# ═══════════════════════════════════════════════════════════════════
#  提取方法
# ═══════════════════════════════════════════════════════════════════

def _page_header(i: int, sep: str) -> str:
    return f"=== Page {i} ===\n" if sep else ""


def _interleave_tables_and_text(
    page, valid_table_objs: List, non_table_chars: List[Dict], fmt: str, opts: MdOptions
) -> str:
    """
    将表格和非表格文本按 Y 坐标交替排列，保持原始阅读顺序。

    策略：
    1. 将非表格字符按行分组，每行记录 top 坐标
    2. 将每个表格记录其 bbox 的 top 坐标
    3. 将所有"块"（文本行 or 表格）按 top 排序
    4. 相邻文本行合并为段落，表格作为独立块
    """
    # ── 收集表格块 ──
    # 每个 block: (top, 'table'|'text', content)
    blocks: List[Tuple[float, str, str]] = []

    for tobj in valid_table_objs:
        tdata = tobj.extract()
        if not tdata or len(tdata) < 2:
            continue
        md = _table_to_md(tdata)
        if md:
            # bbox = (x0, top, x1, bottom)
            table_top = tobj.bbox[1] if tobj.bbox else 0
            blocks.append((table_top, "table", md))

    # ── 将非表格字符按行分组 ──
    if not non_table_chars:
        # 没有非表格文本，只输出表格
        blocks.sort(key=lambda b: b[0])
        return "\n\n".join(b[2] for b in blocks)

    sorted_chars = sorted(non_table_chars, key=lambda c: (round(c["top"], 0), c["x0"]))
    font_sizes = [c.get("size", 12) for c in sorted_chars]
    size_counts = Counter(round(s, 1) for s in font_sizes if s > 0)
    base_size = size_counts.most_common(1)[0][0] if size_counts else 12.0

    # 按行分组
    current_line_chars = []
    current_top = round(sorted_chars[0]["top"], 0)
    text_lines: List[Tuple[float, str, float]] = []  # (top, text, avg_size)

    for ch in sorted_chars:
        ch_top = round(ch["top"], 0)
        if abs(ch_top - current_top) > opts.line_spacing:
            if current_line_chars:
                avg_sz = sum(c.get("size", base_size) for c in current_line_chars) / len(current_line_chars)
                line_text = "".join(c["text"] for c in current_line_chars).strip()
                if line_text:
                    text_lines.append((current_top, line_text, avg_sz))
            current_line_chars = []
            current_top = ch_top
        current_line_chars.append(ch)
    if current_line_chars:
        avg_sz = sum(c.get("size", base_size) for c in current_line_chars) / len(current_line_chars)
        line_text = "".join(c["text"] for c in current_line_chars).strip()
        if line_text:
            text_lines.append((current_top, line_text, avg_sz))

    # ── 将文本行加入 blocks ──
    # 连续的文本行合并为一个 text block，以减少碎片
    if text_lines:
        para_top = text_lines[0][0]
        para_lines: List[str] = []
        para_avg_sizes: List[float] = []

        for line_top, line_text, avg_sz in text_lines:
            # 标记标题
            if opts.heading:
                level = _detect_heading_level(avg_sz, base_size, opts)
                if level > 0:
                    # 先 flush 当前段落
                    if para_lines:
                        para_text = "\n".join(para_lines)
                        blocks.append((para_top, "text", para_text))
                        para_lines = []
                        para_avg_sizes = []
                    blocks.append((line_top, "text", _mark_heading(line_text, level)))
                    para_top = line_top  # 重置段落起点
                    continue
                if opts.heading_pattern:
                    is_h, h_level = _is_heading_by_pattern(line_text, opts)
                    if is_h:
                        if para_lines:
                            para_text = "\n".join(para_lines)
                            blocks.append((para_top, "text", para_text))
                            para_lines = []
                            para_avg_sizes = []
                        blocks.append((line_top, "text", _mark_heading(line_text, h_level)))
                        para_top = line_top
                        continue
            para_lines.append(line_text)
            para_avg_sizes.append(avg_sz)

        # flush 剩余段落
        if para_lines:
            para_text = "\n".join(para_lines)
            blocks.append((para_top, "text", para_text))

    # ── 按 top 排序，输出 ──
    blocks.sort(key=lambda b: b[0])
    raw = "\n\n".join(b[2] for b in blocks)
    return _ensure_heading_blanklines(raw)


def extract_with_pdfplumber(pdf_path: str, fmt: str = "text", opts: MdOptions = None) -> Optional[str]:
    """使用 pdfplumber 提取（支持表格 + 标题）"""
    if opts is None:
        opts = MdOptions()
    _ensure_cryptography_backend()
    if not _ensure_import("pdfplumber"):
        return None
    import pdfplumber
    import warnings
    warnings.filterwarnings("ignore", message=".*FontBBox.*")

    try:
        logger.info(f"使用 pdfplumber 提取: {pdf_path}")
        parts: List[str] = []

        with pdfplumber.open(pdf_path) as pdf:
            total = len(pdf.pages)
            for i, page in enumerate(pdf.pages, 1):
                # 1) 发现表格对象
                valid_table_objs = []
                excluded_bboxes = []
                if opts.table:
                    table_objs = page.find_tables()
                    for tobj in table_objs:
                        tdata = tobj.extract()
                        if not tdata or len(tdata) < 2:
                            continue
                        col_count = max(len(row) for row in tdata)
                        if col_count < opts.table_min_cols:
                            logger.debug(f"  跳过疑似误判表格 ({len(tdata)}行 x {col_count}列)")
                            continue
                        valid_table_objs.append(tobj)
                        if tobj.bbox:
                            excluded_bboxes.append(tobj.bbox)

                # 2) 提取非表格区域字符
                if excluded_bboxes:
                    non_table_chars = []
                    for ch in page.chars:
                        cx = (ch["x0"] + ch["x1"]) / 2
                        cy = (ch["top"] + ch["bottom"]) / 2
                        in_table = any(
                            bb[0] <= cx <= bb[2] and bb[1] <= cy <= bb[3]
                            for bb in excluded_bboxes
                        )
                        if not in_table:
                            non_table_chars.append(ch)
                else:
                    non_table_chars = list(page.chars) if page.chars else []

                # 3) 按阅读顺序交错排列表格和文本
                if valid_table_objs and fmt == "md":
                    page_text = _interleave_tables_and_text(
                        page, valid_table_objs, non_table_chars, fmt, opts
                    )
                elif non_table_chars and fmt == "md":
                    page_text = _chars_to_text(non_table_chars, opts)
                elif non_table_chars:
                    page_text = "\n".join(
                        "".join(c["text"] for c in sorted(
                            non_table_chars, key=lambda c: (round(c["top"], 0), c["x0"])
                        ))
                    )
                else:
                    page_text = page.extract_text() or ""

                if page_text and page_text.strip():
                    page_text = page_text.strip()
                else:
                    page_text = "[无文本]"

                parts.append(_page_header(i, opts.page_sep) + page_text)

                if i % 10 == 0 or i == total:
                    logger.info(f"  进度: {i}/{total}")

        return "\n\n".join(parts)
    except Exception as e:
        logger.error(f"pdfplumber 提取失败: {e}")
        return None


def extract_with_pypdf(pdf_path: str, fmt: str = "text", opts: MdOptions = None) -> Optional[str]:
    if opts is None:
        opts = MdOptions()
    if not _ensure_import("pypdf"):
        return None
    from pypdf import PdfReader

    try:
        logger.info(f"使用 pypdf 提取: {pdf_path}")
        parts: List[str] = []
        reader = PdfReader(pdf_path)
        total = len(reader.pages)

        for i, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            if text.strip():
                text = text.strip()
                if fmt == "md":
                    text = _apply_md_headings(text, opts)
                parts.append(_page_header(i, opts.page_sep) + text)
            else:
                parts.append(_page_header(i, opts.page_sep) + "[无文本]")
            if i % 10 == 0 or i == total:
                logger.info(f"  进度: {i}/{total}")

        return "\n\n".join(parts)
    except Exception as e:
        logger.error(f"pypdf 提取失败: {e}")
        return None


def extract_with_pdfminer(pdf_path: str, fmt: str = "text") -> Optional[str]:
    if not _ensure_import("pdfminer"):
        return None
    from pdfminer.high_level import extract_text as pm_extract

    try:
        logger.info(f"使用 pdfminer.six 提取: {pdf_path}")
        text = pm_extract(pdf_path)
        if text:
            logger.info("pdfminer.six 提取完成")
            return text
        else:
            logger.warning("pdfminer.six 未提取到文本")
            return None
    except Exception as e:
        logger.error(f"pdfminer.six 提取失败: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════
#  文件校验
# ═══════════════════════════════════════════════════════════════════

def check_python_env() -> Tuple[bool, str]:
    """检测 Python 运行环境：版本、pip 可用性"""
    # 版本检测
    vi = sys.version_info
    if vi.major < 3 or (vi.major == 3 and vi.minor < 8):
        return False, (
            f"Python 版本过低: {vi.major}.{vi.minor}.{vi.micro}，"
            f"需要 Python 3.8+\n"
            f"  下载地址: https://www.python.org/downloads/"
        )

    # pip 可用性检测
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True, timeout=30,
        )
    except Exception:
        return False, (
            "pip 不可用，无法自动安装依赖库。\n"
            "  修复方式:\n"
            "    Windows: 重新运行 Python 安装程序，勾选 'pip'\n"
            "    macOS/Linux: python3 -m ensurepip --upgrade"
        )

    return True, "OK"


def check_pdf_file(pdf_path: str) -> Tuple[bool, str]:
    if not os.path.exists(pdf_path):
        return False, f"文件不存在: {pdf_path}"
    if not pdf_path.lower().endswith(".pdf"):
        return False, f"不是 PDF 文件: {pdf_path}"
    try:
        with open(pdf_path, "rb") as f:
            if not f.read(5).startswith(b"%PDF"):
                return False, "文件不是有效 PDF（缺少 %PDF 签名）"
    except Exception as e:
        return False, f"文件读取失败: {e}"
    return True, "OK"


# ═══════════════════════════════════════════════════════════════════
#  主提取入口
# ═══════════════════════════════════════════════════════════════════

def extract_pdf_text(
    pdf_path: str,
    method: str = "auto",
    fmt: str = "text",
    opts: MdOptions = None,
) -> Optional[str]:
    if opts is None:
        opts = MdOptions()
    ok, msg = check_pdf_file(pdf_path)
    if not ok:
        logger.error(msg)
        return None

    size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
    logger.info(f"开始提取: {pdf_path} ({size_mb:.2f} MB), 格式={fmt}")

    if method == "auto":
        methods = ["pdfplumber", "pypdf", "pdfminer"] if fmt == "md" else ["pypdf", "pdfplumber", "pdfminer"]
    else:
        methods = [method]

    for m in methods:
        if m == "pdfplumber":
            result = extract_with_pdfplumber(pdf_path, fmt, opts)
        elif m == "pypdf":
            result = extract_with_pypdf(pdf_path, fmt, opts)
        elif m == "pdfminer":
            result = extract_with_pdfminer(pdf_path, fmt)
        else:
            continue

        if result and result.strip():
            content_lines = [l for l in result.split("\n") if l.strip() and not l.startswith("===")]
            if len(content_lines) >= 3:
                # 标题结构审查（md 格式自动执行）
                if fmt == "md" and opts.heading:
                    result = _validate_heading_structure(result, opts)
                logger.info(f"✅ {m} 提取成功 ({len(content_lines)} 行)")
                return result
            logger.warning(f"{m} 内容过少，尝试下一种方法")

    logger.error("所有方法均失败，PDF 可能是扫描件或加密文件")
    return None


# ═══════════════════════════════════════════════════════════════════
#  输出
# ═══════════════════════════════════════════════════════════════════

def save_output(text: str, output_path: str) -> bool:
    try:
        out_dir = os.path.dirname(output_path)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
        logger.info(f"已保存: {output_path}")
        return True
    except Exception as e:
        logger.error(f"保存失败: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="PDF 文本/Markdown 提取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  %(prog)s doc.pdf -f md                    # Markdown 输出（含表格+标题）
  %(prog)s doc.pdf -f md --no-heading       # Markdown 但不标记标题
  %(prog)s doc.pdf -f md --no-table         # 不要表格
  %(prog)s doc.pdf -f md --table-min-cols 2 # 保留两列表格
  %(prog)s doc.pdf -f md --heading-size-delta 2.0  # 放宽标题字号阈值
""",
    )
    # 基本参数
    parser.add_argument("pdf_file", help="PDF 文件路径")
    parser.add_argument("-o", "--output", help="输出文件路径（默认同名 .txt/.md）")
    parser.add_argument("-m", "--method", choices=["auto", "pdfplumber", "pypdf", "pdfminer"], default="auto",
                        help="提取方法（默认 auto）")
    parser.add_argument("-f", "--format", choices=["text", "md"], default="text",
                        help="输出格式（默认 text）")
    parser.add_argument("-p", "--page-sep", action="store_true",
                        help="输出页分隔符 === Page N ===")
    parser.add_argument("--verbose", action="store_true", help="详细日志")

    # 标题控制
    hdr = parser.add_argument_group("标题识别（仅 -f md）")
    hdr.add_argument("--no-heading", action="store_true", help="禁用标题识别，输出纯文本")
    hdr.add_argument("--no-heading-pattern", action="store_true",
                     help="禁用文本模式匹配标题（仅保留字号判断）")
    hdr.add_argument("--heading-size-delta", type=float, default=1.0,
                     help="字号超过基准多少 pt 视为标题（默认 1.0）")
    hdr.add_argument("--heading-h1-ratio", type=float, default=1.5,
                     help="字号/基准 ≥ 此值标记 H1（默认 1.5）")
    hdr.add_argument("--heading-h2-ratio", type=float, default=1.25,
                     help="字号/基准 ≥ 此值标记 H2（默认 1.25）")
    hdr.add_argument("--heading-max-len", type=int, default=60,
                     help="模式匹配标题的最大行长度（默认 60）")

    # 标题结构审查
    review = parser.add_argument_group("标题结构审查（仅 -f md，自动执行）")
    review.add_argument("--heading-h1-max-len", type=int, default=40,
                        help="H1 标题最大字符数，超限逐级降级（默认 40）")
    review.add_argument("--heading-h2-max-len", type=int, default=50,
                        help="H2 标题最大字符数（默认 50）")
    review.add_argument("--heading-h3-max-len", type=int, default=50,
                        help="H3 标题最大字符数，超限降为正文（默认 50）")
    review.add_argument("--heading-consecutive-limit", type=int, default=3,
                        help="连续同级标题阈值，≥ 此数降为正文（默认 3）")
    review.add_argument("--heading-deco-pattern", type=str, default="",
                        help="自定义装饰性文字正则（分号分隔多条）")

    # 表格控制
    tbl = parser.add_argument_group("表格提取（仅 -f md）")
    tbl.add_argument("--no-table", action="store_true", help="禁用表格提取")
    tbl.add_argument("--table-min-cols", type=int, default=3,
                     help="最少列数，低于此值视为误判（默认 3）")

    # 布局控制
    lay = parser.add_argument_group("布局")
    lay.add_argument("--line-spacing", type=float, default=3.0,
                     help="行分组间距阈值 pt（默认 3.0）")

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # 构建 MdOptions
    opts = MdOptions(
        heading=not args.no_heading and args.format == "md",
        heading_size_delta=args.heading_size_delta,
        heading_h1_ratio=args.heading_h1_ratio,
        heading_h2_ratio=args.heading_h2_ratio,
        heading_pattern=not args.no_heading_pattern,
        heading_max_len=args.heading_max_len,
        heading_h1_max_len=args.heading_h1_max_len,
        heading_h2_max_len=args.heading_h2_max_len,
        heading_h3_max_len=args.heading_h3_max_len,
        heading_consecutive_limit=args.heading_consecutive_limit,
        heading_deco_patterns=args.heading_deco_pattern,
        table=not args.no_table,
        table_min_cols=args.table_min_cols,
        line_spacing=args.line_spacing,
        page_sep="===" if args.page_sep else "",
    )

    # 输出路径
    if args.output:
        output_path = args.output
    else:
        base = os.path.splitext(os.path.basename(args.pdf_file))[0]
        ext = ".md" if args.format == "md" else ".txt"
        output_path = base + ext

    # 环境检测
    env_ok, env_msg = check_python_env()
    if not env_ok:
        print(f"\n❌ 环境检测失败: {env_msg}")
        sys.exit(1)

    # 提取
    t0 = time.time()
    text = extract_pdf_text(args.pdf_file, args.method, args.format, opts)

    if text:
        if save_output(text, output_path):
            elapsed = time.time() - t0
            print(f"\n✅ 已提取到: {output_path}  (耗时 {elapsed:.1f}s)")
            sys.exit(0)
    else:
        print("\n❌ 提取失败。可能原因：")
        print("   1. PDF 是扫描件（图片格式）→ 需要 OCR")
        print("   2. PDF 加密 → 先解密")
        print("   3. 文件损坏")
        print("\n建议：")
        print("   python -m pip install pdfplumber pypdf pdfminer.six cffi")
        print("   python scripts/pdf_extractor.py file.pdf -m pypdf -f md")
        sys.exit(1)


if __name__ == "__main__":
    main()
