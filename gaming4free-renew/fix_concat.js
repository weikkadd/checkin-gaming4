const fs = require('fs');
const path = 'C:\\Users\\ASUS\\Documents\\AgnesCode\\checkin-xuqi\\gaming4free-renew\\renew.py';
let content = fs.readFileSync(path, 'utf8');
content = content.replace(/\r\n/g, '\n');

// 修复两行粘在一起的问题
content = content.replace(
    'account_finished = True res = wait_ad_flow(sb, before_secs, AD_WAIT_SEC)',
    'account_finished = True\n                    res = wait_ad_flow(sb, before_secs, AD_WAIT_SEC)'
);

// 同时修复可能存在的其他粘连
content = content.replace(
    'account_finished = True\n                    res = wait_ad_flow',
    'account_finished = True\n                    res = wait_ad_flow'
);

fs.writeFileSync(path, content, 'utf8');

// 验证修复
if (content.includes('account_finished = True res =')) {
    console.log('❌ Still has粘连');
    const idx = content.indexOf('account_finished = True res =');
    console.log('Context:', JSON.stringify(content.substring(idx - 50, idx + 200)));
} else {
    console.log('✅ 修复成功');
    // 显示修复后的上下文
    const lines = content.split('\n');
    for (let i = 0; i < lines.length; i++) {
        if (lines[i].includes('account_finished = True') && i + 1 < lines.length && lines[i+1].includes('res = wait_ad_flow')) {
            console.log((i+1)+':', lines[i].trim());
            console.log((i+2)+':', lines[i+1].trim());
        }
    }
}
