#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
host2play 自动续期脚本
=====================
- 使用 DrissionPage 自动化浏览器操作
- 支持代理配置（家宽代理 / WARP）
- 支持 reCAPTCHA 音频验证码识别
- 支持多账号批量续期
"""

import os
import sys
import time
import json
import random
import logging
import requests
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone

# ==========================================================
# 配置
# ==========================================================
RENEW_URL = os.getenv("H2P_RENEW_URL", "")
COOKIE_STR = os.getenv("H2P_COOKIE", "")
WARP_PROXY = os.getenv("WARP_PROXY", "")
PROXY_URL = os.getenv("PROXY_URL", "")
RENEW_THRESHOLD_SECONDS = 25 * 3600  # 剩余超过25小时则跳过
MAX_RETRY = 5
PAGE_TIMEOUT = 180  # 增加到180秒，避免Chrome渲染进程超时
TG_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "")
TZ_CN = timezone(timedelta(hours=8))


def now_cn():
    return datetime.now(TZ_CN)


ROOT = Path(__file__).parent
SHOT_DIR = ROOT / "output" / "screenshots"
SHOT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("host2play")


# ==========================================================
# 工具函数
# ==========================================================

def tg(msg: str, silent: bool = False):
    prefix = "\U0001f3ae <b>host2play</b>\n"
    if "host2play" not in msg.lower():
        msg = prefix + msg
    if not TG_TOKEN or not TG_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={
                "chat_id": TG_CHAT_ID,
                "text": msg,
                "parse_mode": "HTML",
                "disable_notification": silent,
            },
            timeout=10,
        )
    except Exception:
        pass


def parse_expires(text: str) -> int:
    """解析剩余时间文本，返回秒数"""
    if not text:
        return -1
    m = re.search(r"(\d{1,2}):(\d{2}):(\d{2})", text)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    return -1


def get_server_info(page):
    """获取服务器信息和剩余时间"""
    server_id = "Unknown"
    expires_text = "Unknown"
    expires_sec = -1

    for attempt in range(10):
        try:
            text_content = page.run_js("return document.body.innerText")
            time_match = re.search(r"(\d{1,2}:\d{2}:\d{2})", text_content)
            if time_match:
                expires_text = time_match.group(1)
                expires_sec = parse_expires(expires_text)
                sid_match = re.search(r"Renew server:\s*([a-zA-Z0-9\-]+)", text_content, re.IGNORECASE)
                if sid_match:
                    server_id = sid_match.group(1)
                # 同时尝试其他可能的服务器ID格式
                if server_id == "Unknown":
                    sid_match2 = re.search(r"Server:\s*([a-zA-Z0-9\-]+)", text_content, re.IGNORECASE)
                    if sid_match2:
                        server_id = sid_match2.group(1)
                if server_id != "Unknown":
                    break
        except Exception:
            pass
        time.sleep(2)

    return server_id, expires_text, expires_sec


def debug_dump(page, label=""):
    """调试：保存截图和页面源码"""
    try:
        shot_path = SHOT_DIR / f"debug_{label}_{int(time.time())}.png"
        page.get_screenshot(path=str(shot_path))
        log.info(f"调试截图已保存: {shot_path}")
    except Exception:
        pass
    try:
        src_path = SHOT_DIR / f"debug_src_{label}_{int(time.time())}.txt"
        src_path.write_text(page.html[:5000], encoding="utf-8")
        log.info(f"页面源码已保存: {src_path} (前5000字符)")
    except Exception:
        pass


def solve_recaptcha_audio(page) -> bool:
    """解决 reCAPTCHA 音频验证码 - 增强版"""
    try:
        import speech_recognition as sr
        import pydub
    except ImportError:
        log.error("缺少依赖: SpeechRecognition 或 pydub")
        return False

    log.info("开始处理 reCAPTCHA...")

    # ========== 第一步：查找 reCAPTCHA checkbox ==========
    checkbox_found = False
    iframe_found = False

    # 方法1：查找所有 recaptcha iframe
    all_iframes = []
    try:
        all_iframes = page.eles('css:iframe')
        log.info(f"页面中共找到 {len(all_iframes)} 个 iframe")
    except Exception as e:
        log.warning(f"获取 iframe 列表失败: {e}")

    for idx, frame in enumerate(all_iframes):
        src = frame.attr("src") or ""
        title = frame.attr("title") or ""
        log.info(f"  iframe[{idx}] src={src[:80]} title={title[:40]}")
        if "recaptcha" in src.lower() or "recaptcha" in title.lower():
            iframe_found = True
            checkbox_iframe = frame
            log.info(f"找到 reCAPTCHA iframe: {src[:80]}")

            # 进入 iframe
            try:
                page.switch_to.frame(checkbox_iframe)
            except Exception:
                log.warning("切换到 iframe 失败，尝试其他方式")
                continue

            # 查找 checkbox
            try:
                checkbox = page.ele('css:.recaptcha-checkbox-checkmark', timeout=5)
                if checkbox:
                    log.info("找到 checkbox，准备点击...")
                    checkbox.click()
                    checkbox_found = True
                    log.info("已点击 checkbox")
                    time.sleep(random.uniform(2, 4))
                else:
                    # 可能已经通过了
                    log.info("未找到 checkbox，可能已通过验证")
                    checkbox_found = True
            except Exception as e:
                log.warning(f"点击 checkbox 失败: {e}")
                # 尝试点击任意可见元素
                try:
                    els = page.eles('css:div[role="checkbox"]', timeout=3)
                    if els:
                        els[0].click()
                        checkbox_found = True
                        log.info(f"通过 role=checkbox 点击成功")
                        time.sleep(random.uniform(2, 4))
                except Exception:
                    pass
            finally:
                try:
                    page.switch_to.main_frame()
                except Exception:
                    pass
            break

    # 如果没有找到 iframe，尝试更宽松的选择器
    if not iframe_found:
        log.info("未通过 iframe 列表找到 reCAPTCHA，尝试宽松选择器...")
        selectors = [
            'css:iframe[src*="recaptcha"]',
            'css:iframe[src*="google.com/recaptcha"]',
            'xpath://iframe[contains(@src, "recaptcha")]',
            'css:iframe[title*="recaptcha"]',
        ]
        for sel in selectors:
            try:
                checkbox_iframe = page.ele(sel, timeout=5)
                if checkbox_iframe:
                    iframe_found = True
                    log.info(f"宽松选择器找到 iframe: {sel}")

                    try:
                        page.switch_to.frame(checkbox_iframe)
                    except Exception:
                        log.warning("切换到 iframe 失败")
                        continue

                    try:
                        checkbox = page.ele('css:.recaptcha-checkbox-checkmark', timeout=5)
                        if checkbox:
                            checkbox.click()
                            checkbox_found = True
                            log.info("已点击 checkbox")
                            time.sleep(random.uniform(2, 4))
                        else:
                            log.info("未找到 checkbox，可能已通过验证")
                            checkbox_found = True
                    except Exception as e:
                        log.warning(f"点击 checkbox 失败: {e}")
                    finally:
                        try:
                            page.switch_to.main_frame()
                        except Exception:
                            pass
                    break
            except Exception:
                pass

    # 如果还是没找到 iframe，尝试查找任何可见的 reCAPTCHA 相关元素
    if not iframe_found:
        log.info("未找到 iframe，尝试查找页面上的 reCAPTCHA 相关元素...")
        try:
            body_text = page.run_js("return document.body.innerText")
            if "recaptcha" in body_text.lower():
                log.info("页面文本中包含 recaptcha 关键字")
                # 尝试通过 JS 点击
                click_result = page.run_js("""
                    var iframes = document.querySelectorAll('iframe');
                    for (var i = 0; i < iframes.length; i++) {
                        if (iframes[i].src.indexOf('recaptcha') !== -1) {
                            return 'FOUND:' + iframes[i].src.substring(0, 80);
                        }
                    }
                    return 'NOT_FOUND';
                """)
                log.info(f"JS 检测结果: {click_result}")
            else:
                log.info("页面文本中不包含 recaptcha 关键字")
        except Exception as e:
            log.warning(f"页面文本检测失败: {e}")

        # 保存调试截图
        debug_dump(page, "before_click")

        # 尝试点击 Renew 按钮附近的区域，看看是否有 checkbox
        try:
            # 尝试点击页面中心区域（可能有 checkbox 浮层）
            page.run_js("window.scrollTo(0, document.body.scrollHeight / 2)")
            time.sleep(2)
        except Exception:
            pass

    # 如果 checkbox 也没找到，尝试全局查找
    if not checkbox_found:
        log.info("未找到 checkbox，尝试全局查找...")
        # 再次尝试所有 iframe
        all_iframes2 = []
        try:
            all_iframes2 = page.eles('css:iframe')
        except Exception:
            pass

        for frame in all_iframes2:
            src = frame.attr("src") or ""
            if "recaptcha" in src.lower():
                try:
                    page.switch_to.frame(frame)
                    time.sleep(1)
                    # 尝试多种选择器
                    for sel in ['css:.recaptcha-checkbox-input', 'css:input[type="checkbox"]', 'css:div[role="checkbox"]']:
                        try:
                            el = page.ele(sel, timeout=3)
                            if el:
                                el.click()
                                checkbox_found = True
                                log.info(f"通过选择器 {sel} 找到并点击了 checkbox")
                                time.sleep(random.uniform(2, 4))
                                break
                        except Exception:
                            continue
                    page.switch_to.main_frame()
                    if checkbox_found:
                        break
                except Exception as e:
                    log.warning(f"处理 iframe 失败: {e}")
                    try:
                        page.switch_to.main_frame()
                    except Exception:
                        pass

    # 如果仍然没有找到 checkbox，尝试直接点击 Renew 按钮看是否能自动通过
    if not checkbox_found:
        log.info("未能找到 reCAPTCHA checkbox，尝试直接点击 Renew 按钮...")
        debug_dump(page, "no_checkbox")
        # 也许不需要验证码，直接重试找 Renew 按钮
        return False

    time.sleep(2)

    # ========== 第二步：处理 reCAPTCHA 挑战（音频验证码） ==========
    for attempt in range(MAX_RETRY):
        log.info(f"第 {attempt + 1} 次尝试 reCAPTCHA 挑战...")

        # 保存当前页面状态
        debug_dump(page, f"challenge_start_{attempt}")

        # 查找 challenge iframe
        challenge_iframe = None
        all_iframes_challenge = []
        try:
            all_iframes_challenge = page.eles('css:iframe')
            log.info(f"挑战阶段找到 {len(all_iframes_challenge)} 个 iframe")
        except Exception:
            pass

        for idx, frame in enumerate(all_iframes_challenge):
            src = frame.attr("src") or ""
            if "recaptcha" in src.lower() and "bframe" in src.lower():
                challenge_iframe = frame
                log.info(f"找到 challenge iframe[{idx}]: {src[:80]}")
                break

        if not challenge_iframe:
            # 尝试找任何 recaptcha iframe
            for frame in all_iframes_challenge:
                src = frame.attr("src") or ""
                if "recaptcha" in src.lower():
                    challenge_iframe = frame
                    log.info(f"找到 recaptcha iframe: {src[:80]}")
                    break

        if not challenge_iframe:
            log.info("未找到挑战 iframe，假设已通过验证")
            # 检查页面是否有 "renewed" 或成功消息
            try:
                body_text = page.run_js("return document.body.innerText")
                if "renew" in body_text.lower() or "success" in body_text.lower() or "extended" in body_text.lower():
                    log.info("页面显示续期成功")
                    return True
            except Exception:
                pass
            return False

        # 进入 challenge iframe
        try:
            page.switch_to.frame(challenge_iframe)
        except Exception as e:
            log.warning(f"切换到 challenge iframe 失败: {e}")
            debug_dump(page, f"switch_fail_{attempt}")
            time.sleep(2)
            continue

        # 点击音频按钮
        audio_btn = None
        audio_selectors = [
            'css:#recaptcha-audio-button',
            'css:.rc-button-audio',
            'css:button[aria-label="Audio CAPTCHA"]',
            'xpath://button[contains(text(), "Audio")]',
        ]
        for sel in audio_selectors:
            try:
                audio_btn = page.ele(sel, timeout=3)
                if audio_btn:
                    log.info(f"找到音频按钮: {sel}")
                    break
            except Exception:
                pass

        if audio_btn:
            audio_btn.click()
            log.info("已点击音频按钮")
            time.sleep(random.uniform(3, 5))
        else:
            log.info("未找到音频按钮，可能已有图片验证码或其他类型")

        # 下载音频
        audio_link = None
        audio_link_selectors = [
            'css:.rc-audiochallenge-tdownload-link',
            'css:a[href*="audio"]',
            'xpath://a[contains(@href, "audio")]',
        ]
        for sel in audio_link_selectors:
            try:
                audio_link = page.ele(sel, timeout=3)
                if audio_link:
                    log.info(f"找到音频下载链接: {sel}")
                    break
            except Exception:
                pass

        if not audio_link:
            # 检查是否被 Google 拦截
            try:
                page_text = page.run_js("return document.body.innerText")
                if "自动查询" in page_text or "automated queries" in page_text:
                    log.error("IP 被 Google 拦截")
                    page.switch_to.main_frame()
                    debug_dump(page, f"blocked_{attempt}")
                    return False
            except Exception:
                pass

            log.warning(f"未找到音频下载链接，切换回主 frame 重试")
            try:
                page.switch_to.main_frame()
            except Exception:
                pass
            debug_dump(page, f"no_audio_link_{attempt}")
            time.sleep(2)
            continue

        # 下载音频
        audio_url = audio_link.attr("href")
        audio_file = SHOT_DIR / f"audio_{attempt}.mp3"
        try:
            resp = requests.get(audio_url, timeout=30)
            audio_file.write_bytes(resp.content)
            log.info(f"音频已下载到: {audio_file} ({resp.headers.get('content-length', '?')} bytes)")
        except Exception as e:
            log.warning(f"下载音频失败: {e}")
            try:
                page.switch_to.main_frame()
            except Exception:
                pass
            continue

        # 转换为 WAV
        wav_file = SHOT_DIR / f"audio_{attempt}.wav"
        try:
            pydub.AudioSegment.from_mp3(str(audio_file)).export(str(wav_file), format="wav")
            log.info("音频已转换为 WAV")
        except Exception as e:
            log.warning(f"WAV 转换失败: {e}")
            try:
                page.switch_to.main_frame()
            except Exception:
                pass
            continue

        # 语音识别
        try:
            recognizer = sr.Recognizer()
            with sr.AudioFile(str(wav_file)) as source:
                audio_data = recognizer.record(source)
                text = recognizer.recognize_google(audio_data, language="en-US")
            log.info(f"识别结果: {text}")
        except Exception as e:
            log.warning(f"语音识别失败: {e}")
            try:
                page.switch_to.main_frame()
            except Exception:
                pass
            continue

        # 输入答案
        try:
            input_box = page.ele('css:#audio-response', timeout=5)
            if input_box:
                input_box.input(text)
                log.info(f"已输入答案: {text}")
                time.sleep(1)

                verify_btn = page.ele('css:#recaptcha-verify-button', timeout=5)
                if verify_btn:
                    verify_btn.click()
                    log.info("已点击验证按钮")
                else:
                    # 尝试其他验证按钮
                    verify_selectors = [
                        'css:.rc-button-default',
                        'xpath://button[contains(text(), "Verify")]',
                        'xpath://button[contains(text(), "Submit")]',
                    ]
                    for vs in verify_selectors:
                        try:
                            vb = page.ele(vs, timeout=3)
                            if vb:
                                vb.click()
                                log.info(f"通过 {vs} 点击验证按钮")
                                break
                        except Exception:
                            pass
        except Exception as e:
            log.warning(f"输入验证失败: {e}")

        page.switch_to.main_frame()
        time.sleep(5)

        # 检查是否还有挑战 iframe
        try:
            remaining_iframes = page.eles('css:iframe')
            has_recaptcha = False
            for fr in remaining_iframes:
                s = fr.attr("src") or ""
                if "recaptcha" in s.lower() and "bframe" in s.lower():
                    has_recaptcha = True
                    break

            if not has_recaptcha:
                log.info("reCAPTCHA 验证通过（无剩余 challenge iframe）")
                return True
            else:
                log.info("仍有 challenge iframe，继续下一轮尝试")
        except Exception as e:
            log.warning(f"检查验证状态失败: {e}")
            return True

    # 所有尝试都失败了
    log.error("reCAPTCHA 音频识别全部失败")
    debug_dump(page, "final_fail")
    return False


def inject_cookies(page, cookie_str: str):
    """注入 Cookie"""
    if not cookie_str:
        return
    for item in cookie_str.split(";"):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            try:
                page.set.cookies({k.strip(): v.strip()})
            except Exception:
                pass


def create_proxy_auth_extension(proxy_url):
    """创建代理认证扩展"""
    import zipfile

    if "@" not in proxy_url:
        return None
    try:
        base_url = proxy_url.split("?")[0]
        scheme = base_url.split("://")[0] if "://" in base_url else "http"
        content = base_url.split("://")[1] if "://" in base_url else base_url
        auth_part, addr_part = content.split("@")
        proxy_user, proxy_pass = auth_part.split(":")
        addr_split = addr_part.split(":")
        proxy_host = addr_split[0]
        proxy_port = addr_split[1] if len(addr_split) > 1 else ("1080" if "socks" in scheme else "8080")
        scheme = "socks5" if "socks" in scheme else "http"
        log.info(f"代理解析: {scheme}://{proxy_host}:{proxy_port}")
    except Exception:
        return None

    manifest_json = json.dumps(
        {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Chrome Proxy",
            "permissions": [
                "proxy",
                "tabs",
                "unlimitedStorage",
                "storage",
                "<all_urls>",
                "webRequest",
                "webRequestBlocking",
            ],
            "background": {"scripts": ["background.js"]},
            "minimum_chrome_version": "22.0.0",
        }
    )
    background_js = """
    var config = { mode: "fixed_servers", rules: { singleProxy: { scheme: "%s", host: "%s", port: parseInt(%s) }, bypassList: ["localhost"] } };
    chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});
    chrome.webRequest.onAuthRequired.addListener(function(details) {
        return { authCredentials: { username: "%s", password: "%s" } };
    }, {urls: ["<all_urls>"]}, ['blocking']);
    """ % (scheme, proxy_host, proxy_port, proxy_user, proxy_pass)

    plugin_path = ROOT / "proxy_auth_plugin.zip"
    with zipfile.ZipFile(str(plugin_path), "w") as zp:
        zp.writestr("manifest.json", manifest_json)
        zp.writestr("background.js", background_js)
    return str(plugin_path)


def run_one(label: str, renew_url: str, cookie_str: str):
    """执行单个账号的续期"""
    from DrissionPage import ChromiumPage, ChromiumOptions

    co = ChromiumOptions()
    co.headless()
    co.set_argument("--no-sandbox")
    co.set_argument("--disable-dev-shm-usage")
    co.set_argument("--disable-gpu")
    co.set_argument("--disable-blink-features=AutomationControlled")
    co.set_argument("--disable-extensions")
    co.set_argument("--disable-background-timer-throttling")
    co.set_argument("--disable-renderer-backgrounding")
    co.set_argument("--disable-backgrounding-occluded-windows")
    co.set_user_agent(
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )

    # 代理配置
    if PROXY_URL:
        if "@" in PROXY_URL:
            plugin = create_proxy_auth_extension(PROXY_URL)
            if plugin:
                co.add_extension(plugin)
            else:
                co.set_argument(f"--proxy-server={PROXY_URL}")
        else:
            co.set_argument(f"--proxy-server={PROXY_URL}")
    elif WARP_PROXY:
        co.set_argument(f"--proxy-server={WARP_PROXY}")

    page = ChromiumPage(co)
    page.set.timeouts(PAGE_TIMEOUT)

    try:
        # 检查出口 IP
        try:
            page.get("https://api.ip.sb/ip", timeout=15)
            ip = page.run_js("return document.body.innerText").strip()
            log.info(f"当前出口 IP: {ip}")
        except Exception as e:
            log.warning(f"IP检查失败: {e}")

        log.info(f"正在访问: {renew_url}")
        page.get(renew_url)
        time.sleep(5)

        # 注入 Cookie
        if cookie_str:
            log.info("注入 Cookie...")
            inject_cookies(page, cookie_str)
            page.get(renew_url)
            time.sleep(10)

        # 获取服务器信息
        server_id, old_time, old_sec = get_server_info(page)
        log.info(f"账号: {label} | 服务器: {server_id} | 剩余: {old_time} ({old_sec}秒)")

        # 如果剩余时间足够，跳过
        if old_sec > RENEW_THRESHOLD_SECONDS:
            return {
                "label": label,
                "sid": server_id,
                "ok": True,
                "msg": f"跳过 (剩余 {old_sec // 3600}h)",
                "new": f"{old_sec // 3600}h",
            }

        # 查找续期按钮
        renew_btn = None
        for sel in ["text:Renew server", "css:button.purple", "xpath://button[contains(text(), 'Renew')]"]:
            try:
                renew_btn = page.ele(sel, timeout=10)
                if renew_btn:
                    break
            except Exception:
                pass

        if not renew_btn:
            # 尝试更多选择器
            page.get_screenshot(path=str(SHOT_DIR / f"error_{label}.png"))
            log.error("未找到续期按钮，已保存截图")
            return {"label": label, "sid": server_id, "ok": False, "msg": "未找到按钮"}

        log.info("点击续期按钮...")
        renew_btn.click()
        time.sleep(8)

        # 处理 reCAPTCHA
        captcha_passed = solve_recaptcha_audio(page)
        if captcha_passed:
            log.info("reCAPTCHA 通过，等待确认按钮出现...")
            time.sleep(5)

            # 查找确认按钮
            renew_confirm = None
            for sel in ["css:button.purple", "xpath://button[contains(text(), 'Confirm')]", "xpath://button[contains(text(), 'Yes')]"]:
                try:
                    renew_confirm = page.ele(sel, timeout=10)
                    if renew_confirm and renew_confirm.is_displayed():
                        break
                except Exception:
                    pass

            if renew_confirm:
                log.info("点击确认按钮...")
                renew_confirm.click()
                time.sleep(15)

            # 刷新页面同步状态
            log.info("刷新页面同步状态...")
            page.get(renew_url)
            time.sleep(8)

            # 检查新时间
            _, new_time, new_sec = get_server_info(page)
            log.info(f"新时间: {new_time} ({new_sec}秒), 旧时间: {old_time} ({old_sec}秒)")

            if new_sec > old_sec:
                return {
                    "label": label,
                    "sid": server_id,
                    "ok": True,
                    "old": old_time,
                    "new": new_time,
                }
            else:
                log.warning(f"时间未增加: {old_sec} -> {new_sec}")
                return {"label": label, "sid": server_id, "ok": False, "msg": f"时间未增加 ({old_sec}s -> {new_sec}s)"}
        else:
            log.warning("reCAPTCHA 未能通过")
            return {"label": label, "sid": server_id, "ok": False, "msg": "reCAPTCHA 流程未完成"}

    except Exception as e:
        log.error(f"运行异常: {e}")
        return {"label": label, "sid": "Error", "ok": False, "msg": f"异常: {e}"}
    finally:
        try:
            page.quit()
        except Exception:
            pass


def collect_accounts():
    """收集账号配置"""
    accounts = []
    multi = os.getenv("H2P_ACCOUNTS", "").strip()
    if multi:
        for line in multi.splitlines():
            parts = line.strip().split("|||")
            if len(parts) >= 3:
                accounts.append((parts[0].strip(), parts[1].strip(), parts[2].strip()))

    if not accounts and RENEW_URL and COOKIE_STR:
        accounts.append(("main", RENEW_URL, COOKIE_STR))

    return accounts


def run():
    """主运行函数"""
    accounts = collect_accounts()
    if not accounts:
        log.error("未找到任何账号配置")
        return False

    results = []
    for label, url, ck in accounts:
        log.info(f"========== 开始处理账号: {label} ==========")
        results.append(run_one(label, url, ck))
        time.sleep(random.uniform(5, 10))

    ok_count = sum(1 for r in results if r.get("ok"))
    summary = [
        "\U0001f3ae <b>host2play 续期</b>",
        f"\u23f0 {now_cn():%Y-%m-%d %H:%M:%S}",
        "",
        f"\U0001f4ca 总账号: {len(results)} | \u2705 {ok_count} | \u274c {len(results) - ok_count}",
        "",
    ]
    default_msg = "成功"
    for r in results:
        status = "\u2705" if r.get("ok") else "\u274c"
        if r.get("new"):
            summary.append(f"\U0001f464 <b>{r['label']}</b> ({r.get('sid', 'Unknown')}): {status} {r['new']}")
        else:
            summary.append(f"\U0001f464 <b>{r['label']}</b> ({r.get('sid', 'Unknown')}): {status} {r.get('msg', default_msg)}")

    tg("\n".join(summary))
    return all(r.get("ok") for r in results)


if __name__ == "__main__":
    if run():
        sys.exit(0)
    else:
        sys.exit(1)
