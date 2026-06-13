# Tauri 打包（Windows + Android）

把现有 Next.js 前端([web/](../))用 [Tauri 2](https://v2.tauri.app/) 套壳，产出 **Windows 安装包**和 **Android APK**。
构建全部在 GitHub Actions 云端完成,**本地无需安装 Rust / Android SDK / NDK**。

> 架构不变:App 只是壳,所有 AI 能力仍由云端 FastAPI 后端提供。打包前请先把后端部署好
> (见根目录 [render.yaml](../../render.yaml)),拿到一个 `https://...` 地址。

---

## 一次性配置(只做一次)

仓库 **Settings → Secrets and variables → Actions → Variables** 新增:

| 名称 | 值 | 说明 |
|---|---|---|
| `NEXT_PUBLIC_API_BASE` | `https://你的后端域名` | 前端打包时写死进包里;不设则回退 `http://127.0.0.1:8000`(手机连不上) |

---

## 触发构建

二选一:

- **手动**:仓库 **Actions** 页 → 选 *Build Tauri (Windows + Android)* → **Run workflow**。
- **打 tag**:
  ```bash
  git tag v0.1.0
  git push origin v0.1.0
  ```

跑完后在该次运行底部 **Artifacts** 下载:
- `windows-installer` — `.exe`(NSIS 安装包)+ `.msi`
- `android-apk` — `app-universal-debug.apk`,手机开启"安装未知来源应用"后直接装

---

## 文件说明

| 文件 | 作用 |
|---|---|
| [tauri.conf.json](tauri.conf.json) | 应用名/标识符/窗口/打包目标;`frontendDist` 指向 Next 静态导出的 `../out` |
| [Cargo.toml](Cargo.toml) / [src/](src/) | Rust 壳(桌面 `main.rs` + 桌面&移动共享 `lib.rs`) |
| [capabilities/default.json](capabilities/default.json) | 权限:核心 API + 用系统浏览器打开外链 |
| [../app-icon.png](../app-icon.png) | **启动图标源**(1024×1024,深底+白 logo+留白)。CI 用 `tauri icon` 自动生成 Windows/Android 各尺寸 |
| [../next.config.ts](../next.config.ts) | 已设 `output: "export"`,这是 Tauri 加载静态前端的前提 |

> `target/`、`gen/`(CI 生成的 Android 工程)、`icons/`(自动生成)均已 gitignore。

---

## 品牌资源(logo / 图标)

单色 logo,跟随主题自动反相,共四个文件:

| 文件 | 用途 | 形态 |
|---|---|---|
| [../public/logo.png](../public/logo.png) | **网页/桌面 App 内**的 logo(顶栏 + 登录页) | 256×256 透明、黑色 mark;UI 里用 `invert dark:invert-0` → 浅色主题显白、深色主题显黑 |
| [../app-icon.png](../app-icon.png) | **Windows/Android 启动图标**源(`tauri icon` 的输入) | 1024×1024 深底 + 白 logo + 留白(Android 安全区) |
| [../app/icon.png](../app/icon.png) | 浏览器高清 tab 图标 | 512×512,同启动图标风格 |
| [../app/favicon.ico](../app/favicon.ico) | 浏览器 favicon | 256×256 内嵌 ICO |

> 这是 UI 内 logo(透明、可反相)与 App 启动图标(不透明、带底色,任何任务栏都看得清)的**职责分离**。

### 想整体换 logo?

给一张 **1024×1024 透明 PNG 母版**,重新生成上面四个文件即可(顶栏/登录页/启动图标/favicon 全部跟着变)。
当前这套是用 PowerShell + GDI+ 从你给的母版合成的;换 logo 时把母版发我,我重跑一遍。

---

## 之后想本地跑/出 iOS?

- **本地桌面开发**(需装 Rust + 系统 WebView):`cd web && pnpm install && pnpm tauri dev`
- **本地出 Android**:另需 JDK 17 + Android Studio(SDK/NDK),然后 `pnpm tauri android init && pnpm tauri android build`
- **iOS**:必须 macOS + Xcode + 苹果开发者账号($99/年)。本仓库暂未配置,需要时加一个 macOS 的 workflow job 跑 `pnpm tauri ios build` 即可。

---

## Android 正式发布(可选)

当前 CI 产出的是 **debug 签名** APK,装机自用没问题,但**上不了应用商店、也无法覆盖升级**。
要发布需用正式 keystore 签名:把 keystore(base64)、密码等存进仓库 Secrets,
在 workflow 的 Android job 里改用 `tauri android build --apk`(release)并配置签名。需要时再加。
