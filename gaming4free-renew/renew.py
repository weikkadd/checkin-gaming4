#!/usr/bin/env python3
"""
gaming4free 自动续期脚本 v5
- 核心: 识别并走完「看广告得时长」流程 (adLoading → adRewardReady → 必要时再点 +90 → extend)
- 核心: 按 Livewire 方法名识别真实续期调用 (轮询 $refresh 不再误报为「疑似续期请求」)
- 修复: 点击后不再立刻重载页面 (会打断广告流程); 不再乱点 Confirm/OK (会误杀广告弹窗)
- 修复: 「时间异常减少」误报 — 两次读取间的自然流逝不等于异常
- 增加: Alpine 组件状态实时观测 + 完整按钮 HTML dump + 广告元素检测
- 保留: uc_click 真实点击 / Turnstile 处理 / fetch+XHR 请求监听
"""

import os, time, random, urllib.request, urllib.parse, re
from seleniumbase import SB

# ================== 环境变量 ==================
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "").strip()
TG_TOKEN   = os.environ.get("TG_BOT_TOKEN", "").strip()
GF_COOKIE  = os.environ.get("GAME4FREE_COOKIE", "").strip()

raw_accounts = os.environ.get("GAME4FREE_ACCOUNT", "").strip().splitlines()
ACCOUNTS = []
for line in raw_accounts:
    line = line.strip()
    if not line:
        continue
    parts = line.split(",", 1)
    if len(parts) == 2:
        ACCOUNTS.append((parts[0].strip(), parts[1].strip()))

TARGET_SECONDS = 48 * 3600
ADD_SECONDS = 90 * 60
# 修复 #5: 原值 MAX_ROUNDS=10 + COOLDOWN=300s 单账号约 50 分钟, 超过 Actions 30 分钟限制
# 改为 5 轮 × 120s ≈ 10 分钟, 配合 timeout 60 分钟可稳定跑完
COOLDOWN_SEC = 120
MAX_ROUNDS = 5
# v5: 点击 +90 后等待「看广告 → 奖励就绪 → 真正续期」走完的最长时间
# (广告一般 15~30s, 留足余量; 期间页面绝对不能重载)
AD_WAIT_SEC = 100
SCREENSHOT_DIR = "/tmp/g4f-debug"

# ================== 工具函数 ==================
def now_str():
    import datetime
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def log(msg):
    print(f"{msg}", flush=True)

def screenshot(sb, name):
    try:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        path = f"{SCREENSHOT_DIR}/{name}.png"
        sb.save_screenshot(path)
        log(f"[截图] {path}")
    except:
        pass

def send_tg(result, server_name="", expiry=""):
    if not TG_TOKEN or not TG_CHAT_ID:
        return
    msg = (
        f"🎮Game4Free 续期通知\n"
        f"⏰运行时间: {now_str()}\n"
        f"🖥️服务器: {server_name}\n"
    )
    if expiry:
        msg += f"🔢剩余时间: {expiry}\n"
    msg += f"📊续期结果: {result}"
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": TG_CHAT_ID, "text": msg}).encode()
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=15):
            log("📨 TG推送成功")
    except Exception as e:
        log(f"⚠️ TG推送失败: {e}")

def parse_countdown_seconds(text):
    if not text:
        return 0
    text = text.strip()
    parts = text.split(":")
    if len(parts) == 3:
        try:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        except:
            pass
    h = re.search(r'(\d+)\s*h', text, re.I)
    m = re.search(r'(\d+)\s*m', text, re.I)
    total = 0
    if h: total += int(h.group(1)) * 3600
    if m: total += int(m.group(1)) * 60
    return total

def format_hms(seconds):
    seconds = max(0, int(seconds))
    h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

# ================== 续期逻辑 ==================
def get_remaining_time(sb):
    try:
        selectors = [
            '[class*="timer"]', '[class*="remaining"]', '[class*="countdown"]',
            '#sd-timer', '[class*="time-remaining"]', '[data-timer]',
        ]
        for sel in selectors:
            try:
                text = sb.execute_script(
                    "(function() { var el = document.querySelector('" + sel + "'); "
                    "return el ? el.textContent.trim() : ''; })();"
                )
                if text and len(text) < 30:
                    secs = parse_countdown_seconds(text)
                    if secs > 0: return text, secs
            except: continue
        page_text = sb.execute_script(
            "(function() { return document.body ? document.body.innerText : ''; })();"
        )
        if page_text:
            match = re.search(r'(\d{1,2}:\d{2}:\d{2})', page_text)
            if match: return match.group(1), parse_countdown_seconds(match.group(1))
            match = re.search(r'(\d+h\s*\d+m)', page_text, re.I)
            if match: return match.group(1), parse_countdown_seconds(match.group(1))
    except: pass
    return "", 0

def close_modals(sb):
    """关闭遮挡按钮的弹窗"""
    try:
        close_selectors = [
            'button:contains("Maybe later")',
            'button:contains("×")',
            '.modal-close',
            'button:contains("Enjoy ad-free")',
            '[aria-label="Close"]',
        ]
        for sel in close_selectors:
            try:
                is_modal = sb.execute_script(
                    "(function() { var el = document.querySelector('" + sel + "'); "
                    "if (!el) return false; var p = el.parentElement; "
                    "while(p) { if (p.className && (p.className.indexOf('modal') !== -1 "
                    "|| p.className.indexOf('dialog') !== -1 || p.tagName === 'DIALOG')) return true; "
                    "p = p.parentElement; } return false; })();"
                )
                if is_modal:
                    sb.click(sel)
                    log(f"🛡️ 已关闭弹窗: {sel}")
                    time.sleep(1)
            except: continue
    except: pass

