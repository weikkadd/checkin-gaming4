const fs = require('fs');
const path = 'C:\\Users\\ASUS\\Documents\\AgnesCode\\checkin-xuqi\\gaming4free-renew\\renew.py';
let content = fs.readFileSync(path, 'utf8');

// 修复双大括号问题
content = content.replace(/return \{\{'cooldown'/g, "return {'cooldown'");

fs.writeFileSync(path, content, 'utf8');
console.log('Fixed double braces');

// 验证
const idx = content.indexOf("return {'cooldown': True");
console.log('Found correct return at:', idx);
if (idx > 0) console.log('Context:', content.substring(idx-20, idx+60));
