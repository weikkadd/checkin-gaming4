const fs = require('fs');
const path = 'C:\\Users\\ASUS\\Documents\\AgnesCode\\checkin-xuqi\\gaming4free-renew\\renew.py';
let content = fs.readFileSync(path, 'utf8');

// 找到 "策略2: dispatch livewire:submit 事件" 那一行
const idx = content.indexOf('# === Step 3: dispatch livewire:submit 事件 ===');
if (idx === -1) {
    console.log('Step 3 not found');
    process.exit(1);
}

// 找到这一段的结束位置（下一个 "===" 或 "# === Step 4"）
const step3End = content.indexOf('# === Step 4: 纯 JS .click() 兜底 ===');
if (step3End === -1) {
    console.log('Step 4 not found');
    process.exit(1);
}

// 找到 Step 3 的开始（往前找 "if not click_done:"）
const step3Start = content.indexOf('if not click_done:', idx - 200);
if (step3Start === -1) {
    console.log('Step 3 start not found');
    process.exit(1);
}

// 替换整个 Step 3 为更可靠的 Livewire 直接调用
const oldStep3 = content.substring(step3Start, step3End);

const newStep3 = `if not click_done:
        try:
            log("📍 策略2: 直接通过 Livewire API 调用 extend...")
            # 找到所有 Livewire 组件
            result = sb.execute_script("""
                (function() {
                    if (!window.Livewire) return 'no-lw';
                    var comps = window.Livewire.all();
                    var results = [];
                    for (var i = 0; i < comps.length; i++) {
                        try {
                            comps[i].call('extend');
                            results.push('called:' + comps[i].id);
                        } catch(e) {
                            results.push('failed:' + e.message);
                        }
                    }
                    return JSON.stringify(results);
                })();
            """)
            log(f"   🎯 Livewire extend 调用结果: {result}")
            if 'called' in str(result):
                click_done = True
                time.sleep(2)
                # 检查是否有 Livewire 请求发出
                reqs = sb.execute_script("return (window.__reqs || []).length;")
                log(f"   📡 Livewire requests captured: {reqs}")
        except Exception as e:
            log(f"   ⚠️ 策略2失败: {e}")`;

content = content.replace(oldStep3, newStep3);
fs.writeFileSync(path, content, 'utf8');
console.log('✅ Replaced Step 3 with direct Livewire extend call');