def clear_overlays(sb):
    """点击前移除可能遮挡按钮的 modal/overlay 残留 (修复 #6)

    上一轮失败后页面常残留半透明遮罩/backdrop, 导致真实点击落在遮罩上而非按钮。
    这里只移除明确的遮罩层, 不碰功能元素。
    """
    try:
        removed = sb.execute_script("""
        (function() {
            var n = 0;
            // Tailwind/Livewire 常见遮罩: modal backdrop, fixed 全屏遮罩
            document.querySelectorAll(
                '.modal-backdrop, .modal.show, [x-show="true"][x-transition], ' +
                '.fixed.inset-0.bg-black, .v-overlay, .modal-open'
            ).forEach(function(el){
                // 只删确实是遮罩的 (无文字内容 或 全屏 fixed)
                var txt = (el.innerText || '').trim();
                var rect = el.getBoundingClientRect();
                if (txt.length === 0 || (rect.width > window.innerWidth * 0.8
                    && rect.height > window.innerHeight * 0.8)) {
                    el.remove();
                    n++;
                }
            });
            return n;
        })();
        """)
        if removed:
            log(f"🧹 清除 {removed} 个遮罩残留")
            time.sleep(0.5)
    except Exception:
        pass

def check_button_cooldown(sb):
    """检查 +90 按钮是否处于冷却"""
    cooldown_check = """
    (function() {
        var btns = document.querySelectorAll('button');
        for (var i = 0; i < btns.length; i++) {
            var text = btns[i].innerText || '';
            if (text.indexOf('90') !== -1) {
                var disabled = btns[i].disabled || btns[i].getAttribute('aria-disabled') === 'true';
                var classes = btns[i].className || '';
                var isCooldown = classes.indexOf('disabled') !== -1
                    || classes.indexOf('cursor-not-allowed') !== -1 || disabled;
                var waitMatch = text.match(/Wait\\s*(\\d+)/i) || text.match(/(\\d+)\\s*s/);
                if (waitMatch) {
                    return {cooldown: true, remaining: parseInt(waitMatch[1]), text: text.trim()};
                }
                if (isCooldown) {
                    return {cooldown: true, disabled: true, text: text.trim()};
                }
                return {cooldown: false, text: text.trim(), html: btns[i].outerHTML.substring(0, 200)};
            }
        }
        return null;
    })();
    """
    try:
        return sb.execute_script(cooldown_check)
    except:
        return None

def handle_turnstile(sb, max_retries=3):
    """处理 Cloudflare Turnstile 验证"""
    for attempt in range(max_retries):
        try:
            # 方法1: uc_gui_click_captcha (最可靠)
            cf_iframes = sb.find_elements('iframe[src*="cloudflare"]') or \
                         sb.find_elements('iframe[src*="turnstile"]') or \
                         sb.find_elements('iframe[title*="challenge"]')
            if cf_iframes:
                log(f"🛡️ 检测到 Turnstile (尝试 {attempt+1}/{max_retries})")
                screenshot(sb, f"turnstile-{attempt}")
                try:
                    sb.uc_gui_click_captcha()
                    log("✅ uc_gui_click_captcha 已执行")
                    time.sleep(5)
                    return True
                except Exception as e:
                    log(f"⚠️ uc_gui_click_captcha 失败: {e}")
                    # 方法2: 直接点击 iframe 内 checkbox
                    try:
                        sb.switch_to_frame('iframe[src*="cloudflare"]')
                        sb.click('input[type="checkbox"]')
                        sb.switch_to_default_content()
                        log("✅ 手动点击 checkbox")
                        time.sleep(5)
                        return True
                    except:
                        sb.switch_to_default_content()
        except:
            pass
        time.sleep(2)
    return False

# ================== v5: 广告流程处理 ==================
POLLING_METHODS = ('$refresh', 'refresh', 'poll', '$poll')

def read_alpine_state(sb):
    """读取 +90 按钮所属 Alpine 组件的实时状态 (adLoading/adRewardReady/extendDisabled...)"""
    js = """
    (function() {
        var btn = null;
        var all = document.querySelectorAll('button');
        for (var i = 0; i < all.length; i++) {
            if ((all[i].innerText || '').indexOf('90') !== -1) { btn = all[i]; break; }
        }
        if (!btn) return null;
        var st = {cls: btn.className || '', disabledAttr: !!btn.disabled, hasAlpine: false};
        var root = btn.closest('[x-data]') || btn;
        var d = null;
        try { if (window.Alpine && Alpine.$data) d = Alpine.$data(root); } catch(e) {}
        try { if (!d && root.__x && root.__x.$data) d = root.__x.$data; } catch(e) {}
        if (d) {
            st.hasAlpine = true;
            for (var k in d) {
                try {
                    var v = d[k];
                    var tv = typeof v;
                    if ((tv === 'boolean' || tv === 'number' || tv === 'string') && ('' + v).length < 60) {
                        st[k] = v;
                    }
                } catch(e) {}
            }
        }
        return st;
    })();
    """
    try:
        return sb.execute_script(js)
    except Exception:
        return None

