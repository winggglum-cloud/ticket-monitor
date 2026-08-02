#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上海文化广场余票监控脚本 v2 - 完整修复版
使用Selenium执行JavaScript，支持动态加载
修复: 时区问题（UTC→UTC+8） & Chrome无头模式
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
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError as e:
    print(f"❌ 需要安装依赖: pip install selenium webdriver-manager")
    exit(1)

# ==================== 时区工具 ====================
# 上海时区 (UTC+8)
SH_TZ = timezone(timedelta(hours=8))

def get_shanghai_time() -> str:
    """获取上海时间"""
    return datetime.now(SH_TZ).strftime('%Y-%m-%d %H:%M:%S')

# ==================== 配置部分 ====================
CONFIG = {
    "url": "https://www.shcstheatre.com/Program/ProgramDetails.aspx?headtype=YanChu&ARTICLE_ID=41885&id=41885",
    "notification": {
        "type": "email",
        "email": {
            "enabled": True,
            "sender": "1917543138@qq.com",
            "password": "ayboyiayjtkyeiii",
            "recipient": "1917543138@qq.com",
            "smtp_server": "smtp.qq.com",
            "smtp_port": 587
        },
    }
}

# ==================== 文件管理 ====================
def load_state() -> Dict:
    """加载上次的状态"""
    if os.path.exists("ticket_monitor_state.json"):
        try:
            with open("ticket_monitor_state.json", 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"last_hash": "", "available_count": 0}
    return {"last_hash": "", "available_count": 0}

def save_state(state: Dict):
    """保存当前状态"""
    with open("ticket_monitor_state.json", 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def get_content_hash(content: str) -> str:
    """计算内容哈希值"""
    return hashlib.md5(content.encode()).hexdigest()

# ==================== 通知系统 ====================
def send_email_notification(subject: str, message: str) -> bool:
    """发送邮件通知"""
    try:
        import smtplib
        from email.mime.text import MIMEText

        email_config = CONFIG["notification"]["email"]
        msg = MIMEText(message, 'html', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = email_config["sender"]
        msg['To'] = email_config["recipient"]

        with smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"]) as server:
            server.starttls()
            server.login(email_config["sender"], email_config["password"])
            server.send_message(msg)

        print(f"✅ 邮件已发送: {subject}")
        return True
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")
        return False

def send_notification(title: str, message: str):
    """发送通知"""
    if CONFIG["notification"]["email"]["enabled"]:
        send_email_notification(title, message)
    else:
        print(f"\n🔔 {title}\n{message}\n")

# ==================== 网页爬取 ====================
def extract_ticket_info(driver) -> Dict:
    """提取余票信息"""
    try:
        # 找到场次列表
        event_list_elem = driver.find_element(By.ID, "DT_EVENT_DATETIME")
        event_items = event_list_elem.find_elements(By.CLASS_NAME, "selection-date-details")

        tickets = []
        for item in event_items:
            try:
                # 获取日期和时间
                spans = item.find_elements(By.TAG_NAME, 'span')
                date_text = spans[0].text if len(spans) > 0 else "未知"
                time_text = spans[1].text if len(spans) > 1 else ""

                # 获取关键属性
                s_cnt = item.get_attribute('s_cnt') or '0'
                if_begin = item.get_attribute('if_begin') or '0'

                # 判断是否有余票
                seat_count = int(s_cnt) if s_cnt and s_cnt != '0' else 0
                is_available = seat_count > 0 and if_begin == '1'

                event_info = f"{date_text} {time_text}".strip()
                tickets.append({
                    "date_time": event_info,
                    "seat_count": seat_count,
                    "available": is_available,
                    "raw_text": f"{event_info} - {'✅有票' if is_available else '❌已售罄'} ({seat_count}张)"
                })
            except Exception as e:
                continue

        available_count = sum(1 for t in tickets if t["available"])
        return {
            "status": "success",
            "data": tickets,
            "count": len(tickets),
            "available_count": available_count
        }
    except Exception as e:
        print(f"❌ 提取信息失败: {e}")
        return {"status": "error", "data": [], "count": 0, "available_count": 0}

# ==================== 主监控逻辑 ====================
def check_tickets():
    """检查余票"""
    print(f"\n{'='*60}")
    print(f"🔍 检查时间: {get_shanghai_time()}")
    print(f"{'='*60}")

    driver = None
    try:
        # 创建Chrome选项
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  # 无头模式
        options.add_argument('--no-sandbox')  # GitHub Actions需要
        options.add_argument('--disable-dev-shm-usage')  # 禁用共享内存
        options.add_argument('--disable-gpu')  # 禁用GPU
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        # 创建WebDriver
        driver = webdriver.Chrome(options=options)

        print("   📡 正在访问页面...")
        driver.get(CONFIG["url"])

        # 等待元素加载
        print("   ⏳ 等待页面加载...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "selection-date-details"))
        )
        time.sleep(1)

        # 尝试点击"更多场次"按钮来展开所有场次
        try:
            more_button = driver.find_element(By.CLASS_NAME, "more-field-selection")
            if more_button:
                print("   📂 正在展开所有场次...")
                driver.execute_script("arguments[0].click();", more_button)
                time.sleep(3)
                print("   ✅ 已展开所有场次")
        except:
            pass

        # 滚动页面加载更多内容
        print("   📜 正在滚动页面加载内容...")
        for i in range(5):
            driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(0.5)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)

        # 提取信息
        ticket_info = extract_ticket_info(driver)
        driver.quit()
        driver = None

        print(f"📊 提取到 {ticket_info['count']} 条场次信息")
        print(f"🎟️ 其中有余票: {ticket_info['available_count']} 场")

        if ticket_info['count'] == 0:
            print("⚠️ 未找到场次信息")
            return

        # 计算哈希值
        content_hash = get_content_hash(json.dumps(ticket_info))
        state = load_state()

        # 只在有余票时才通知
        if ticket_info['available_count'] > 0:
            print(f"\n✨ 发现 {ticket_info['available_count']} 场有余票！")

            # 生成通知消息
            ticket_details = "\n".join([
                t['raw_text'] for t in ticket_info["data"] if t["available"]
            ])

            message = f"""
            <h2>🎭 大状王音乐剧 - 有新余票！</h2>
            <p><strong>发现时间:</strong> {get_shanghai_time()}</p>
            <p><strong>可购票场次:</strong></p>
            <pre>{ticket_details}</pre>
            <p><strong>立即购票:</strong> <a href="{CONFIG['url']}">点击这里</a></p>
            """
            send_notification("🎭 大状王音乐剧 - 有新余票！", message)
        else:
            print("⏸️ 暂无余票")

        # 打印所有场次状态
        print("\n📋 所有场次状态:")
        for idx, ticket in enumerate(ticket_info["data"], 1):
            print(f"   {idx}. {ticket['raw_text']}")

        # 保存状态
        state["last_hash"] = content_hash
        state["available_count"] = ticket_info['available_count']
        save_state(state)

    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

if __name__ == "__main__":
    check_tickets()
