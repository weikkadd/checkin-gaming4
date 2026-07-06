# gaming4free 自动续期（GHA + WARP）

> 利用 GitHub Actions + Cloudflare WARP 出口 + seleniumbase UC mode 自动续期 gaming4free 服务器。
> 因为 WARP 是 Cloudflare 自家 IP，Turnstile 几乎必过。

## 🎯 原理对比

| 方案 | 出口 IP | Turnstile 通过率 |
|---|---|---|
| VPS + playwright | 机房 IP（CF 黑名单） | ❌ 0% |
| **GHA + WARP** | CF 自家 IP | ✅ ~95% |

## 📁 文件结构

```
gaming4free-renew/
├── .github/workflows/
│   └── gaming4free.yml      # GitHub Actions 工作流
├── renew.py                 # 续期主脚本
├── requirements.txt         # Python 依赖
└── README.md                # 本文档
```

## 🚀 部署步骤

### 1. Fork / 推到自己的 GitHub 仓库

```bash
git init
git add .
git commit -m "gaming4free renew"
git branch -M main
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

### 2. 配置仓库 Secrets

进入仓库 → `Settings` → `Secrets and variables` → `Actions` → `New repository secret`：

| Secret 名 | 必填 | 说明 |
|---|---|---|
| `MC_USERNAME`   | ✅ | Minecraft 用户名 |
| `MC_PASSWORD`   | ⚠️ | 密码（如站点需要登录才填） |
| `GF_SITE_URL`   | ✅ | 续期页面完整 URL，如 `https://gaming4free.zapto.org/` |
| `GF_LOGIN_URL`  | ❌ | 独立登录页 URL，没有则留空 |
| `GF_COOKIE`     | ❌ | 备用：浏览器 F12 复制 cookie 字符串 |
| `TG_BOT_TOKEN`  | ❌ | Telegram bot token（要通知才填） |
| `TG_CHAT_ID`    | ❌ | Telegram chat id |

### 3. 手动触发首次测试

`Actions` → `gaming4free renew` → `Run workflow`

跑完后下载 `screenshots-*` artifact 看截图，确认是否成功。

### 4. 自动续期

工作流默认 `cron: "13 */2 * * *"`（每 2 小时跑一次）。
- gaming4free 上限 48 小时
- 2 小时跑一次足够保险
- 想改频率自己改 cron 表达式即可

## 🔧 调试技巧

### Q: 第一次跑没找到续期按钮？

打开 `screenshots-*.png` 看页面长啥样，然后改 `renew.py` 里的 `click_renew_button()` 选择器：

```python
candidates = [
    'button:contains("Renew")',   # ← 改成你站点的按钮文字
    'button:contains("Extend")',
    ...
]
```

### Q: 续期按钮点到了但时间没增加？

1. 看 `screenshots/fail_*.png` 是否出现 Turnstile
2. 如果有 Turnstile 但没过，把 `TURNSTILE_WAIT` 从 90 改到 180
3. 如果不是 Turnstile 是别的验证码（reCAPTCHA / hCaptcha），需要另外处理

### Q: 怎么看续期日志？

下载 `renew-log-*` artifact，里面有完整运行日志。

### Q: GHA 跑太慢？

每个 cron 触发后约 3-5 分钟才开始跑（GitHub 排队），属正常现象。如果想精确控制时间，把 cron 改成 `13 0,2,4,6,8,10,12,14,16,18,20,22 * * *`。

## ⚠️ 注意事项

1. **GitHub Actions 免费额度**：公开仓库无限，私有仓库每月 2000 分钟。本项目每次跑约 10-15 分钟，每天 12 次 ≈ 3600 分钟/月，**请用公开仓库**。
2. **WARP 注册**：每次跑都是新 WARP 实例，需要重新注册，约 5-10 秒。
3. **不要滥用**：单次运行 `MAX_CLICKS=30`，跑满 48h 会自动停。
4. **失败截图保留 7 天**：超过自动删除。

