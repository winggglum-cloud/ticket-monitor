#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上海文化广场余票监控脚本 v2 - 修复版
使用Selenium执行JavaScript，支持动态加载
修复: 时区问题（UTC→UTC+8） & 移除测试模式
"""
import time
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import hashlib
import sys

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service  # ← 新增
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager  # ← 新增
except ImportError as e:
    print(f"❌ 需要安装依赖: pip install selenium webdriver-manager")
    exit(1)
