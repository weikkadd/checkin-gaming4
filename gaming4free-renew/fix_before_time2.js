const fs = require('fs');
const path = 'C:\\Users\\ASUS\\Documents\\AgnesCode\\checkin-xuqi\\gaming4free-renew\\renew.py';
let content = fs.readFileSync(path, 'utf8');

const oldCode = '                    screenshot(sb, "before-login")\r\n\r\n                    # 获取当前时间\r\n                    before_text, before_secs = get_remaining_time(sb)\r\n                    log(f"⏱️ 续期前剩余时长: {before_text} ({before_secs}秒)")';

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

// 尝试多种换行符组合
let found = content.includes(oldCode);
if (!found) {
    // 尝试 \n 换行
    const oldCodeLF = oldCode.replace(/\r\n/g, '\n');
    found = content.includes(oldCodeLF);
    if (found) {
        content = content.replace(oldCodeLF, newCode);
        console.log('Found with LF line endings');
    }
}
if (!found) {
    // 用正则匹配
    const regex = /screenshot\(sb, "before-login"\)\s+# 获取当前时间\s+before_text, before_secs = get_remaining_time\(sb\)\s+log\(f"⏱️ 续期前剩余时长: \{before_text\} \(\{before_secs\}秒"\)/;
    if (regex.test(content)) {
        content = content.replace(regex, `screenshot(sb, "before-login")\n\n                    # 获取当前时间 - 等待页面完全渲染\n                    log("⏳ 等待页面完全渲染以获取初始时间...")\n                    for _wait in range(15):\n                        text, secs = get_remaining_time(sb)\n                        if secs > 0:\n                            before_text, before_secs = text, secs\n                            log(f"⏱️ 续期前剩余时长: {before_text} ({before_secs}秒)")\n                            break\n                    else:\n                        before_text, before_secs = "", 0\n                        log(f"⏱️ 续期前剩余时长: {before_text} ({before_secs}秒) - 页面未完全渲染")`);
        console.log('Found with regex');
        found = true;
    }
}

if (found) {
    fs.writeFileSync(path, content, 'utf8');
    console.log('✅ Fixed before_secs wait logic');
} else {
    console.log('❌ Could not find the pattern');
    // Show what we're looking for vs what's there
    const idx = content.indexOf('before-login');
    if (idx >= 0) {
        console.log('Actual content:', JSON.stringify(content.substring(idx, idx + 200)));
    }
}
