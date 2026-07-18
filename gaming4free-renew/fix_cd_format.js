const fs = require('fs');
const path = 'C:\\Users\\ASUS\\Documents\\AgnesCode\\checkin-xuqi\\gaming4free-renew\\renew.py';
let content = fs.readFileSync(path, 'utf8');

// 在 check_button_cooldown 的策略1之后，添加策略1.5：检查 "XX:XX cd" 格式
const strategy1End = "                    log(f\"⏳ 检测到续费冷却: {exp_text} (剩余 {remaining_sec}秒)\")\n                    return {'cooldown': True, 'remaining': remaining_sec, 'text': exp_text}";

const newStrategy1_5 = `
                # 匹配 "XX:XX cd" 格式 (如 "04:56 cd" 表示按钮冷却倒计时)
                cd_match = re.search(r'(\\d+):(\\d+)\\s+cd', page_text, re.I)
                if cd_match:
                    mins = int(cd_match.group(1))
                    secs = int(cd_match.group(2))
                    remaining_sec = mins * 60 + secs
                    cd_text = cd_match.group(0).strip()
                    log(f"⏳ 检测到按钮冷却倒计时: {cd_text} (剩余 {remaining_sec}秒)")
                    return {{'cooldown': True, 'remaining': remaining_sec, 'text': cd_text}}`;

if content.contains(strategy1End):
    content = content.replace(strategy1End, strategy1End + newStrategy1_5)
    fs.writeFileSync(path, content, 'utf8')
    console.log('✅ Added CD format detection')
else:
    console.log('❌ Could not find strategy1End')
