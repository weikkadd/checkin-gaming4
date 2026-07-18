import re

with open(r'C:\Users\ASUS\Documents\AgnesCode\checkin-xuqi\gaming4free-renew\renew.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 查找冷却检测逻辑
pattern = r'续期按钮处于冷却中.*?(?=# |\n\s{20,}\S)'
match = re.search(pattern, content, re.DOTALL)

if match:
    print("=== 冷却检测逻辑 ===")
    print(match.group(0)[:500])
else:
    print("未找到冷却检测逻辑")
    # 尝试查找关键字
    if '续期按钮处于冷却中' in content:
        idx = content.index('续期按钮处于冷却中')
        print(f"找到关键字在位置 {idx}")
        print(content[max(0,idx-100):idx+300])
