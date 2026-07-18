const fs = require('fs');
const path = 'C:\\Users\\ASUS\\Documents\\AgnesCode\\checkin-xuqi\\gaming4free-renew\\renew.py';
let c = fs.readFileSync(path, 'utf8');
c = c.replace(/\r\n/g, '\n');

const before = c;
c = c.split('{{e}}').join('{e}');

if (before !== c) {
    fs.writeFileSync(path, c, 'utf8');
    console.log('✅ Fixed {{e}} -> {e}');
    // Verify
    const idx = c.indexOf('检查按钮冷却失败');
    if (idx >= 0) console.log('Verified:', JSON.stringify(c.substring(idx - 5, idx + 50)));
} else {
    console.log('❌ No changes made');
}
