const fs = require('fs');
const path = 'C:\\Users\\ASUS\\Documents\\AgnesCode\\checkin-xuqi\\gaming4free-renew\\renew.py';
let content = fs.readFileSync(path, 'utf8');

const oldCode = `                    screenshot(sb, "before-login")

                    # 获取当前时间
                    before_text, before_secs = get_remaining_time(sb)
                    log(f"⏱️ 续期前剩余时长: {before_text} ({before_secs}秒)")`;

const newCode = `                    screenshot(sb, "before-login")

                    # 获取当前时间 - 等待页面完全渲染
                    log("⏳ 等待页面完全渲染以获取初始时间...")
                    for _wait in range(15):
                        text, secs = get_remaining_time(sb)
                        if secs > 0:
                            before_text, before_secs = text, secs
                            log(f"⏱️ 续期前剩余时长: {before_text} ({before_secs}秒)")
                            break
                        time.sleep(1)
                    else:
                        # 超时仍未获取到时间，使用默认值
                        before_text, before_secs = "", 0
                        log(f"⏱️ 续期前剩余时长: {before_text} ({before_secs}秒) - 页面未完全渲染")`;

if (content.includes(oldCode)) {
    content = content.replace(oldCode, newCode);
    fs.writeFileSync(path, content, 'utf8');
    console.log('✅ Fixed get_remaining_time wait logic');
} else {
    console.log('oldCode not found, searching...');
    const idx = content.indexOf('screenshot(sb, "before-login")');
    if (idx > -1) {
        console.log('Found at:', idx);
        console.log('Context:', content.substring(idx, idx + 300));
    }
}
