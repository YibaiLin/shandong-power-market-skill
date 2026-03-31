#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
山东电力市场运行日报 - 实时市场用电侧小时级电价提取工具 V4

更新说明 (V4):
1. 修正跨页提取逻辑：采用累积式提取策略
2. 智能推断时段：当表格缺少时刻标记行时，根据已有数据自动判断是1-12还是13-24时
3. 持续处理目标章节后的页面，直到收集完整24小时数据
4. 改进日志记录，显示具体的提取方法

继承 V3 的特性:
- 修正日期逻辑：文件名日期 - 1天 = 数据真实日期
- 支持递归目录扫描 (rglob)
- 支持 --year 参数过滤指定年份
"""

import os
import re
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple

import pdfplumber
import pandas as pd

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class RealtimePriceExtractor:
    """实时市场用电侧电价提取器"""

    # 目标关键词
    TARGET_SECTION = "实时市场用电侧小时级电价"
    TABLE_MARKER = "表3"

    def __init__(self, input_dir: str, output_dir: str = None, target_year: int = None):
        """
        初始化提取器

        Args:
            input_dir: PDF文件所在目录（将递归搜索）
            output_dir: 输出目录
            target_year: 目标年份（整数），如果指定，只保留该年份的数据
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir) if output_dir else self.input_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.target_year = target_year

        # 存储提取结果
        self.results: List[Dict] = []
        self.errors: List[Dict] = []

    def parse_real_date_from_filename(self, filename: str) -> Optional[str]:
        """
        从文件名解析日期，并减去1天得到真实数据日期

        Args:
            filename: 文件名，如 "2026-01-01_日报.pdf"

        Returns:
            真实日期字符串 "2025-12-31" 或 None
        """
        date_str = None
        # 匹配 YYYY-MM-DD 格式
        match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
        if match:
            date_str = match.group(1)
        else:
            # 匹配 YYYYMMDD 格式
            match = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
            if match:
                date_str = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

        if date_str:
            try:
                # 核心修改：将字符串转为日期对象，减去1天，再转回字符串
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                real_date = dt - timedelta(days=1)
                return real_date.strftime("%Y-%m-%d")
            except ValueError:
                return None

        return None

    def _extract_prices_from_table(self, table: List[List], prices: List[Optional[float]],
                                   require_section_marker: bool = True) -> Tuple[List[Optional[float]], bool]:
        """
        从表格中提取电价数据（累积式）

        Args:
            table: pdfplumber提取的表格数据
            prices: 当前的电价数组（24个元素）
            require_section_marker: 是否要求找到目标章节标记

        Returns:
            (更新后的prices数组, 是否找到了数据)
        """
        found_data = False
        found_target_section = not require_section_marker  # 如果不要求标记，默认认为已找到

        for i, row in enumerate(table):
            if not row:
                continue

            first_cell = str(row[0]) if row[0] else ""

            # 检查是否找到目标章节
            if require_section_marker:
                if self.TARGET_SECTION in first_cell or "用电侧" in first_cell:
                    found_target_section = True
                    continue

            # 只有找到目标章节后才处理电价行
            if found_target_section and first_cell == "电价":
                # 尝试从上一行获取时段标记
                time_marker = None
                if i > 0:
                    prev_row = table[i - 1]
                    if prev_row and len(prev_row) > 1:
                        second_cell = str(prev_row[1]) if prev_row[1] else ""
                        if second_cell == "1":
                            time_marker = "1-12"
                        elif second_cell == "13":
                            time_marker = "13-24"

                # 如果没有明确的时段标记，智能推断
                if not time_marker:
                    # 检查1-12时是否已有数据
                    first_half_filled = sum(1 for p in prices[0:12] if p is not None) >= 10
                    if first_half_filled:
                        # 前12时已填充，这应该是13-24时
                        time_marker = "13-24"
                    else:
                        # 前12时未填充，这应该是1-12时
                        time_marker = "1-12"

                # 根据时段标记提取数据
                if time_marker == "1-12":
                    for j in range(1, min(13, len(row))):
                        if row[j]:
                            try:
                                prices[j - 1] = float(re.sub(r"\s+", "", str(row[j])))
                                found_data = True
                            except:
                                pass
                elif time_marker == "13-24":
                    for j in range(1, min(13, len(row))):
                        if row[j]:
                            try:
                                prices[j + 11] = float(re.sub(r"\s+", "", str(row[j])))
                                found_data = True
                            except:
                                pass

        return prices, found_data

    def extract_from_pdf(self, pdf_path: Path) -> Tuple[Optional[List[float]], str]:
        """
        从单个PDF提取电价数据（改进的跨页处理）

        Returns:
            (24小时电价列表, 提取方法描述)
        """
        try:
            prices = [None] * 24
            found_target_page = False
            extraction_method = []

            with pdfplumber.open(pdf_path) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""

                    # 检查是否包含目标章节
                    if self.TARGET_SECTION in text:
                        found_target_page = True
                        extraction_method.append(f"p{page_idx+1}")

                    # 如果已找到目标页面，处理当前页和后续页的表格
                    if found_target_page:
                        tables = page.extract_tables()
                        for table in tables:
                            if table:
                                # 第一次在目标页面提取时，需要章节标记
                                require_marker = (page_idx == page_idx)  # 总是从找到的页面开始
                                prices, found_data = self._extract_prices_from_table(
                                    table, prices, require_section_marker=False
                                )

                        # 检查是否已收集完整数据
                        valid_count = sum(1 for p in prices if p is not None)
                        if valid_count >= 20:
                            # 收集到足够数据，可以返回
                            method_str = "+".join(extraction_method)
                            return prices, f"table_multi_page({method_str})" if len(extraction_method) > 1 else "table"

                        # 如果当前页没有更多表格，继续下一页
                        # （因为数据可能跨页）

            # 处理完所有页面后检查结果
            valid_count = sum(1 for p in prices if p is not None)
            if valid_count >= 20:
                method_str = "+".join(extraction_method)
                return prices, f"table_cross_page({method_str})"

            return None, "目标内容未找到或数据不完整"

        except Exception as e:
            return None, f"PDF读取错误: {str(e)}"

    def process_all(self) -> None:
        """处理目录下所有PDF文件（递归搜索）"""
        # 递归搜索所有PDF文件
        pdf_files = sorted(self.input_dir.rglob("*.pdf"))

        if not pdf_files:
            logger.warning(f"目录下（含子目录）未找到PDF文件: {self.input_dir}")
            return

        logger.info(f"共扫描到 {len(pdf_files)} 个PDF文件")

        processed_count = 0
        for i, pdf_path in enumerate(pdf_files, 1):
            filename = pdf_path.name

            # 使用新的日期解析逻辑（已包含 -1 天操作）
            real_date_str = self.parse_real_date_from_filename(filename)

            if not real_date_str:
                continue  # 跳过无法解析日期的文件

            # 如果设置了年份过滤
            if self.target_year:
                file_year = int(real_date_str.split('-')[0])
                if file_year != self.target_year:
                    continue  # 跳过非目标年份的数据

            processed_count += 1
            if processed_count % 10 == 0:
                logger.info(f"正在处理第 {processed_count} 个文件: {filename} (数据日期: {real_date_str})")

            prices, method_or_error = self.extract_from_pdf(pdf_path)

            if prices:
                record = {
                    "date": real_date_str,
                    "file": filename,
                    "method": method_or_error
                }
                for hour in range(1, 25):
                    record[f"h{hour}"] = prices[hour - 1]

                self.results.append(record)
            else:
                self.errors.append({
                    "file": filename,
                    "date": real_date_str,
                    "error": method_or_error
                })

        logger.info(f"处理结束，共尝试提取 {processed_count} 个符合条件的文件")

    def save_results(self) -> Tuple[Path, Path]:
        """保存结果到Excel和JSON"""
        if not self.results:
            logger.warning("无数据可保存")
            return None, None

        # 按日期排序
        self.results.sort(key=lambda x: x["date"])

        df_data = []
        for record in self.results:
            row = {"数据日期": record["date"], "来源文件": record["file"]}
            for hour in range(1, 25):
                row[f"{hour}时"] = record.get(f"h{hour}")
            df_data.append(row)

        df = pd.DataFrame(df_data)

        # 根据是否筛选年份生成文件名
        filename_suffix = f"_{self.target_year}" if self.target_year else ""
        excel_path = self.output_dir / f"山东电力_实时用电侧电价{filename_suffix}.xlsx"

        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='用电侧小时电价', index=False)

            # 错误记录表
            if self.errors:
                pd.DataFrame(self.errors).to_excel(writer, sheet_name='提取失败记录', index=False)

        logger.info(f"Excel已保存: {excel_path}")
        return excel_path, None

    def print_summary(self) -> None:
        """打印摘要"""
        print("\n" + "=" * 60)
        print(f"提取完成统计 (目标年份: {self.target_year if self.target_year else '全部'})")
        print("=" * 60)
        print(f"  提取成功天数: {len(self.results)}")
        print(f"  提取失败天数: {len(self.errors)}")

        if self.results:
            print(f"  数据日期范围: {self.results[0]['date']} ~ {self.results[-1]['date']}")
        print("=" * 60)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="山东电力日报 - 实时电价提取工具 V4")

    parser.add_argument("-i", "--input", type=str, default=".",
                        help="PDF文件根目录 (默认: 当前目录)")

    parser.add_argument("-o", "--output", type=str, default="output",
                        help="输出目录 (默认: output)")
    parser.add_argument("-y", "--year", type=int, default=None,
                        help="指定提取年份 (例如 2025)，脚本会自动处理跨年文件")

    args = parser.parse_args()

    extractor = RealtimePriceExtractor(
        input_dir=args.input,
        output_dir=args.output,
        target_year=args.year
    )

    extractor.process_all()
    extractor.save_results()
    extractor.print_summary()


if __name__ == "__main__":
    main()