def detect_ad(sb):
    """检测页面上正在展示的广告 (视频 / 广告 iframe / 含广告字样的模态)"""
    js = """
    (function() {
        var vids = document.querySelectorAll('video');
        for (var i = 0; i < vids.length; i++) {
            if (vids[i].offsetParent !== null) {
                return 'video(dur=' + (vids[i].duration || '?') + ',t=' + (vids[i].currentTime || 0).toFixed(0) + ',paused=' + vids[i].paused + ')';
            }
        }
        var ifs = document.querySelectorAll('iframe');
        for (var j = 0; j < ifs.length; j++) {
            var s = ((ifs[j].src || '') + ' ' + (ifs[j].id || '') + ' ' + (ifs[j].name || ''));
            if (/ads|doubleclick|googlesyndication|adnxs|pubmatic|reward|vast/i.test(s) && ifs[j].offsetParent !== null) {
                return 'iframe:' + (ifs[j].src || '').substring(0, 90);
            }
        }
        var modals = document.querySelectorAll('[role="dialog"], [class*="modal"], [class*="Modal"]');
        for (var k = 0; k < modals.length; k++) {
            var el = modals[k];
            if (el.offsetParent !== null) {
                var t = (el.innerText || '').replace(/\\s+/g, ' ').trim();
                if (/ad|广告|reward|watch/i.test(t) && t.length > 0 && t.length < 200) {
                    return 'modal:' + t.substring(0, 80);
                }
            }
        }
        return '';
    })();
    """
    try:
        return sb.execute_script(js) or ''
    except Exception:
        return ''

def try_ad_controls(sb, ad_elapsed):
    """广告展示中的保守操作 (只点可见且文字明确的元素):
    - 出现 Claim/领取 类按钮 → 点击领取奖励
    - 广告已展示 >20s 仍未发奖励 → 尝试关闭广告模态 (很多奖励广告要关闭后才发奖励回调)
    """
    try:
        r = sb.execute_script("""
        (function() {
            var kws = ['claim', 'collect', '领取', 'get reward', 'claim reward', '获取奖励'];
            var els = document.querySelectorAll('button, a, [role="button"]');
            for (var i = 0; i < els.length; i++) {
                var t = (els[i].innerText || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                if (t.length === 0 || t.length > 30) continue;
                if (els[i].offsetParent === null) continue;
                for (var k = 0; k < kws.length; k++) {
                    if (t.indexOf(kws[k]) !== -1) { els[i].click(); return 'claim:' + t; }
                }
            }
            return '';
        })();
        """)
        if r:
            log(f"🎁 点击广告奖励按钮: {r}")
            return
    except Exception:
        pass
    if ad_elapsed > 20:
        try:
            r2 = sb.execute_script("""
            (function() {
                var els = document.querySelectorAll('[aria-label="Close"], [aria-label="close"], button[class*="close"], [class*="modal"] button');
                for (var i = 0; i < els.length; i++) {
                    var t = (els[i].innerText || '').trim();
                    if (els[i].offsetParent === null) continue;
                    if (!(t === '×' || t === '✕' || t === 'x' || t === 'X' || t === ''
                          || /close/i.test(els[i].getAttribute('aria-label') || ''))) continue;
                    var p = els[i];
                    while (p) {
                        if (p.getAttribute && (p.getAttribute('role') === 'dialog' || /modal|dialog/i.test(p.className || ''))) {
                            els[i].click();
                            return 'closed ad modal';
                        }
                        p = p.parentElement;
                    }
                }
                return '';
            })();
            """)
            if r2:
                log(f"🧹 广告已超 20s, 尝试关闭: {r2}")
        except Exception:
            pass

