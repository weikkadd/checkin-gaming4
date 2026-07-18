const fs = require('fs');
const path = 'C:\\Users\\ASUS\\Documents\\AgnesCode\\checkin-xuqi\\gaming4free-renew\\renew.py';
let content = fs.readFileSync(path, 'utf8');

const lines = content.split('\r\n');
const newLines = [];
for (let i = 0; i < lines.length; i++) {
    if (lines[i].includes('exp_match = re.search')) {
        // 匹配 "expires 20:00" 或 "expires 20h" 等 - 使用 \S+ 匹配非空白字符
        newLines.push("              exp_match = re.search(r'expires\\s+(\\d+\\S+)', page_text, re.I)");
    } else {
        newLines.push(lines[i]);
    }
}

const newContent = newLines.join('\r\n');
fs.writeFileSync(path, newContent, 'utf8');
console.log('Fixed! New line:');
const fixedLine = newLines.find(l => l.includes('exp_match = re.search'));
console.log(fixedLine);
