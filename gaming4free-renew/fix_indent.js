const fs = require('fs');
const path = 'C:\\Users\\ASUS\\Documents\\AgnesCode\\checkin-xuqi\\gaming4free-renew\\renew.py';
let content = fs.readFileSync(path, 'utf8');

// 找到错误的缩进的 CD 检测代码并修复
// 当前：cd_match 检测在 if exp_match 块内（错误）
// 需要：cd_match 检测应该在 if exp_match 块外，作为独立的检测

const oldIncorrectBlock = `                # 匹配 "XX:XX cd" 格式 (如 "04:56 cd" 表示按钮冷却倒计时)
                cd_match = re.search(r'(\\d+):(\\d+)\\s+cd', page_text, re.I)
                if cd_match:
                    mins = int(cd_match.group(1))
                    secs = int(cd_match.group(2))
                    remaining_sec = mins * 60 + secs
                    cd_text = cd_match.group(0).strip()`;

const newCorrectBlock = `                # 匹配 "XX:XX cd" 格式 (如 "04:56 cd" 表示按钮冷却倒计时)
                cd_match = re.search(r'(\\d+):(\\d+)\\s+cd', page_text, re.I)
                if cd_match:
                    mins = int(cd_match.group(1))
                    secs = int(cd_match.group(2))
                    remaining_sec = mins * 60 + secs
                    cd_text = cd_match.group(0).strip()`;

// 实际上内容是一样的，问题在于缩进层级
// 让我找到整个 check_button_cooldown 函数并重新构建

const funcStart = content.indexOf('def check_button_cooldown(sb):');
const funcEnd = content.indexOf('def handle_turnstile(sb', funcStart);

if (funcStart === -1 || funcEnd === -1) {
    console.error('Could not find function boundaries');
    process.exit(1);
}

const correctFunction = `def check_button_cooldown(sb):
    """检查续期按钮是否处于冷却状态"""
    # === 策略1: 检查页面上的 "expires XX:XX" 冷却文本 ===
    try:
        page_text = sb.execute_script("(function(){ return document.body?document.body.innerText:''; })()")
        if page_text:
            exp_match = re.search(r'expires\\s+(\\d+\\S+)', page_text, re.I)
            if exp_match:
                exp_text = exp_match.group(0).strip()
                # 匹配 HH:MM 格式 (如 "expires 20:00" 表示 20分钟)
                hm_match = re.search(r'(\\d+):(\\d+)', exp_text)
                if hm_match:
                    hours = int(hm_match.group(1))
                    mins = int(hm_match.group(2))
                    remaining_sec = hours * 3600 + mins * 60
                    log(f"⏳ 检测到续费冷却: {exp_text} (剩余 {remaining_sec}秒 = {hours}h{mins}m)")
                    return {{'cooldown': True, 'remaining': remaining_sec, 'text': exp_text}}
                # 匹配纯数字格式 (如 "expires 5m", "expires 2h")
                num_match = re.search(r'(\\d+)', exp_text)
                if num_match:
                    val = int(num_match.group(1))
                    if 'd' in exp_text.lower():
                        remaining_sec = val * 86400
                    elif 'h' in exp_text.lower():
                        remaining_sec = val * 3600
                    elif 'm' in exp_text.lower():
                        remaining_sec = val * 60
                    else:
                        remaining_sec = val
                    log(f"⏳ 检测到续费冷却: {exp_text} (剩余 {remaining_sec}秒)")
                    return {{'cooldown': True, 'remaining': remaining_sec, 'text': exp_text}}
            # 匹配 "XX:XX cd" 格式 (如 "04:56 cd" 表示按钮冷却倒计时)
            cd_match = re.search(r'(\\d+):(\\d+)\\s+cd', page_text, re.I)
            if cd_match:
                mins = int(cd_match.group(1))
                secs = int(cd_match.group(2))
                remaining_sec = mins * 60 + secs
                cd_text = cd_match.group(0).strip()
                log(f"⏳ 检测到按钮冷却倒计时: {cd_text} (剩余 {remaining_sec}秒)")
                return {{'cooldown': True, 'remaining': remaining_sec, 'text': cd_text}}
    except Exception as e:
        log(f"⚠️ 检查 expires 冷却失败: {{e}}")
    
    # === 策略2: 检查按钮本身的 disabled 状态 ===
    js = r"""
    (function() {{
        var btns = document.querySelectorAll('button');
        for (var i = 0; i < btns.length; i++) {{
            var text = btns[i].innerText || '';
            if (text.indexOf('90') !== -1) {{
                var disabled = btns[i].disabled || btns[i].getAttribute('aria-disabled') === 'true';
                var classes = btns[i].className || '';
                var isCooldown = classes.indexOf('disabled') !== -1 || classes.indexOf('cursor-not-allowed') !== -1 || disabled;
                var waitMatch = text.match(/Wait\\s*(\\d+)/i) || text.match(/(\\d+)\\s*s/);
                if (waitMatch) return {{cooldown: true, remaining: parseInt(waitMatch[1]), text: text.trim()}};
                if (isCooldown) return {{cooldown: true, disabled: true, text: text.trim()}};
                return {{cooldown: false, text: text.trim()}};
            }}
        }}
        return null;
    }})();
    """
    try: return sb.execute_script(js)
    except Exception as e: log(f"⚠️ 检查按钮冷却失败: {{e}}"); return None`;

content = content.substring(0, funcStart) + correctFunction + content.substring(funcEnd);
fs.writeFileSync(path, content, 'utf8');
console.log('✅ Fixed check_button_cooldown function with proper indentation');
