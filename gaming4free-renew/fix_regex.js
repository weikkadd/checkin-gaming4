const fs = require('fs');
const path = 'C:\\Users\\ASUS\\Documents\\AgnesCode\\checkin-xuqi\\gaming4free-renew\\renew.py';
let content = fs.readFileSync(path, 'utf8');

// 修复 check_button_cooldown 中的正则表达式
// 原正则无法匹配 "expires 20:00" 格式
const oldPattern = /exp_match = re\.search\(r'expires\\\s\+\(\\\d\+\[dhms\]\?\\\s\*\)\+', page_text, re\.I\)/;
const newCode = "exp_match = re.search(r'expires\\\\s+(\\\\d+[:hmsd]*\\\\s*)+', page_text, re.I)";

// 更简单的方法：直接替换整行
const lines = content.split('\r\n');
const newLines = [];
for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.includes("exp_match = re.search(r'expires")) {
        // 替换为支持 "expires 20:00" 格式的正则
        newLines.push("              exp_match = re.search(r'expires\\\\s+(\\\\d+[:\\\\.hmsd]+)', page_text, re.I)");
    } else {
        newLines.push(line);
    }
}

const newContent = newLines.join('\r\n');
fs.writeFileSync(path, newContent, 'utf8');
console.log('Fixed check_button_cooldown regex to match "expires 20:00" format');
