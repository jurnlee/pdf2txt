#!/usr/bin/env python3
"""
PDF 文本提取工具
支持多种提取方法，自动选择最佳方案
"""

import os
import sys
import argparse
import logging
import time
from pathlib import Path
from typing import Optional, Tuple

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('pdf_extraction.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


def extract_with_pdfplumber(pdf_path: str) -> Optional[str]:
    """使用 pdfplumber 提取文本"""
    try:
        import pdfplumber
        logger.info(f"使用 pdfplumber 提取: {pdf_path}")
        text_parts = []
        
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            for i, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"=== Page {i} ===\n{page_text}\n")
                else:
                    text_parts.append(f"=== Page {i} === [无文本]\n")
                
                if i % 10 == 0 or i == total_pages:
                    logger.info(f"  处理进度: {i}/{total_pages}")
        
        if not any("无文本" in part for part in text_parts):
            logger.info("pdfplumber 提取完成，所有页面均有文本")
        else:
            logger.warning("pdfplumber 提取到部分页面无文本")
        
        return "".join(text_parts)
    except ImportError:
        logger.error("pdfplumber 未安装，请运行: pip install pdfplumber")
        return None
    except Exception as e:
        logger.error(f"pdfplumber 提取失败: {str(e)}")
        return None


def extract_with_pypdf(pdf_path: str) -> Optional[str]:
    """使用 pypdf 提取文本"""
    try:
        from pypdf import PdfReader
        logger.info(f"使用 pypdf 提取: {pdf_path}")
        text_parts = []
        
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        
        for i, page in enumerate(reader.pages, 1):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(f"=== Page {i} ===\n{page_text}\n")
            else:
                text_parts.append(f"=== Page {i} === [无文本]\n")
            
            if i % 10 == 0 or i == total_pages:
                logger.info(f"  处理进度: {i}/{total_pages}")
        
        if not any("无文本" in part for part in text_parts):
            logger.info("pypdf 提取完成，所有页面均有文本")
        else:
            logger.warning("pypdf 提取到部分页面无文本")
        
        return "".join(text_parts)
    except ImportError:
        logger.error("pypdf 未安装，请运行: pip install pypdf")
        return None
    except Exception as e:
        logger.error(f"pypdf 提取失败: {str(e)}")
        return None


def extract_with_pdfminer(pdf_path: str) -> Optional[str]:
    """使用 pdfminer.six 提取文本（更精确的布局分析）"""
    try:
        from pdfminer.high_level import extract_text
        logger.info(f"使用 pdfminer.six 提取: {pdf_path}")
        text = extract_text(pdf_path)
        if text:
            logger.info("pdfminer.six 提取完成")
            # 添加分页标记（pdfminer不提供分页信息）
            lines = text.split('\n')
            pages = []
            current_page = []
            chars_per_page = 2000  # 每页大约字符数
            
            for line in lines:
                current_page.append(line)
                if sum(len(l) for l in current_page) >= chars_per_page:
                    pages.append("=== Page 估计 ===" + "\n".join(current_page))
                    current_page = []
            
            if current_page:
                pages.append("=== Page 估计 ===" + "\n".join(current_page))
            
            return "\n\n".join(pages)
        else:
            logger.warning("pdfminer.six 未提取到文本")
            return None
    except ImportError:
        logger.error("pdfminer.six 未安装，请运行: pip install pdfminer.six")
        return None
    except Exception as e:
        logger.error(f"pdfminer.six 提取失败: {str(e)}")
        return None


def check_pdf_file(pdf_path: str) -> Tuple[bool, str]:
    """检查PDF文件是否有效"""
    if not os.path.exists(pdf_path):
        return False, f"文件不存在: {pdf_path}"
    
    if not pdf_path.lower().endswith('.pdf'):
        return False, f"文件不是PDF格式: {pdf_path}"
    
    try:
        with open(pdf_path, 'rb') as f:
            header = f.read(5)
            if not header.startswith(b'%PDF'):
                return False, "文件不是有效的PDF（缺少PDF签名）"
    except Exception as e:
        return False, f"文件读取失败: {str(e)}"
    
    return True, "文件有效"