def wait_ad_flow(sb, before_secs, max_wait=AD_WAIT_SEC):
    """v5 核心: 点击 +90 后等广告流程走完, 并捕获真实的续期调用。

    站点逻辑 (从按钮 Alpine 绑定反推):
      点 +90 → 浏览器端 isNativeApp=false 走广告分支 → adLoading=true 播广告
      → 广告完成 adRewardReady=true → (自动、或需再点一次 +90) 发出真正的 extend 调用
    旧版在点击后 ~15s 就重载页面, 把广告流程直接掐死 — 这是续期从不生效的根因。

    返回 dict: extend_seen / reward_ready / ad_seen / live_text / live_secs
      live_*: Livewire 不重载页面直接重渲染出的新时间 (最快的成功信号)
    """
    result = {'extend_seen': False, 'reward_ready': False, 'ad_seen': False,
              'live_text': '', 'live_secs': 0}
    log(f"🎬 进入广告等待流程 (最长 {max_wait}s, 期间不重载页面)...")
    t0 = time.time()
    clicked_again = False
    alpine_logged = 0
    ad_first_seen = None

    while time.time() - t0 < max_wait:
        elapsed = time.time() - t0

        # 1. 是否已发出真实 Livewire 调用 (按方法名, 排除轮询)
        try:
            calls = sb.execute_script(
                "(function(){ return (window.__reqs||[]).filter(function(r){"
                "return r.m==='POST' && /livewire/i.test(r.u) && (r.methods||[]).length>0;"
                "}).map(function(r){ return {methods: r.methods}; }); })();"
            ) or []
        except Exception:
            calls = []
        real_methods = []
        for c in calls:
            for m in (c.get('methods') or []):
                if m not in POLLING_METHODS and m not in real_methods:
                    real_methods.append(m)
        if real_methods:
            log(f"✅ 捕获真实 Livewire 调用: method={real_methods}")
            result['extend_seen'] = True
            screenshot(sb, "extend-call")
            time.sleep(3)  # 给页面 3s 重渲染新时间
            lt, ls = get_remaining_time(sb)
            if ls > before_secs + 60:
                log(f"🎉 页面已实时刷新时间: {lt} (无需重载)")
                result['live_text'], result['live_secs'] = lt, ls
            break

        # 2. Alpine 状态观测 (前几次打全量, 关键位变化必打)
        st = read_alpine_state(sb)
        if st:
            if alpine_logged < 5:
                keys = {k: st.get(k) for k in ('adLoading', 'adRewardReady', 'extendDisabled',
                                               'isNativeApp', 'cls', 'hasAlpine') if k in st}
                log(f"🔬 Alpine[{int(elapsed)}s]: {keys}")
                alpine_logged += 1
            if st.get('adRewardReady') is True and not result['reward_ready']:
                result['reward_ready'] = True
                log(f"🎁 [{int(elapsed)}s] adRewardReady=true — 广告奖励已就绪!")
        elif alpine_logged < 2:
            log(f"🔬 Alpine[{int(elapsed)}s]: 未取到组件状态 (按钮未找到或无 x-data)")
            alpine_logged += 1

        # 3. 广告元素检测
        ad = detect_ad(sb)
        if ad and not result['ad_seen']:
            result['ad_seen'] = True
            ad_first_seen = time.time()
            log(f"🎬 [{int(elapsed)}s] 检测到广告: {ad}")
            screenshot(sb, "ad-showing")

        # 4. 奖励就绪但没自动发 extend → 再点一次 +90
        if result['reward_ready'] and not clicked_again:
            clicked_again = True
            log("🖱️ 奖励就绪, 再次点击 +90 触发真正的续期调用...")
            try:
                sb.uc_click("button:contains('+ 90 min')", reconnect_time=4)
                log("🎯 二次点击完成")
            except Exception as e:
                log(f"⚠️ 二次点击异常: {e}")
            time.sleep(3)
            continue

        # 5. 广告控制 (领取 / 到时关闭)
        if result['ad_seen']:
            try_ad_controls(sb, time.time() - (ad_first_seen or time.time()))

        # 6. 定期看页面时间有没有自己跳变 (有的流程 extend 后直接重渲染计时器)
        if int(elapsed) % 20 < 2 and elapsed > 5:
            try:
                lt, ls = get_remaining_time(sb)
                if ls > before_secs + 60:
                    log(f"🎉 [{int(elapsed)}s] 页面时间已实时增加: {lt}")
                    result['live_text'], result['live_secs'] = lt, ls
                    result['extend_seen'] = True
                    break
            except Exception:
                pass

        time.sleep(2)

    if not result['extend_seen']:
        log(f"⏰ 广告等待 {max_wait}s 结束, 未捕获真实续期调用 "
            f"(ad_seen={result['ad_seen']}, reward_ready={result['reward_ready']})")
        screenshot(sb, "ad-flow-end")
    return result

def analyze_requests(sb):
    """v5: 按 Livewire 方法名精确分析点击后的请求 (轮询不再误报为「疑似续期」)"""
    try:
        reqs = sb.execute_script("(function() { return window.__reqs || []; })();") or []
        click_t0 = sb.execute_script("return window.__clickT0 || 0;") or 0
        if not reqs:
            log("⚠️ 点击后未记录到任何请求")
            return
        posts = [r for r in reqs if r.get('m') == 'POST']
        log(f"🌐 点击后共 {len(reqs)} 个请求, 其中 POST {len(posts)} 个")
        livewire = [r for r in posts if 'livewire' in (r.get('u') or '').lower()]
        real, polling = [], 0
        for r in livewire:
            ms = [m for m in (r.get('methods') or []) if m not in POLLING_METHODS]
            if ms:
                real.append((r, ms))
            else:
                polling += 1
        log(f"📡 Livewire POST {len(livewire)} 个: 轮询 {polling} 个, 真实动作 {len(real)} 个")
        for r, ms in real:
            delta = r.get('t', 0) - click_t0 if click_t0 else 0
            log(f"    🎯 method={ms} +{delta}ms → {r.get('u')}")
            if r.get('r'):
                log(f"       resp: {r.get('r')!r}")
        # 非 Livewire 的 POST 域名统计 (确认广告流量去向)
        try:
            from collections import Counter
            hosts = Counter()
            for r in posts:
                u = r.get('u') or ''
                if 'livewire' in u.lower() or 'gaming4free' in u.lower():
                    continue
                m2 = re.search(r'https?://([^/]+)', u)
                if m2:
                    hosts[m2.group(1)] += 1
            if hosts:
                top = ', '.join(f"{h}×{n}" for h, n in hosts.most_common(8))
                log(f"📊 其他 POST 去向: {top}")
        except Exception:
            pass
    except Exception as e:
        log(f"⚠️ 请求分析异常: {e}")

