#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
山东电力交易中心 - 电力市场运行日报批量采集脚本
数据来源: https://pmos.sd.sgcc.com.cn

功能:
1. 通过API获取日报列表
2. 过滤指定年份的日报
3. 批量下载PDF文件
4. 支持断点续传
"""

import os
import json
import time
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class ShandongPowerDailyCrawler:
    """山东电力日报采集器"""
    
    # API 配置
    BASE_URL = "https://pmos.sd.sgcc.com.cn"
    LIST_API = "/px-phbsd-settlement-infpubdisclosure/unstructuredcommon/getData"
    DOWNLOAD_API = "/px-settlement-infpubmeex/fileService/download"
    
    # 日报类型ID（电力市场运行工作日报）
    INFORMATION_ID = "1607d409-652e-4948-85be-2d77d7556016"
    MARKET_ID = "PHBSD"
    
    # 请求头
    HEADERS = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Content-Type": "application/json;charset=UTF-8",
        "ClientTag": "OUTNET_BROWSE",
        "CurrentRoute": "/pxf-phbsd-settlement-infpubdisclosure/homePage/index",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/pxf-phbsd-settlement-infpubdisclosure/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "X-Ticket": "undefined"
    }
    
    def __init__(self, output_dir: str = "./shandong_power_daily", year: int = 2025):
        """
        初始化采集器
        
        Args:
            output_dir: PDF保存目录
            year: 要采集的年份
        """
        self.output_dir = Path(output_dir)
        self.year = year
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        
        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 下载状态记录文件
        self.status_file = self.output_dir / "download_status.json"
        self.download_status = self._load_status()
    
    def _load_status(self) -> dict:
        """加载下载状态"""
        if self.status_file.exists():
            with open(self.status_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"downloaded": [], "failed": []}
    
    def _save_status(self):
        """保存下载状态"""
        with open(self.status_file, 'w', encoding='utf-8') as f:
            json.dump(self.download_status, f, ensure_ascii=False, indent=2)
    
    def fetch_list(self, page_num: int = 1, page_size: int = 100) -> dict:
        """
        获取日报列表
        
        Args:
            page_num: 页码
            page_size: 每页数量
            
        Returns:
            API响应数据
        """
        url = f"{self.BASE_URL}{self.LIST_API}"
        payload = {
            "data": {
                "operateTimeArr": [],
                "customInfoName": "",
                "sourceName": "",
                "marketId": self.MARKET_ID,
                "informationIds": [self.INFORMATION_ID]
            },
            "pageInfo": {
                "pageSizes": [10, 20, 50, 100],
                "pageSize": page_size,
                "pageNum": page_num
            }
        }
        
        response = self.session.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def get_all_reports(self) -> list:
        """
        获取指定年份的所有日报信息
        
        Returns:
            日报记录列表
        """
        all_reports = []
        page_num = 1
        page_size = 100
        
        logger.info(f"开始获取 {self.year} 年日报列表...")
        
        while True:
            logger.info(f"正在获取第 {page_num} 页...")
            
            try:
                result = self.fetch_list(page_num, page_size)
                
                if result.get("status") != 0:
                    logger.error(f"API返回错误: {result.get('message')}")
                    break
                
                data = result.get("data", {})
                reports = data.get("list", [])
                total = data.get("total", 0)
                
                if not reports:
                    break
                
                # 过滤指定年份
                for report in reports:
                    if report.get("fyear") == self.year:
                        all_reports.append(report)
                
                logger.info(f"  获取到 {len(reports)} 条记录，累计 {self.year} 年记录: {len(all_reports)} 条")
                
                # 检查是否还有更多页
                if page_num * page_size >= total:
                    break
                
                page_num += 1
                time.sleep(0.5)  # 请求间隔，避免过快
                
            except Exception as e:
                logger.error(f"获取列表失败: {e}")
                break
        
        logger.info(f"共获取 {self.year} 年日报 {len(all_reports)} 条")
        return all_reports
    
    def parse_attachment(self, attachment_str: str) -> Optional[dict]:
        """
        解析附件信息
        
        Args:
            attachment_str: 附件JSON字符串
            
        Returns:
            附件信息字典 {"id": "xxx", "name": "xxx.pdf"}
        """
        try:
            attachments = json.loads(attachment_str)
            if attachments and len(attachments) > 0:
                return attachments[0]
        except Exception as e:
            logger.warning(f"解析附件信息失败: {e}")
        return None
    
    def download_pdf(self, file_id: str, save_path: Path) -> bool:
        """
        下载PDF文件
        
        Args:
            file_id: 文件ID
            save_path: 保存路径
            
        Returns:
            是否下载成功
        """
        url = f"{self.BASE_URL}{self.DOWNLOAD_API}"
        params = {"fileId": file_id}
        
        try:
            response = self.session.get(url, params=params, timeout=60, stream=True)
            response.raise_for_status()
            
            # 检查内容类型
            content_type = response.headers.get("Content-Type", "")
            if "pdf" not in content_type.lower() and "octet-stream" not in content_type.lower():
                logger.warning(f"响应内容类型异常: {content_type}")
            
            # 保存文件
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # 验证文件大小
            if save_path.stat().st_size < 1000:
                logger.warning(f"文件大小异常: {save_path.stat().st_size} bytes")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"下载失败: {e}")
            return False
    
    def generate_filename(self, report: dict) -> str:
        """
        生成文件名
        
        Args:
            report: 日报记录
            
        Returns:
            文件名 (格式: 2025-01-01_山东电力市场运行日报.pdf)
        """
        year = report.get("fyear", 2025)
        month = report.get("fmonth", 1)
        day = report.get("fday", 1)
        
        return f"{year}-{month:02d}-{day:02d}_山东电力市场运行日报.pdf"
    
    def run(self, skip_downloaded: bool = True, delay: float = 1.0):
        """
        执行采集任务
        
        Args:
            skip_downloaded: 是否跳过已下载的文件
            delay: 下载间隔（秒）
        """
        # 获取所有日报列表
        reports = self.get_all_reports()
        
        if not reports:
            logger.warning("未获取到日报数据")
            return
        
        # 统计信息
        total = len(reports)
        downloaded = 0
        skipped = 0
        failed = 0
        
        logger.info(f"开始下载，共 {total} 个文件...")
        
        for i, report in enumerate(reports, 1):
            guid = report.get("guid", "")
            title = report.get("title", "")
            filename = self.generate_filename(report)
            save_path = self.output_dir / filename
            
            # 检查是否已下载
            if skip_downloaded:
                if guid in self.download_status["downloaded"] or save_path.exists():
                    logger.info(f"[{i}/{total}] 跳过已下载: {filename}")
                    skipped += 1
                    continue
            
            # 解析附件
            attachment = self.parse_attachment(report.get("attachment", "[]"))
            if not attachment:
                logger.warning(f"[{i}/{total}] 无附件信息: {title}")
                failed += 1
                continue
            
            file_id = attachment.get("id", "")
            if not file_id:
                logger.warning(f"[{i}/{total}] 无文件ID: {title}")
                failed += 1
                continue
            
            # 下载
            logger.info(f"[{i}/{total}] 正在下载: {filename}")
            
            if self.download_pdf(file_id, save_path):
                downloaded += 1
                self.download_status["downloaded"].append(guid)
                self._save_status()
                logger.info(f"  ✓ 下载成功: {save_path.stat().st_size / 1024:.1f} KB")
            else:
                failed += 1
                if guid not in self.download_status["failed"]:
                    self.download_status["failed"].append(guid)
                self._save_status()
                logger.error(f"  ✗ 下载失败")
            
            # 下载间隔
            if i < total:
                time.sleep(delay)
        
        # 输出统计
        logger.info("=" * 50)
        logger.info(f"采集完成！")
        logger.info(f"  总计: {total} 个")
        logger.info(f"  新下载: {downloaded} 个")
        logger.info(f"  已跳过: {skipped} 个")
        logger.info(f"  失败: {failed} 个")
        logger.info(f"  保存目录: {self.output_dir.absolute()}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="山东电力交易日报采集工具")
    parser.add_argument("-y", "--year", type=int, default=2025, help="采集年份 (默认: 2025)")
    parser.add_argument("-o", "--output", type=str, default="./shandong_power_daily", help="输出目录")
    parser.add_argument("-d", "--delay", type=float, default=1.0, help="下载间隔秒数 (默认: 1.0)")
    parser.add_argument("--no-skip", action="store_true", help="不跳过已下载的文件")
    
    args = parser.parse_args()
    
    crawler = ShandongPowerDailyCrawler(
        output_dir=args.output,
        year=args.year
    )
    
    crawler.run(
        skip_downloaded=not args.no_skip,
        delay=args.delay
    )


if __name__ == "__main__":
    main()
