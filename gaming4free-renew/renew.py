#!/usr/bin/env python3
"""
Gaming4Free Renew Pro v14 - 终极修复版
- 移除 with SB 上下文管理器，改用 try/finally 避免 autocrlf 压缩问题
- 直接调用 Livewire API 触发续期
- 深度广告 DOM 监测
- 模拟真人活跃状态
- 多层冷却检测
"""
import os, sys, time, re, json, traceback, urllib.parse, urllib.request
from datetime import datetime

try:
    from seleniumbase import SB
except ImportError:
    print("seleniumbase not installed. Run: pip install seleniumbase")
    sys.exit(1)

from utils import log, screenshot, parse_countdown_seconds
from utils import get_remaining_time
from cooldown import check_button_cooldown
from tg_notify import send_tg
from config import SERVERS

MAX_BROWSER_RETRIES = 3
RENEW_THRESHOLD_SECONDS = 45 * 3600
MAX_ROUNDS = 10

def main():
    log("========== 开始处理服务器账号 (Pro v14) ==========")
    if not SERVERS:
        log("❌ 未配置服务器信息")
        sys.exit(1)

    for server_name, server_url, server_cookie in SERVERS:
        log(f"\n🔑 准备执行账号操作: {server_name}")
        
        success_in_this_server = False
        for browser_attempt in range(MAX_BROWSER_RETRIES):
            if success_in_this_server:
                break
            
            sb = None
            driver = None
            try:
                log(f"🚀 启动浏览器 (第 {browser_attempt+1}/{MAX_BROWSER_RETRIES} 次尝试)...")
                sb = SB(uc=True, headless=False, browser='chrome',
                        agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
                driver = sb.driver
                driver.set_page_load_timeout(120)

                log(f"🌐 访问页面: {server_url}")
                driver.get(server_url)
                
                if server_cookie:
                    log("🍪 注入 Cookie...")
                    for item in server_cookie.split(";"):
                        item = item.strip()
                        if "=" in item:
                            name, value = item.split("=", 1)
                            try:
                                driver.add_cookie({"name": name.strip(), "value": value.strip(), "domain": ".gaming4free.net", "path": "/", "secure": True})
                            except:
                                pass
                    driver.refresh()
                    time.sleep(10)

                current_round = 0
                while current_round < MAX_ROUNDS:
                    current_round += 1
                    log(f"\n🔄 --- 第 {current_round}/{MAX_ROUNDS} 轮续期 ---")
                    
                    before_lt, before_ls = get_remaining_time(driver)
                    log(f"⏱️ 当前剩余时长: {before_lt} ({before_ls}秒)")
                    
                    if before_ls >= RENEW_THRESHOLD_SECONDS:
                        log(f"✅ 目标时长已达标，停止续期")
                        success_in_this_server = True
                        break

                    # 检查 5 分钟冷却
                    try:
                        page_text = driver.execute_script("return document.body.innerText")
                        if "05:00" in page_text and "cd" in page_text:
                            log("⏳ 侦测到 5 分钟冷却期 (05:00 cd)，强制等待 310 秒...")
                            time.sleep(310)
                            driver.refresh()
                            time.sleep(10)
                            continue
                    except:
                        pass

                    # 检查按钮冷却
                    cooldown_info = check_button_cooldown(driver)
                    if cooldown_info and cooldown_info.get('cooldown'):
                        remaining = cooldown_info.get('remaining', 0)
                        log(f"⏳ 按钮冷却中，剩余 {remaining}秒，等待...")
                        time.sleep(min(remaining, 300))
                        driver.refresh()
                        time.sleep(5)
                        continue

                    # 触发续期
                    log("🖱️ 尝试触发续期...")
                    try:
                        lw_result = driver.execute_script("""
                            try {
                                var comps = Livewire.all;
                                for (var i = 0; i < comps.length; i++) {
                                    try { comps[i].call('extend'); return 'success'; } catch(e) {}
                                }
                            } catch(e) {}
                            try {
                                var btn = document.querySelector('button.rt-btn-free');
                                if (btn) { btn.click(); return 'clicked'; }
                            } catch(e) {}
                            return 'fail';
                        """)
                        if lw_result == 'success':
                            log("✅ Livewire API 调用成功")
                        elif lw_result == 'clicked':
                            log("✅ 按钮点击成功")
                        else:
                            log("⚠️ Livewire 调用失败，回退到模拟点击")
                            driver.execute_script("document.querySelector('button.rt-btn-free').click();")
                    except Exception as e:
                        log(f"⚠️ 触发续期异常: {e}")

                    # 处理验证码
                    time.sleep(5)
                    try:
                        if driver.find_elements('css selector', 'iframe[src*="challenges.cloudflare.com"]'):
                            log("🛡️ 等待 Turnstile 验证...")
                            for _ in range(30):
                                if not driver.find_elements('css selector', 'iframe[src*="challenges.cloudflare.com"]'):
                                    log("✅ Turnstile 已通过")
                                    break
                                time.sleep(1)
                    except:
                        pass
                    
                    # 深度广告监测与等待
                    log("🎬 监测广告播放中...")
                    start_wait = time.time()
                    while time.time() - start_wait < 90:
                        driver.execute_script("window.dispatchEvent(new Event('mousemove'));")
                        try:
                            driver.execute_script("""
                                var closeBtns = document.querySelectorAll('[aria-label="Close"], .modal-close, button[aria-label="Close"]');
                                for(var i=0; i<closeBtns.length; i++) {
                                    if(closeBtns[i].offsetParent !== null) closeBtns[i].click();
                                }
                            """)
                        except:
                            pass
                        try:
                            after_check = get_remaining_time(driver)
                            if after_check[1] > before_ls + 100:
                                log(f"✅ 检测到时间增加 ({after_check[0]} > {before_lt})，提前跳出广告等待")
                                break
                        except:
                            pass
                        time.sleep(5)

                    # 验证续期结果
                    try:
                        driver.refresh()
                        time.sleep(5)
                    except:
                        time.sleep(10)
                    
                    after_lt, after_ls = get_remaining_time(driver)
                    diff = after_ls - before_ls
                    log(f"⏱️ 续期后: {after_lt} ({after_ls}秒)，增加: {diff}秒")
                    
                    if diff > 0:
                        log(f"✅ 续期成功! 增加 {diff}秒 ({before_lt} → {after_lt})")
                        send_tg(f"✅ Pro续期成功 (+{diff}s)", server_name, after_lt)
                        break
                    else:
                        log(f"❌ 本轮续期失败，继续下一轮...")
                        time.sleep(10)
                
                if success_in_this_server:
                    break
                    
            except Exception as e:
                log(f"❌ 服务器 '{server_name}' 执行异常: {e}")
                try:
                    screenshot(sb, "错误截图")
                except:
                    pass
                send_tg(f"❌ 执行异常: {e}", server_name)
                break
            finally:
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                if sb:
                    try:
                        sb.quit()
                    except:
                        pass

if __name__ == "__main__":
    main()