def dump_buttons(sb):
    """调试: 打印页面上所有含 '90' 的按钮的 outerHTML 和 wire:click 属性"""
    try:
        info = sb.execute_script("""
        (function() {
            var out = [];
            var all = document.querySelectorAll('button, [role="button"], a');
            for (var i = 0; i < all.length; i++) {
                var el = all[i];
                var t = (el.innerText || el.textContent || "").replace(/\\s+/g, ' ').trim();
                if (t.indexOf('90') !== -1 || /90/.test(el.getAttribute('wire:click') || '')) {
                    out.push({
                        tag: el.tagName.toLowerCase(),
                        text: t.substring(0, 60),
                        wc: el.getAttribute('wire:click') || '',
                        disabled: el.disabled || (el.getAttribute('aria-disabled') === 'true'),
                        cls: el.className || '',
                        // v5: 完整 outerHTML — 需要看清 Alpine @click 的完整表达式
                        html: el.outerHTML.substring(0, 1200)
                    });
                }
            }
            return out;
        })();
        """)
        if info:
            log(f"🔎 [调试] 含 90 的按钮共 {len(info)} 个:")
            for b in info:
                log(f"    <{b.get('tag')}> wc='{b.get('wc')}' disabled={b.get('disabled')} cls='{b.get('cls')}' text='{b.get('text')}'")
                log(f"      html: {b.get('html')}")
        else:
            log("🔎 [调试] 未找到任何含 90 的按钮")
        return info or []
    except Exception as e:
        log(f"⚠️ dump_buttons 异常: {e}")
        return []


def click_plus_90(sb):
    """点击 +90 min 按钮 — 优先按 wire:click 属性定位 (不依赖文字子串)"""
    close_modals(sb)
    # 每轮点击前清理可能遮挡的 modal/overlay 残留 (修复 #6)
    clear_overlays(sb)

    # 调试: 先 dump 出真实按钮结构 (修复 #1)
    btn_info = dump_buttons(sb)

    # 检查 cooldown
    btn_status = check_button_cooldown(sb)
    if btn_status and btn_status.get('cooldown'):
        remaining = btn_status.get('remaining', '?')
        log(f"⏳ 按钮冷却中: {btn_status.get('text','')} (剩余 {remaining}s)")
        return False
    if btn_status:
        log(f"📋 按钮状态: {btn_status.get('text','')}")

    clicked = False

    # 1. ★ 优先: 按 wire:click 属性精确定位 (修复 #1 核心)
    #    不再依赖文字子串 "90 min" (会被 span/strong 碎片/换行/图标打断)
    if not clicked:
        try:
            result = sb.execute_script("""
            (function() {
                var cands = document.querySelectorAll('[wire\\\\:click]');
                for (var i = 0; i < cands.length; i++) {
                    var wc = cands[i].getAttribute('wire:click') || '';
                    if (/90/.test(wc) && !cands[i].disabled
                        && cands[i].getAttribute('aria-disabled') !== 'true') {
                        cands[i].scrollIntoView({block: 'center', behavior: 'instant'});
                        try { cands[i].focus(); } catch(e) {}
                        try { cands[i].click(); } catch(e) {}
                        return 'wc-clicked: ' + wc + ' on <' + cands[i].tagName.toLowerCase() + '>';
                    }
                }
                return false;
            })();
            """)
            if result:
                log(f"🎯 [策略1] wire:click 定位点击: {result}")
                clicked = True
        except Exception as e:
            log(f"⚠️ [策略1] wire:click 点击异常: {e}")

    # 2. ★ 主策略: sb.uc_click (SeleniumBase UC mode 专用真实点击)
    #    ActionChains/JS合成 click 都不行:
    #    - ActionChains 用 sb.driver 直连 → UC mode reconnect 窗口期 Connection refused
    #    - JS el.click() → isTrusted=false → Alpine @click 不响应
    #    sb.uc_click 内部: setTimeout调度点击 + 断开chromedriver + 等待 + 重连
    #    → 真实可信点击(isTrusted=true) 且 绕过 reconnect 窗口期
    #    用 jQuery 风格 :contains() 选择器定位含文字的按钮 (SeleniumBase 原生支持)
    if not clicked:
        uc_selectors = [
            "button:contains('+ 90 min')",
            "button:contains('90 min')",
            "button:contains('+90')",
        ]
        for sel in uc_selectors:
            try:
                # reconnect_time=4: 点击后断开4秒再重连 (给 Turnstile/Livewire 反应时间)
                sb.uc_click(sel, reconnect_time=4)
                log(f"🎯 [策略2] uc_click 真实点击成功: {sel}")
                screenshot(sb, "after-click")
                clicked = True
                break
            except Exception as e:
                log(f"⚠️ [策略2] uc_click({sel}) 异常: {e}")
                continue

        # uc_click 失败的兜底: JS 合成 click (isTrusted=false, 最后手段)
        if not clicked:
            try:
                result = sb.execute_script("""
                (function() {
                    var all = document.querySelectorAll('button, [role="button"], a');
                    for (var i = 0; i < all.length; i++) {
                        var el = all[i];
                        var t = (el.innerText || el.textContent || "").replace(/\\s+/g, ' ').trim();
                        if (t.length <= 30 && /90/.test(t) && !el.disabled
                            && el.getAttribute('aria-disabled') !== 'true') {
                            el.scrollIntoView({block: 'center', behavior: 'instant'});
                            try { el.focus(); } catch(e) {}
                            try { el.click(); } catch(e) {}
                            return 'js-clicked: ' + t + ' on <' + el.tagName.toLowerCase() + '>';
                        }
                    }
                    return false;
                })();
                """)
                if result:
                    log(f"🚀 [策略2-兜底] JS 合成 click(): {result}")
                    clicked = True
            except Exception as e:
                log(f"⚠️ [策略2-兜底] 异常: {e}")

    # 3. 检查广告按钮 (Watch Ad 等) — 广告流程可能在前置
    if not clicked:
        log("🔍 [策略3] 检查广告按钮...")
        ad_keywords = ['Watch Ad', 'Play Ad', 'Claim Reward', 'Get Free Time', 'Earn Time']
        for kw in ad_keywords:
            try:
                ad_result = sb.execute_script(
                    '(function() { var btns = document.querySelectorAll("button, a, [role=\\"button\\"]"); '
                    'for (var i = 0; i < btns.length; i++) { var t = (btns[i].innerText || "").trim(); '
                    'if (t.toLowerCase().indexOf("' + kw.lower() + '") !== -1 && t.length < 30) { '
                    'btns[i].scrollIntoView({block: "center"}); try{btns[i].click();}catch(e){} return "ad:" + t; } } '
                    'return false; })();'
                )
                if ad_result:
                    log(f"🎬 [策略3] 广告按钮: {ad_result}")
                    time.sleep(15)
                    # 广告后再找含 90 的按钮
                    result2 = sb.execute_script(
                        '(function() { var btns = document.querySelectorAll("button, [role=\\"button\\"]"); '
                        'for (var i = 0; i < btns.length; i++) { var t = (btns[i].innerText||"").replace(/\\s+/g," ").trim(); '
                        'if (/90/.test(t) && t.length < 30 && !btns[i].disabled) { '
                        'btns[i].scrollIntoView({block:"center"}); try{btns[i].click();}catch(e){} return "clicked:"+t; } } '
                        'return false; })();'
                    )
                    if result2:
                        log(f"🚀 [策略3] 广告后点击 +90: {result2}")
                        clicked = True
                        break
            except:
                continue

    # (策略4 已合并入策略2: 真实 WebDriver 点击现在为主策略)

    if not clicked:
        log("❌ 所有点击策略失败")
        screenshot(sb, "click-fail")
        return False

    # 点击后统一处理 Turnstile
    time.sleep(2)
    screenshot(sb, "after-click")
    handle_turnstile(sb)
    time.sleep(5)
    return True

