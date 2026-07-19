const child = require('child_process');
const result = child.execSync('cd C:\\Users\\ASUS\\Documents\\AgnesCode\\checkin-xuqi && git show HEAD:gaming4free-renew/renew.py', {encoding: 'utf8'});
const lines = result.split('\n');
console.log('Total lines:', lines.length);
console.log('Total bytes:', Buffer.byteLength(result, 'utf8'));
if (lines.length < 10) {
    console.log('FILE IS CORRUPTED IN GIT');
    console.log('Line 1 length:', lines[0].length);
} else {
    console.log('File looks OK in git');
    for (let i = 0; i < Math.min(40, lines.length); i++) {
        console.log((i+1).toString().padStart(4) + ':', lines[i].substring(0, 120));
    }
}