def extract_pdf_text(pdf_path: str, method: str = 'auto') -> Optional[str]:
    """
    提取PDF文本
    
    Args:
        pdf_path: PDF文件路径
        method: 提取方法，可选 'auto', 'pdfplumber', 'pypdf', 'pdfminer'
    
    Returns:
        提取的文本或None
    """
    # 检查文件
    is_valid, msg = check_pdf_file(pdf_path)
    if not is_valid:
        logger.error(msg)
        return None
    
    file_size = os.path.getsize(pdf_path) / (1024 * 1024)  # MB
    logger.info(f"开始提取: {pdf_path} ({file_size:.2f} MB)")
    
    # 自动选择方法
    if method == 'auto':
        methods = ['pdfplumber', 'pypdf', 'pdfminer']
    else:
        methods = [method]
    
    extracted_text = None
    
    for method_name in methods:
        if method_name == 'pdfplumber':
            extracted_text = extract_with_pdfplumber(pdf_path)
        elif method_name == 'pypdf':
            extracted_text = extract_with_pypdf(pdf_path)
        elif method_name == 'pdfminer':
            extracted_text = extract_with_pdfminer(pdf_path)
        
        if extracted_text and extracted_text.strip():
            # 检查是否有实际内容（不只是页码标记）
            content_lines = [line for line in extracted_text.split('\n') 
                           if line.strip() and not line.startswith('===')]
            if len(content_lines) > 5:  # 至少有5行内容
                logger.info(f"使用 {method_name} 成功提取文本")
                break
            else:
                logger.warning(f"{method_name} 提取的内容过少，尝试其他方法")
                extracted_text = None
    
    if extracted_text:
        # 统计信息
        lines = extracted_text.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        logger.info(f"提取完成: {len(non_empty_lines)} 行非空文本，{len(extracted_text)} 字符")
    else:
        logger.error("所有提取方法均失败，PDF可能是扫描件(图片)或加密文件")
    
    return extracted_text


def save_text_to_file(text: str, output_path: str) -> bool:
    """保存文本到文件"""
    try:
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        logger.info(f"文本已保存到: {output_path}")
        return True
    except Exception as e:
        logger.error(f"保存文件失败: {str(e)}")
        return False


def main():
    parser = argparse.ArgumentParser(description='PDF 文本提取工具')
    parser.add_argument('pdf_file', help='PDF文件路径')
    parser.add_argument('-o', '--output', help='输出文本文件路径（默认：同名.txt）')
    parser.add_argument('-m', '--method', 
                       choices=['auto', 'pdfplumber', 'pypdf', 'pdfminer'],
                       default='auto',
                       help='提取方法（默认：auto）')
    parser.add_argument('--verbose', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # 确定输出路径
    if args.output:
        output_path = args.output
    else:
        pdf_name = os.path.splitext(os.path.basename(args.pdf_file))[0]
        output_path = f"{pdf_name}_extracted.txt"
    
    # 提取文本
    start_time = time.time()
    text = extract_pdf_text(args.pdf_file, args.method)
    
    if text:
        # 保存文本
        if save_text_to_file(text, output_path):
            elapsed = time.time() - start_time
            logger.info(f"任务完成，耗时: {elapsed:.2f} 秒")
            print(f"\n✅ 文本已提取到: {output_path}")
            sys.exit(0)
        else:
            logger.error("保存失败")
            sys.exit(1)
    else:
        logger.error("文本提取失败")
        print("\n❌ 提取失败，可能的原因：")
        print("   1. PDF是扫描件（图片格式）")
        print("   2. PDF加密或受保护")
        print("   3. 缺少必要的Python库")
        print("   4. 文件损坏")
        print("\n建议：")
        print("   1. 安装依赖: pip install pdfplumber pypdf pdfminer.six")
        print("   2. 尝试不同方法: python pdf_extractor.py file.pdf -m pypdf")
        print("   3. 对于扫描件，需要使用OCR工具")
        sys.exit(1)


if __name__ == '__main__':
    main()