def renew_account(sb, server_name, renew_url):
    log(f"\n🎮 开始续期: {server_name}")
    parts = renew_url.rstrip('/').split('/')
    slug = None
    for part in reversed(parts):
        if part and part.lower() not in ['console', 'settings', 'server', 'servers', 'vote']:
            if len(part) >= 4:
                slug = part
                break
    if not slug:
        slug = parts[-1] if parts else ''
    console_url = f"https://control.gaming4free.net/server/{slug}/console"
    log(f"🔗 打开: {console_url}")

    # 修复 #4: reconnect 调大, 代理慢/Cloudflare 挑战时 6s 不够
    sb.uc_open_with_reconnect(console_url, reconnect_time=10)
    time.sleep(5)

    time_text, time_secs = get_remaining_time(sb)
    if time_text:
        log(f"📅 当前剩余: {time_text} ({time_secs // 3600}h {(time_secs % 3600) // 60}m)")

    if time_secs + ADD_SECONDS > TARGET_SECONDS:
        log(f"✅ 已达 48h 上限, 跳过")
        return time_text, time_secs, True

    # 检查按钮状态
    btn_status = check_button_cooldown(sb)
    if btn_status:
        log(f"📋 按钮信息: {btn_status.get('text','')} | cooldown={btn_status.get('cooldown')}")

    log("🔍 查找 +90 min 按钮...")
    # 监听网络请求: 记录点击后所有 XHR/fetch (修复 #2)
    # 注意: 必须用 sb.execute_script (非 sb.driver.execute_script) —
    # UC mode reconnect 后 sb.driver 直连会 Connection refused, sb 封装会自动重连重试
    listen_js = """
        (function() {
            window.__reqs = [];
            // 序列化各种类型的 body 为可读字符串 (Filament/Livewire 可能用 FormData/Blob)
            var serializeBody = function(body) {
                if (body == null) return '';
                if (typeof body === 'string') return body.substring(0, 150);
                if (body instanceof FormData) {
                    var parts = [];
                    body.forEach(function(v, k){ parts.push(k + '=' + (typeof v === 'string' ? v.substring(0,40) : v.name || '?')); });
                    return 'FD:' + parts.join('&');
                };
                if (body instanceof URLSearchParams) return 'USP:' + body.toString().substring(0, 150);
                if (body instanceof Blob) return 'Blob(' + body.type + ',' + body.size + ')';
                if (body instanceof ArrayBuffer) return 'AB(' + body.byteLength + ')';
                return String(body).substring(0, 60);
            };
            var record = function(method, url, bodyHint, rawBody) {
                if (!url) return;
                if (/\\.(js|css|png|jpg|jpeg|gif|svg|woff|ico)(\\?|$)/i.test(url)) return;
                if (/ipify|cloudflare|turnstile|recaptcha/i.test(url)) return;
                var entry = {m: (method||'').toUpperCase(), u: String(url).substring(0, 120), b: (bodyHint||'').substring(0,150), t: Date.now(), r: '', methods: []};
                // v5: 从完整 body 提取 Livewire 方法名 (snapshot 很长, 方法名在截断点之后, 必须用未截断的原文)
                try {
                    var raw = (typeof rawBody === 'string') ? rawBody : '';
                    if (raw.indexOf('"method"') !== -1) {
                        var mre = /"method"\\s*:\\s*"([^"\\\\]+)"/g, mm;
                        while ((mm = mre.exec(raw)) !== null) {
                            if (entry.methods.indexOf(mm[1]) === -1) entry.methods.push(mm[1]);
                        }
                    }
                } catch(e) {}
                window.__reqs.push(entry);
                return entry;
            };
            if (!window.__fetchHooked) {
                var origFetch = window.fetch;
                window.fetch = function() {
                    var url = arguments[0], opt = arguments[1] || {};
                    var entry = null;
                    try {
                        var u = (typeof url === 'string') ? url : (url && url.url) || '';
                        entry = record(opt.method || 'GET', u, serializeBody(opt.body), opt.body);
                    } catch(e) {}
                    var p = origFetch.apply(this, arguments);
                    if (entry) {
                        p.then(function(resp){
                            try {
                                var ct = resp.headers.get('content-type') || '';
                                if (ct.indexOf('json') !== -1 || ct.indexOf('text') !== -1) {
                                    resp.clone().text().then(function(txt){
                                        entry.r = txt.substring(0, 200);
                                    }).catch(function(){});
                                }
                            } catch(e) {}
                        }).catch(function(){});
                    }
                    return p;
                };
                var origOpen = XMLHttpRequest.prototype.open;
                var origSend = XMLHttpRequest.prototype.send;
                XMLHttpRequest.prototype.open = function(method, url) {
                    this.__m = method; this.__u = url;
                    return origOpen.apply(this, arguments);
                };
                XMLHttpRequest.prototype.send = function(body) {
                    var entry = null;
                    try { entry = record(this.__m, this.__u, serializeBody(body), body); } catch(e) {}
                    var xhr = this;
                    if (entry) {
                        xhr.addEventListener('load', function(){
                            try {
                                var ct = xhr.getResponseHeader('content-type') || '';
                                if (ct.indexOf('json') !== -1 || ct.indexOf('text') !== -1) {
                                    entry.r = (xhr.responseText || '').substring(0, 200);
                                }
                            } catch(e) {}
                        });
                    }
                    return origSend.apply(this, arguments);
                };
                window.__fetchHooked = true;
            }
        })();
    """
    listen_ok = False
    for attempt in range(3):
        try:
            sb.execute_script(listen_js)
            listen_ok = True
            break
        except Exception as e:
            log(f"⚠️ 监听注入第 {attempt+1}/3 次失败: {e}")
            time.sleep(2)
    if not listen_ok:
        log("⚠️ 监听注入彻底失败, 本次将无法观测请求 (点击可能仍生效)")

    # 点击前清零请求列表 + 记录基准时间 (区分 +90 请求 vs Livewire 轮询)
    try:
        sb.execute_script("window.__reqs = []; window.__clickT0 = Date.now();")
    except:
        pass

    if not click_plus_90(sb):
        screenshot(sb, f"fail_{server_name}")
        return time_text, time_secs, False

    # v5: 点击后先处理 Turnstile, 然后进入广告等待流程 — 绝不能立刻重载页面 (会掐死广告)
    time.sleep(2)
    handle_turnstile(sb)

    ad_result = wait_ad_flow(sb, time_secs, max_wait=AD_WAIT_SEC)

    # v5: 按方法名精确分析请求 (诊断日志, 能看清到底发没发 extend)
    analyze_requests(sb)

    # v5: 页面已实时刷新出更长时间 → 直接判成功, 无需重载
    if ad_result.get('live_secs', 0) > time_secs + 60:
        lt, ls = ad_result['live_text'], ad_result['live_secs']
        log(f"✅ 续期成功! {time_text} → {lt} (+{(ls - time_secs) // 60}m {(ls - time_secs) % 60}s)")
        log(f"📊 轮次结果: ✅成功 | 时间 {time_text}→{lt} (+{(ls - time_secs) // 60}m)")
        return lt, ls, True

    # 重新加载页面读取时间 (修复 #4: reconnect 调大 + 主动等计时器元素)
    try:
        sb.uc_open_with_reconnect(console_url, reconnect_time=10)
    except Exception as e:
        log(f"⚠️ 重新加载超时: {e}")
        time.sleep(5)

    # 修复 #4: 不要只 sleep 固定秒数, 主动等计时器元素出现 (最多 15s)
    timer_sels = ['[class*="timer"]', '[class*="remaining"]', '[class*="countdown"]', '#sd-timer']
    timer_ready = False
    for _ in range(15):
        for sel in timer_sels:
            try:
                txt = sb.execute_script(
                    "(function(){var el=document.querySelector('" + sel + "');"
                    "return el ? (el.textContent||'').trim() : '';})();"
                )
                if txt and len(txt) < 30 and parse_countdown_seconds(txt) > 0:
                    timer_ready = True
                    break
            except Exception:
                pass
        if timer_ready:
            break
        time.sleep(1)
    if not timer_ready:
        log("⚠️ 重载后计时器未就绪 (页面可能仍在加载/挑战)")

    new_text, new_secs = get_remaining_time(sb)

    # 修复 #3: 读不到时间时不要拿 0 去算 diff (那是假"时间异常减少")
    if not new_text:
        log(f"⚠️ 重载后读不到剩余时间文本 (旧={time_text}), 本轮判失败, 不误报")
        screenshot(sb, f"no-time-{server_name}")
        log(f"📊 轮次结果: ❌失败 | 时间 {time_text}→读不到 | 计时器就绪={timer_ready}")
        return time_text, time_secs, False

    time_diff = new_secs - time_secs

    if time_diff > 60:
        log(f"✅ 续期成功! {time_text} → {new_text} (+{time_diff//60}m {time_diff%60}s)")
        log(f"📊 轮次结果: ✅成功 | 时间 {time_text}→{new_text} (+{time_diff//60}m)")
        return new_text, new_secs, True
    elif time_diff >= -60:
        log(f"❌ 未生效! {time_text} → {new_text} (差 {time_diff}s)")
        screenshot(sb, f"no-effect-{server_name}")
        # 检查是否有错误提示
        try:
            error_text = sb.execute_script(
                '(function() { var el = document.querySelector(".alert, .error, [class*=\\"error\\"], '
                '[class*=\\"alert\\"]"); return el ? el.textContent.trim() : ""; })();'
            )
            if error_text:
                log(f"⚠️ 页面错误提示: {error_text}")
        except: pass
        log(f"📊 轮次结果: ❌未生效 | 时间 {time_text}→{new_text} (差{time_diff}s)")
        return time_text, time_secs, False
    else:
        # v5: 两次读取之间隔了「点击 + 广告等待 + 重载」, 时间自然流逝 ≠ 异常减少
        log(f"❌ 未生效 (差值≈等待期间的自然流逝): {time_text} → {new_text} (差 {time_diff}s)")
        screenshot(sb, f"time-drop-{server_name}")
        log(f"📊 轮次结果: ❌未生效 | 时间 {time_text}→{new_text} (差{time_diff}s)")
        return time_text, time_secs, False

