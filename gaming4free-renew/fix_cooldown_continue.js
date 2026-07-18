const fs = require('fs');
const path = 'C:\\Users\\ASUS\\Documents\\AgnesCode\\checkin-xuqi\\gaming4free-renew\\renew.py';
let content = fs.readFileSync(path, 'utf8');

// 找到并替换冷却检测后的逻辑
// 原逻辑：account_finished = True; break （直接退出，不再重试）
// 新逻辑：continue （跳过本次，继续外层循环重试）

const oldCoolDownLogic = `                    # 检查按钮冷却
                    cooldown_info = check_button_cooldown(sb)
                    if cooldown_info and cooldown_info.get('cooldown'):
                        rem = cooldown_info.get('remaining', '?')
                        log(f"⏳ 续期按钮处于冷却中，剩余 {rem} 秒，跳过此轮")
                        send_tg(f"⏳ 冷却中 ({rem}s)", server_name, before_text)
                        account_finished = True
                        break`;

const newCoolDownLogic = `                    # 检查按钮冷却
                    cooldown_info = check_button_cooldown(sb)
                    if cooldown_info and cooldown_info.get('cooldown'):
                        rem = cooldown_info.get('remaining', '?')
                        log(f"⏳ 续期按钮处于冷却中，剩余 {rem} 秒，跳过此轮，稍后重试")
                        send_tg(f"⏳ 冷却中 ({rem}s)", server_name, before_text)
                        # 不标记 account_finished，而是 continue 让外层循环继续重试
                        continue`;

if (content.includes(oldCoolDownLogic)) {
    content = content.replace(oldCoolDownLogic, newCoolDownLogic);
    fs.writeFileSync(path, content, 'utf8');
    console.log('✅ Fixed cooldown logic: changed break to continue');
} else {
    console.log('❌ Could not find the exact cooldown logic block');
    console.log('Searching for partial match...');
    const idx = content.indexOf('检查按钮冷却');
    if (idx > -1) {
        console.log('Found at index:', idx);
        console.log('Context:', content.substring(idx, idx + 500));
    } else {
        console.log('Not found at all');
    }
}
