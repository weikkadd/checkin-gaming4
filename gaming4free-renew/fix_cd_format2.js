const fs = require('fs');
const path = 'C:\\Users\\ASUS\\Documents\\AgnesCode\\checkin-xuqi\\gaming4free-renew\\renew.py';
let content = fs.readFileSync(path, 'utf8');

// 找到 "检测到续费冷却:" 日志行后面的 return 语句
const target = "log(f\"⏳ 检测到续费冷却: {exp_text} (剩余 {remaining_sec}秒)\")\n                    return {'cooldown': True, 'remaining': remaining_sec, 'text': exp_text}";

const newCode = `log(f"⏳ 检测到续费冷却: {exp_text} (剩余 {remaining_sec}秒)")
                    return {'cooldown': True, 'remaining': remaining_sec, 'text': exp_text}
                # 匹配 "XX:XX cd" 格式 (如 "04:56 cd" 表示按钮冷却倒计时)
                cd_match = re.search(r'(\\d+):(\\d+)\\s+cd', page_text, re.I)
                if cd_match:
                    mins = int(cd_match.group(1))
                    secs = int(cd_match.group(2))
                    remaining_sec = mins * 60 + secs
                    cd_text = cd_match.group(0).strip()
                    log(f"⏳ 检测到按钮冷却倒计时: {cd_text} (剩余 {remaining_sec}秒)")
                    return {{'cooldown': True, 'remaining': remaining_sec, 'text': cd_text}}`;

const idx = content.indexOf(target);
if (idx > -1) {
    content = content.substring(0, idx) + newCode + content.substring(idx + target.length);
    fs.writeFileSync(path, content, 'utf8');
    console.log('✅ Added CD format detection after expires handling');
} else {
    console.log('❌ Could not find target string');
    // 尝试查找部分匹配
    const partialIdx = content.indexOf('检测到续费冷却');
    if (partialIdx > -1) {
        console.log('Found partial match at:', partialIdx);
        console.log('Context:', content.substring(partialIdx, partialIdx + 200));
    }
}
