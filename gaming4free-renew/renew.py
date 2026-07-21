#!/usr/bin/env python3
"""Gaming4Free Renew Pro v21 - 实时时间监测续期策略"""
import os,sys,time,re,urllib.parse,urllib.request
from datetime import datetime
try:
    from seleniumbase import SB
except ImportError:
    print("seleniumbase not installed")
    sys.exit(1)
from cfg import *
from util import *
from cd import *
from tg import send_tg

def main():
    log("========== 开始处理服务器账号 (Pro v21) ==========")
    svrs=[]
    if RENEW_URL and COOKIE:
        nm="我的服务器"
        if "/server/" in RENEW_URL:
            sl=RENEW_URL.split("/server/")[1].split("/")[0]
            nm=f"服务器-{sl[:8]}"
        svrs.append((nm,RENEW_URL,COOKIE))
    for n,u,c in ACCOUNTS:
        svrs.append((n,u,c))
    if not svrs:
        log("❌ 未配置服务器信息"); sys.exit(1)
    for sn,su,sc in svrs:
        ok=False
        for bt in range(MAX_TRIES):
            if ok: break
            try:
                log(f"🚀 启动浏览器 (第 {bt+1}/{MAX_TRIES} 次尝试)...")
                with SB(uc=True,headless=False,browser='chrome',
                        agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36") as sb:
                    dr=sb.driver
                    dr.set_page_load_timeout(120)
                    log(f"🌐 访问页面: {su}")
                    dr.get(su)
                    log(f"📄 标题: {dr.title}")
                    if sc:
                        log("🍪 注入 Cookie...")
                        for it in sc.split(";"):
                            it=it.strip()
                            if "=" in it:
                                n,v=it.split("=",1)
                                try: dr.add_cookie({"name":n.strip(),"value":v.strip(),"domain":".gaming4free.net","path":"/","secure":True})
                                except: pass
                        dr.refresh(); time.sleep(5)
                        log("⏳ 等待页面加载...")
                        for _ in range(30):
                            try:
                                if dr.find_elements('css selector','iframe[src*="challenges.cloudflare.com"]'):
                                    log("🛡️ 检测到 Turnstile，等待通过...")
                                    time.sleep(5)
                                    continue
                                title=dr.title
                                if title and "Login" not in title and "login" not in title:
                                    log(f"✅ 页面加载完成: {title}")
                                    break
                            except: pass
                            time.sleep(2)
                    do_rounds(dr,sb,sn,sc)
                    bl,bs=get_time(dr)
                    if bs>=THRESHOLD:
                        ok=True
            except Exception as e:
                log(f"❌ 异常: {e}")
                try: scr(sb,"err")
                except: pass
                try: send_tg(f"❌ 异常: {e}",sn)
                except: pass
                break
            time.sleep(3)
        if ok:
            try: send_tg(f"✅ 已达到目标时长 {THRESHOLD//3600}h，停止续期",sn)
            except: pass
        else:
            try: send_tg(f"⚠️ 已达最大轮数 {MAX_ROUNDS}，停止续期",sn)
            except: pass

def do_rounds(dr,sb,sn,sc):
    cr=0
    while cr<MAX_ROUNDS:
        cr+=1
        log(f"\n🔄 --- 第 {cr}/{MAX_ROUNDS} 轮续期 ---")
        bl,bs=get_time(dr)
        log(f"⏱️ 当前剩余时长: {bl} ({bs}秒)")
        if bs>=THRESHOLD:
            log(f"✅ 已超过目标时长 {THRESHOLD//3600} 小时")
            try: send_tg(f"🎉 已达到目标时长 {bl}",sn,bl)
            except: pass
            return True

        ci=chk_cd(dr)
        if ci and ci.get('cooldown'):
            rem=ci.get('remaining',0)
            log(f"⏳ 检测到按钮冷却，剩余: {ci.get('text','')} (剩 {rem}秒)")
            for _ in range(rem):
                time.sleep(1)
                if (_ % 10)==0:
                    try: dr.refresh(); time.sleep(2)
                    except: pass
            dr.refresh(); time.sleep(5)
            bl,bs=get_time(dr)
            log(f"⏱️ 冷却后: {bl} ({bs}秒)")

        pre_ts=time.time()
        pre_time=bs

        try:
            # ===== 纯按钮点击策略 =====
            # 1. 找到 +90min 按钮
            btn_result=dr.execute_script("""
                var result=null;
                var allBtns=document.querySelectorAll('button,[role=button],a[class*="btn"],a[class*="Btn"]');
                for(var i=0;i<allBtns.length;i++){
                    var t=(allBtns[i].innerText||allBtns[i].textContent||'').trim();
                    if(t.indexOf('90')!==-1 && t.indexOf('min')!==-1){
                        var rect=allBtns[i].getBoundingClientRect();
                        result={
                            idx:i,
                            text:t,
                            wireClick:allBtns[i].getAttribute('wire:click'),
                            disabled:allBtns[i].disabled,
                            visible:rect.width>0&&rect.height>0,
                            tagName:allBtns[i].tagName
                        };
                        break;
                    }
                }
                if(!result){
                    var btnClasses=document.querySelectorAll('[class*="btn"]');
                    for(var i=0;i<btnClasses.length;i++){
                        var parent=btnClasses[i].tagName==='BUTTON'?btnClasses[i]:btnClasses[i].querySelector('button');
                        if(parent){
                            var t=(parent.innerText||parent.textContent||'').trim();
                            if(t.indexOf('90')!==-1 && t.indexOf('min')!==-1){
                                var rect=parent.getBoundingClientRect();
                                result={text:t,wireClick:parent.getAttribute('wire:click'),disabled:parent.disabled,visible:rect.width>0&&rect.height>0,tagName:parent.tagName};
                                break;
                            }
                        }
                    }
                }
                return result?JSON.stringify(result):'not_found';
            """)
            
            if btn_result == 'not_found':
                log("❌ 未找到 +90min 按钮!")
                scr(sb, f"fail_round{cr}_no_btn")
                time.sleep(10)
                continue
            
            import json
            try:
                bi=json.loads(btn_result)
                log(f"🔍 找到按钮: text={bi.get('text')}, wire:click={bi.get('wireClick')}, disabled={bi.get('disabled')}, visible={bi.get('visible')}")
            except:
                bi={}
                log(f"🔍 按钮信息: {btn_result[:200]}")

            if bi.get('disabled') or not bi.get('visible'):
                log(f"⚠️ 按钮不可用 (disabled={bi.get('disabled')}, visible={bi.get('visible')})")
                scr(sb, f"fail_round{cr}_btn_disabled")
                time.sleep(10)
                continue

            # 2. 滚动到按钮并点击（不用 f-string，避免 JS 对象字面量冲突）
            btn_idx=bi.get('idx',0)
            click_js = (
                "var allBtns=document.querySelectorAll('button,[role=button],a[class*=\\'btn\\'],a[class*=\\'Btn\\']);"
                "if(allBtns[" + str(btn_idx) + "]){"
                "var b=allBtns[" + str(btn_idx) + "];"
                "b.scrollIntoView({block:'center',behavior:'instant'});"
                "b.dispatchEvent(new MouseEvent('mouseover',{bubbles:true,cancelable:true}));"
                "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));"
                "b.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true}));"
                "b.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));"
                "return 'clicked';"
                "}"
                "return 'not_found';"
            )
            dr.execute_script(click_js)
            log("🖱️ 按钮点击事件已触发")

            # ===== 关键：实时监测时间变化（v14 成功的核心逻辑）=====
            log("⏳ 等待广告弹窗处理，实时监测时间...")
            ad_end=time.time()+120
            renewed=False
            while time.time()<ad_end:
                # 关闭弹窗
                try:
                    dr.execute_script("""
                        var closers=document.querySelectorAll('[aria-label="Close"],[aria-label=Close],.modal-close,.close-btn,.close,.dismiss,.overlay-close,.cf-turnstile-close,.ctf-spinner-close');
                        for(var i=0;i<closers.length;i++){
                            try{closers[i].click();}catch(e){}
                        }""")
                except: pass

                # 每 3 秒检查一次时间
                try:
                    ct,cs=get_time(dr)
                    diff=cs-pre_time
                    if diff > 300:
                        log(f"✅ 检测到时间增加 ({ct} > {bl}), 增加 {diff}秒，提前跳出")
                        renewed=True
                        break
                except: pass

                # 检查按钮是否重新可见
                btn_vis=dr.execute_script("""
                    var allBtns=document.querySelectorAll('button,[role=button],a[class*="btn"],a[class*="Btn"]');
                    for(var i=0;i<allBtns.length;i++){
                        var t=(allBtns[i].innerText||allBtns[i].textContent||'').trim();
                        if(t.indexOf('90')!==-1 && t.indexOf('min')!==-1){
                            var r=allBtns[i].getBoundingClientRect();
                            if(r.width>0 && r.height>0) return true;
                        }
                    }
                    return false;""")
                if btn_vis and not renewed:
                    log("✅ 弹窗已关闭，按钮可见")

                time.sleep(3)
            
            if not renewed:
                log("⚠️ 等待弹窗超时，继续检查最终结果...")
                scr(sb, f"fail_round{cr}_popup_timeout")

        except Exception as e:
            log(f"❌ 续期异常: {e}")
            scr(sb, f"fail_round{cr}_exception")

        # 等待 Cloudflare Turnstile 完全消失
        try:
            turnstile_end=time.time()+90
            while time.time()<turnstile_end:
                tf=dr.find_elements('css selector','iframe[src*="challenges.cloudflare.com"]')
                if not tf:
                    log("✅ Turnstile 验证通过")
                    break
                time.sleep(2)
            else:
                log("⚠️ Turnstile 等待超时")
        except: pass

        # 最终检查
        al,as_=get_time(dr)
        df=int(as_)-int(pre_time)
        elapsed=time.time()-pre_ts
        log(f"⏱️ 续期后: {al} ({as_}秒), 增加: {df}秒, 耗时: {elapsed:.0f}s")

        if df > 300:
            log(f"🎉 续期成功! +{df}s ({bl} → {al})")
            try: send_tg(f"🎉 Pro续期成功 (+{df//60}分钟)",sn,al)
            except: pass
            log(f"💤 等待5分钟再续下一轮...")
            time.sleep(300)
            dr.refresh(); time.sleep(5)
            continue
        else:
            err_text=dr.execute_script("return document.body?document.body.innerText.substring(0,500):'';")
            if err_text: log(f"⚠️ 页面内容片段: {err_text[:200]}")
            scr(sb, f"fail_round{cr}")
            log(f"❌ 续期失败，继续下一轮")
            time.sleep(10)

    return False

if __name__=="__main__":
    main()
