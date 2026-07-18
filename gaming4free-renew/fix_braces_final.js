const fs = require('fs');
const path = 'C:\\Users\\ASUS\\Documents\\AgnesCode\\checkin-xuqi\\gaming4free-renew\\renew.py';
let content = fs.readFileSync(path, 'utf8');

// 将所有双大括号替换为单大括号（Python 不需要转义）
content = content.replace(/\{\{/g, '{').replace(/\}\}/g, '}');

fs.writeFileSync(path, content, 'utf8');
console.log('✅ Fixed double braces to single braces');

// 验证
const funcStart = content.indexOf('def check_button_cooldown');
const funcEnd = content.indexOf('def handle_turnstile', funcStart);
const func = content.substring(funcStart, funcEnd);
console.log('\n=== 验证修复后的函数 ===');
console.log(func.substring(0, 1500));
