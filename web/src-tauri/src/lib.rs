// 桌面与移动端共享的运行入口。移动端由 tauri 通过 mobile_entry_point 调用。
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        // opener: 让报告里的来源链接用系统浏览器打开（而不是在 App 内跳走）。
        .plugin(tauri_plugin_opener::init())
        .setup(|_app| {
            // 系统托盘仅桌面端：托盘图标 + 右键菜单(显示/退出)，左键点击唤回窗口。
            #[cfg(desktop)]
            {
                use tauri::menu::{Menu, MenuItem};
                use tauri::tray::{TrayIconBuilder, TrayIconEvent};
                use tauri::Manager;

                let show = MenuItem::with_id(_app, "show", "显示主窗口", true, None::<&str>)?;
                let quit = MenuItem::with_id(_app, "quit", "退出", true, None::<&str>)?;
                let menu = Menu::with_items(_app, &[&show, &quit])?;
                let icon = _app.default_window_icon().unwrap().clone();

                TrayIconBuilder::new()
                    .icon(icon)
                    .tooltip("Foodsta Kitchens AI Advisor")
                    .menu(&menu)
                    .on_menu_event(|app, event| match event.id.as_ref() {
                        "show" => {
                            if let Some(w) = app.get_webview_window("main") {
                                let _ = w.show();
                                let _ = w.set_focus();
                            }
                        }
                        "quit" => app.exit(0),
                        _ => {}
                    })
                    .on_tray_icon_event(|tray, event| {
                        if let TrayIconEvent::Click { .. } = event {
                            if let Some(w) = tray.app_handle().get_webview_window("main") {
                                let _ = w.show();
                                let _ = w.set_focus();
                            }
                        }
                    })
                    .build(_app)?;
            }
            Ok(())
        })
        // 点窗口关闭按钮 → 隐藏到托盘而不是退出(像微信)。仅桌面端。
        .on_window_event(|window, event| {
            #[cfg(desktop)]
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                let _ = window.hide();
                api.prevent_close();
            }
            #[cfg(not(desktop))]
            let _ = (window, event);
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