def run_script():
    if not ACCOUNTS:
        log("❌ 未解析到任何账号")
        exit(1)

    sb_kwargs = {"uc": True, "test": True}
    if os.environ.get("IS_PROXY", "false").lower() == "true":
        proxy = os.environ.get("PROXY_URL") or os.environ.get("PROXY_SERVER")
        if proxy:
            sb_kwargs["proxy"] = proxy.strip()
            log(f"🔗 使用代理: {sb_kwargs['proxy']}")

    with SB(**sb_kwargs) as sb:
        log("🚀 浏览器就绪!")

        try:
            sb.open("https://api.ipify.org/?format=json")
            ip = sb.get_text('body')[:50]
            log(f"📍 出口IP: {ip}")
        except:
            log("⚠️ IP验证超时")

        if GF_COOKIE:
            log("🍪 注入 Cookie...")
            try:
                sb.open("https://control.gaming4free.net/")
                time.sleep(2)
                sb.execute_script(
                    '(function() { var cookieStr = ' + repr(GF_COOKIE) + '; '
                    'cookieStr.split(";").forEach(function(c) { '
                    'var parts = c.trim().split("="); '
                    'if (parts.length >= 2) { '
                    'document.cookie = parts[0].trim() + "=" + parts.slice(1).join("=") + "; path=/; domain=.gaming4free.net"; '
                    '} }); })();'
                )
                sb.open("https://control.gaming4free.net/")
                time.sleep(2)
                log("✅ Cookie 注入完成")
            except Exception as e:
                log(f"⚠️ Cookie 注入异常: {e}")

        for server_name, renew_url in ACCOUNTS:
            success_count = 0
            for r in range(MAX_ROUNDS):
                log(f"\n🔄 [{server_name}] 第 {r+1}/{MAX_ROUNDS} 轮尝试")
                try:
                    time_text, time_secs, success = renew_account(sb, server_name, renew_url)
                except Exception as e:
                    log(f"❌ 第 {r+1} 轮异常: {e}")
                    time_text, time_secs, success = "", 0, False

                if success:
                    if time_secs + ADD_SECONDS > TARGET_SECONDS:
                        send_tg("✅ 已达48h上限", server_name, time_text)
                        break
                    send_tg("✅续期成功", server_name, time_text)
                    success_count += 1
                else:
                    log(f"⚠️ 第 {r+1} 轮未成功, 继续重试")

                if r < MAX_ROUNDS - 1:
                    log(f"⏳ 等待 {COOLDOWN_SEC} 秒冷却...")
                    time.sleep(COOLDOWN_SEC)

            if success_count > 0:
                log(f"\n🎉 [{server_name}] 共续期 {success_count} 次")
            else:
                log(f"\n❌ [{server_name}] 所有轮次均未成功")

if __name__ == "__main__":
    run_script()
