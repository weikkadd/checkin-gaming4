const fs = require('fs');
const path = 'C:\\Users\\ASUS\\Documents\\AgnesCode\\checkin-xuqi\\gaming4free-renew\\renew.py';
let content = fs.readFileSync(path, 'utf8');

// 精确替换：将 account_finished = True; break 改为 continue
const oldBlock = `                        account_finished = True
                        break`;

const newBlock = `                        # 冷却中，跳过本次续期，继续外层循环重试
                        continue`;

// 只替换冷却检测上下文中的那两处
const lines = content.split('\r\n');
const newLines = [];
let inCooldownSection = false;
let replaced = 0;

for (let i = 0; i < lines.length; i++) {
    if (lines[i].includes('续期按钮处于冷却中')) {
        inCooldownSection = true;
    }
    
    if (inCooldownSection && lines[i].trim() === 'account_finished = True') {
        // 检查下一行是否是 break
        if (i + 1 < lines.length && lines[i + 1].trim() === 'break') {
            newLines.push('                        # 冷却中，跳过本次续期，继续外层循环重试');
            newLines.push('                        continue');
            i++; // 跳过 break 行
            replaced++;
            inCooldownSection = false;
            continue;
        }
    }
    
    newLines.push(lines[i]);
}

if (replaced > 0) {
    const newContent = newLines.join('\r\n');
    fs.writeFileSync(path, newContent, 'utf8');
    console.log(`✅ Replaced ${replaced} occurrence(s) of cooldown break -> continue`);
} else {
    console.log('❌ No replacements made');
}
