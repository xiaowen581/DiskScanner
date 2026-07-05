#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build.py — DiskScanner PyQt5 打包脚本
使用 PyInstaller 将应用打包为可执行程序
"""

import os
import sys
import shutil
import platform
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.absolute()

def clean_build():
    """清理构建目录"""
    dirs_to_remove = ['build', 'dist']
    files_to_remove = ['DiskScanner.spec']
    
    for dir_name in dirs_to_remove:
        dir_path = PROJECT_ROOT / dir_name
        if dir_path.exists():
            print(f"正在清理目录: {dir_name}")
            shutil.rmtree(dir_path)
    
    for file_name in files_to_remove:
        file_path = PROJECT_ROOT / file_name
        if file_path.exists():
            print(f"正在删除文件: {file_name}")
            file_path.unlink()

def build_rust_extension():
    """构建 Rust 扩展模块 (scanner_core)，失败则中止"""
    scanner_core_dir = PROJECT_ROOT / 'scanner_core'
    if not scanner_core_dir.exists():
        print("错误: 未找到 scanner_core 目录，Rust 扩展模块缺失")
        sys.exit(1)

    # 确保 maturin 已安装
    import subprocess
    check = subprocess.run([sys.executable, '-m', 'pip', 'show', 'maturin'],
                           capture_output=True)
    if check.returncode != 0:
        print("正在安装 maturin...")
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', 'maturin'])
        if result.returncode != 0:
            print("错误: 安装 maturin 失败，请手动安装: pip install maturin")
            sys.exit(1)

    print("正在构建 Rust 扩展模块 (scanner_core)...")
    result = subprocess.run(
        [sys.executable, '-m', 'maturin', 'develop', '--release'],
        cwd=str(scanner_core_dir),
    )
    if result.returncode != 0:
        print("错误: Rust 扩展构建失败，请检查上方日志排查问题")
        sys.exit(1)

    # 验证 .pyd 已安装
    try:
        import scanner_core
        print(f"✓ Rust 扩展构建成功")
    except ImportError:
        print("错误: scanner_core 构建成功但无法导入，请检查 maturin 安装路径")
        sys.exit(1)


def build_executable():
    """使用 PyInstaller 打包应用"""
    try:
        import PyInstaller
    except ImportError:
        print("错误: 未安装 PyInstaller")
        print("请先安装: pip install pyinstaller")
        sys.exit(1)
    
    # 定位 scanner_core 包路径
    import importlib.util, glob
    spec = importlib.util.find_spec('scanner_core')
    if spec is None or spec.origin is None:
        print("错误: 无法定位 scanner_core 包，请确认 maturin develop 已成功执行")
        sys.exit(1)
    pkg_dir = os.path.dirname(spec.origin)
    pyd_files = glob.glob(os.path.join(pkg_dir, '*.pyd')) + glob.glob(os.path.join(pkg_dir, '*.so'))
    if not pyd_files:
        print(f"错误: 在 {pkg_dir} 中未找到 .pyd/.so 文件")
        sys.exit(1)
    pyd_path = pyd_files[0]
    init_path = os.path.join(pkg_dir, '__init__.py')
    print(f"scanner_core.pyd: {pyd_path}")
    print(f"scanner_core init: {init_path}")

    # 构建命令
    cmd = [
        'pyinstaller',
        '--name=DiskScanner',
        '--windowed',  # 使用 GUI 模式，不显示控制台
        '--onefile',   # 打包为单个可执行文件
        '--noconfirm', # 不确认覆盖
        '--clean',     # 清理临时文件
        '--hidden-import=scanner_core',   # 确保 Rust 扩展被发现
        f'--add-binary={pyd_path}{os.pathsep}scanner_core',  # 显式打包 .pyd
        f'--add-data={init_path}{os.pathsep}scanner_core',   # 显式打包 __init__.py
    ]
    
    # 添加图标（如果存在）
    icon_path = PROJECT_ROOT / 'icon.ico'
    if icon_path.exists():
        cmd.append(f'--icon={icon_path}')
        print(f"使用图标: {icon_path}")
    else:
        print("未找到 icon.ico，将使用默认图标")
    
    # 添加数据文件（如果需要）
    # 例如: cmd.append('--add-data=ui;ui')
    
    # 入口文件
    cmd.append('pyqt_gui.py')
    
    print("\n开始构建...")
    print(f"命令: {' '.join(cmd)}")
    print()
    
    # 执行 PyInstaller
    exit_code = os.system(' '.join(cmd))
    
    if exit_code == 0:
        print("\n✓ 构建成功!")
        
        # 显示输出文件
        if platform.system() == 'Windows':
            exe_path = PROJECT_ROOT / 'dist' / 'DiskScanner.exe'
        else:
            exe_path = PROJECT_ROOT / 'dist' / 'DiskScanner'
        
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"✓ 可执行文件: {exe_path}")
            print(f"✓ 文件大小: {size_mb:.2f} MB")
    else:
        print("\n✗ 构建失败!")
        sys.exit(1)

def main():
    """主函数"""
    print("=" * 60)
    print("DiskScanner PyQt5 打包工具")
    print("=" * 60)
    print()
    
    # 询问是否清理旧构建
    if (PROJECT_ROOT / 'dist').exists():
        response = input("是否清理旧的构建文件? (y/n): ").strip().lower()
        if response == 'y':
            clean_build()
    else:
        clean_build()
    
    print()
    # 构建 Rust 扩展（必须成功）
    build_rust_extension()
    print()
    build_executable()

if __name__ == '__main__':
    main()
