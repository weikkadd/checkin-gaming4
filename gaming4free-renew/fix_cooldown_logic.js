const fs = require('fs');
const path = 'C:\\Users\\ASUS\\Documents\\AgnesCode\\checkin-xuqi\\gaming4free-renew\\renew.py';
let content = fs.readFileSync(path, 'utf8');

// 找到 check_button_cooldown 函数中处理 expires 的部分
// 需要替换从 exp_match 到 return 的整个逻辑块
const oldBlockStart = "              exp_match = re.search(r'expires\\s+(\\d+\\S+)', page_text, re.I)";
const oldBlockEnd = "                    return {'cooldown': True, 'remaining': remaining_sec, 'text': exp_text}";

const startIndex = content.indexOf(oldBlockStart);
const endIndex = content.indexOf(oldBlockEnd) + oldBlockEnd.length;

if (startIndex === -1 || endIndex === -1) {
    console.error('Could not find the block to replace');
    console.log('startIndex:', startIndex, 'endIndex:', endIndex);
    process.exit(1);
}

const newBlock = `              exp_match = re.search(r'expires\\s+(\\d+\\S+)', page_text, re.I)
            if exp_match:
                exp_text = exp_match.group(0).strip()
                # 匹配 HH:MM 格式 (如 "expires 20:00" 表示 20分钟)
                hm_match = re.search(r'(\\d+):(\\d+)', exp_text)
                if hm_match:
                    hours = int(hm_match.group(1))
                    mins = int(hm_match.group(2))
                    remaining_sec = hours * 3600 + mins * 60
                    log(f"⏳ 检测到续费冷却: {exp_text} (剩余 {remaining_sec}秒 = {hours}h{mins}m)")
                    return {{'cooldown': True, 'remaining': remaining_sec, 'text': exp_text}}
                # 匹配纯数字格式 (如 "expires 5m", "expires 2h")
                num_match = re.search(r'(\\d+)', exp_text)
                if num_match:
                    val = int(num_match.group(1))
                    if 'd' in exp_text.lower():
                        remaining_sec = val * 86400
                    elif 'h' in exp_text.lower():
                        remaining_sec = val * 3600
                    elif 'm' in exp_text.lower():
                        remaining_sec = val * 60
                    else:
                        remaining_sec = val
                    log(f"⏳ 检测到续费冷却: {exp_text} (剩余 {remaining_sec}秒)")
                    return {{'cooldown': True, 'remaining': remaining_sec, 'text': exp_text}}`;

const before = content.substring(0, startIndex);
const after = content.substring(endIndex);
const newContent = before + newBlock + after;

fs.writeFileSync(path, newContent, 'utf8');
console.log('Fixed check_button_cooldown to handle HH:MM format!');
