#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai/prompts.py — AI 文件分析的提示词模板
"""

SYSTEM_PROMPT = """\
你是 DiskScanner 的文件分析助手。用户会提供磁盘扫描结果中的文件/目录列表，\
包含完整路径、最后修改日期、文件大小和类型。

你的任务：
1. 为每个条目提供简短的作用描述（中文，最多20个字符）
2. 判断该条目是否可以安全直接删除

删除建议等级：
- "safe": 临时文件、缓存、日志、缩略图缓存、安装包残留、空目录等可安全删除的内容
- "caution": 用户文档、下载文件、媒体文件、数据库文件等需根据用户需求判断
- "unsafe": 系统文件、配置文件、注册表、程序可执行文件、驱动、关键库文件等不建议删除的内容

输出要求：
- description 字段：简洁明了，最多20个中文字符
- deletability 字段：必须是 "safe"、"caution" 或 "unsafe" 之一
- reason 字段：简短解释删除建议理由，最多30个中文字符
- path 字段：必须与输入中的路径完全一致

始终以 JSON 格式返回结果，包含 items 数组。"""


USER_PROMPT_TEMPLATE = """\
扫描目录: {scan_path}
分析时间: {current_time}

以下是该目录下的 {count} 个{type_label}：

{formatted_items}

请分析以上条目并以 JSON 格式返回结果，包含 items 数组，每个元素包含 path、description、deletability、reason 字段。"""


def format_items_for_prompt(items, scan_path: str) -> str:
    """
    将 FileNode/DirNode 列表格式化为提示词文本

    Args:
        items: FileNode 或 DirNode 列表
        scan_path: 扫描根路径

    Returns:
        格式化后的文本
    """
    from datetime import datetime
    from disk_scanner import FileNode, DirNode, format_size

    lines = []
    for i, node in enumerate(items, 1):
        mod_str = "N/A"
        if node.modified and node.modified > 0:
            try:
                mod_str = datetime.fromtimestamp(node.modified).strftime("%Y-%m-%d")
            except (OSError, ValueError):
                pass

        if isinstance(node, DirNode):
            lines.append(
                f"{i}. [DIR] {node.path} | 修改: {mod_str}"
            )
        else:
            size_str = format_size(node.size)
            ext = getattr(node, 'extension', '') or ''
            lines.append(
                f"{i}. [FILE] {node.path} | 修改: {mod_str} | {size_str} | {ext}"
            )

    return "\n".join(lines)


def build_user_prompt(items, scan_path: str) -> str:
    """构建用户提示词"""
    from datetime import datetime
    from disk_scanner import DirNode

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = format_items_for_prompt(items, scan_path)

    # 判断类型标签
    has_dirs = any(isinstance(n, DirNode) for n in items)
    has_files = any(not isinstance(n, DirNode) for n in items)
    if has_dirs and has_files:
        type_label = "文件和目录"
    elif has_dirs:
        type_label = "目录"
    else:
        type_label = "文件"

    return USER_PROMPT_TEMPLATE.format(
        scan_path=scan_path,
        current_time=current_time,
        count=len(items),
        type_label=type_label,
        formatted_items=formatted,
    )