## 📞 故障排查

| 现象 | 原因 | 解决 |
|---|---|---|
| `WARP 端口 40000 不可达` | WARP 客户端没起来 | 重跑 workflow；或检查 workflow yaml 第 1 步 |
| `未找到续期按钮` | 站点结构变了 / 登录没成功 | 看 screenshot，调整选择器或登录逻辑 |
| `Turnstile 90s 未通过` | WARP IP 也偶尔被识别 | 多跑几次；或把 `TURNSTILE_WAIT` 加大 |
| `时间未增加` | 假成功 | 脚本已自带时间对比，会自动重试一次 |

## 📈 跟 VPS 方案怎么选？

- **只用 gaming4free** → 用这个 GHA 方案，免费
- **还要 host2play / katabump** → VPS 后端跑那俩（link 模式无盾），GHA 跑 gaming4free
- **两套并存也行** → VPS 面板里把 gaming4free 任务禁用，让 GHA 接管

---

## 🔌 跟 VPS 后端共存（重要）

如果你已经在 VPS 上跑了 checkin-new-panel 后端，**强烈建议把 gaming4free 任务在 VPS 面板里禁用**，让 GHA 接管 gaming4free。否则两套同时跑会冲突：

- VPS 那边因为 IP 在 CF 黑名单，每次都会失败（30 次重试就锁 1 小时）
- GHA 这边用 WARP IP 能稳定通过
- 两套并发会让 gaming4free 看到异常流量，可能临时封号

### VPS 后端禁用 gaming4free 任务的操作

#### 方法 A：通过面板 UI（推荐）

1. 打开 `https://你的面板域名/`
2. 找到 `gaming4free` 那条任务
3. 点击编辑（✏️ 图标）
4. 把 **`enabled`** 字段改成 `false`（或者直接删除该任务）
5. 保存

#### 方法 B：通过 API（命令行）

```bash
# 1. 查所有任务，找到 gaming4free 的 id
curl -s https://你的后端域名/trpc/task.getAll | python3 -m json.tool

# 2. 假设 gaming4free 任务的 id=1，禁用它
curl -X POST https://你的后端域名/trpc/task.update \
  -H "Content-Type: application/json" \
  -d '{"id":1,"data":{"enabled":false}}'
```

#### 方法 C：直接改数据库（终极方案）

```bash
mysql -h <DB_HOST> -u <DB_USER> -p <DB_NAME> -e \
  "UPDATE tasks SET enabled=0 WHERE name LIKE '%gaming4free%';"
```

### 验证禁用成功

VPS 面板里 gaming4free 那条任务的"上次运行"时间应该不再更新。GHA 这边的运行记录可以在 GitHub 仓库 → `Actions` → `gaming4free renew` 看到。

### 后续如果 GHA 出问题想回滚

1. 把 GHA workflow 的 cron 注释掉（或删 `.github/workflows/gaming4free.yml`）
2. VPS 面板里把 gaming4free 任务 `enabled` 改回 `true`
3. 重启 VPS 后端 `pm2 restart checkin-api`

---

## 📁 仓库内文件位置

如果你正在阅读本仓库的源码：

```
checkin-new-panel/
├── .github/workflows/
│   └── gaming4free.yml         # ← GHA 工作流（必须放在仓库根的 .github/workflows/）
├── gaming4free-renew/
│   ├── renew.py                # ← 续期脚本
│   ├── requirements.txt        # ← Python 依赖
│   └── README.md               # ← 本文档
├── server/                     # ← VPS 后端代码（host2play / katabump 用）
├── client/                     # ← Cloudflare Pages 前端代码
└── README.md                   # ← 项目总说明
```

> 注意：workflow yaml **必须放在仓库根目录的 `.github/workflows/`**，放在 `gaming4free-renew/.github/workflows/` 是不会触发的。本仓库已正确放置。
