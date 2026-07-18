const fs = require('fs');
const path = 'C:\\Users\\ASUS\\Documents\\AgnesCode\\checkin-xuqi\\gaming4free-renew\\renew.py';
let content = fs.readFileSync(path, 'utf8');

// 将双反斜杠替换为单反斜杠（因为 Python 的 r'' 原始字符串中 \s 就是正则的 \s）
content = content.replace(/expires\\\\\\\\s/ g, 'expires\\\\s');
content = content.replace(/\\\\d\\\\+/g, '\\\\d+');
content = content.replace(/\\\\[:\\\\\\\\\\\\.hmsd\\\\]+/g, '[:\\\\.hmsd]+');

fs.writeFileSync(path, content, 'utf8');
console.log('Fixed backslashes in exp_match regex');
console.log('New line:', content.match(/exp_match = re\.search[^;]+/));
