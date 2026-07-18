const fs = require('fs');
const path = 'C:\\Users\\ASUS\\Documents\\AgnesCode\\checkin-xuqi\\gaming4free-renew\\renew.py';
let content = fs.readFileSync(path, 'utf8');

// 标准化为 \n 再替换
content = content.replace(/\r\n/g, '\n');

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
                    else:
                        before_text, before_secs = "", 0
                        log(f"⏱️ 续期前剩余时长: {before_text} ({before_secs}秒) - 页面未完全渲染")`;

if (content.includes(oldCode)) {
    content = content.replace(oldCode, newCode);
    fs.writeFileSync(path, content, 'utf8');
    console.log('✅ Fixed before_secs wait logic');
} else {
    console.log('❌ Pattern not found after normalization');
}
