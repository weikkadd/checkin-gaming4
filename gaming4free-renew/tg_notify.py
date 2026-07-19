import os, urllib.request, urllib.parse
from datetime import datetime

def send_tg(message, server_name="", time_text=""):
    from utils import log
    tg_bot_token = os.environ.get("TG_BOT_TOKEN","")
    tg_chat_id = os.environ.get("TG_CHAT_ID","")
    if not tg_bot_token or not tg_chat_id:
        return
    try:
        masked = "****"
        from config import ACCOUNTS
        if ACCOUNTS:
            email = ACCOUNTS[0][2]
            if "@" in email:
                local, domain = email.rsplit("@", 1)
                if len(local) > 3:
                    masked = local[:2] + "****" + local[-2:] + "@" + domain
                else:
                    masked = local + "****@" + domain
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = (
            f"🎮Gaming4Free Pro\n"
            f"🖥️服务器: {server_name}\n"
            f"⏰时间: {now}\n"
            f"📊状态: {message}\n"
            f"⏱剩余: {time_text}\n"
            f"⚙️模式: Renew-Pro v10"
        )
        url = f"https://api.telegram.org/bot{tg_bot_token}/sendMessage"
        data = f"chat_id={tg_chat_id}&text={urllib.parse.quote(msg)}&parse_mode=HTML".encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/x-www-form-urlencoded"})
        urllib.request.urlopen(req, timeout=10)
        log(f"📨 TG 通知成功")
    except Exception as e:
        log(f"⚠️ TG 通知失败: {e}")
