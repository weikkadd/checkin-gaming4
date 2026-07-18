const fs = require('fs');
const path = 'C:\\Users\\ASUS\\Documents\\AgnesCode\\checkin-xuqi\\gaming4free-renew\\renew.py';
let content = fs.readFileSync(path, 'utf8');

// 找到包含 exp_match 的那一行
const lines = content.split('\r\n');
const newLines = [];
for (let i = 0; i < lines.length; i++) {
    if (lines[i].includes('exp_match = re.search')) {
        // 替换为正确的 Python 代码（r'' 中 \s 就是正则的 \s）
        newLines.push("              exp_match = re.search(r'expires\\s+(\\d+[:\\.hmsd]+)', page_text, re.I)");
    } else {
        newLines.push(lines[i]);
    }
}

const newContent = newLines.join('\r\n');
fs.writeFileSync(path, newContent, 'utf8');
console.log('Fixed! New line:');
const fixedLine = newLines.find(l => l.includes('exp_match = re.search'));
console.log(fixedLine);
