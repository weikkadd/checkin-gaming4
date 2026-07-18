const fs = require('fs');
const path = 'C:\\Users\\ASUS\\Documents\\AgnesCode\\checkin-xuqi\\gaming4free-renew\\renew.py';
let content = fs.readFileSync(path, 'utf8');

// 修复多余的闭合大括号
content = content.replace(/return \{'cooldown': True, 'remaining': remaining_sec, 'text': exp_text\}\}/g, "return {'cooldown': True, 'remaining': remaining_sec, 'text': exp_text}");

fs.writeFileSync(path, content, 'utf8');
console.log('Fixed extra closing brace');

// 验证
const matches = content.match(/return \{'cooldown': True[^}]+\}/g);
if (matches) {
    console.log('Found', matches.length, 'correct return statements:');
    matches.forEach((m, i) => console.log(i+1 + ':', m));
} else {
    console.log('No matches found');
}
