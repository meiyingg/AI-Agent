// 桌面与移动端共享的运行入口。移动端由 tauri 通过 mobile_entry_point 调用。
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        // opener: 让报告里的来源链接用系统浏览器打开（而不是在 App 内跳走）。
        .plugin(tauri_plugin_opener::init())
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
