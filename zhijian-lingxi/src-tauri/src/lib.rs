use std::process::{Child, Command};
use std::sync::Mutex;

use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    Manager,
};

// 后台 FastAPI 子进程句柄
struct BackendProcess(Mutex<Option<Child>>);

/// 启动 FastAPI 后端子进程，返回子进程句柄供退出时清理
fn start_backend() -> Option<Child> {
    let exe = std::env::current_exe().ok()?;
    // 打包后 exe 位置：<安装目录>/main.exe（或 target/release/main.exe）
    let base_dir = exe.parent()?.to_path_buf();

    // 后端打包后放在 exe 同级的 backend/main(.exe)，开发时跳过
    let backend_exe = base_dir.join("backend").join("main");
    let backend_exe = if cfg!(windows) {
        backend_exe.with_extension("exe")
    } else {
        backend_exe
    };

    if !backend_exe.exists() {
        eprintln!("[智简灵析] 后端可执行文件不存在，跳过启动: {:?}", backend_exe);
        return None;
    }

    match Command::new(&backend_exe)
        .current_dir(base_dir.join("backend"))
        .spawn()
    {
        Ok(child) => Some(child),
        Err(e) => {
            eprintln!("[智简灵析] 启动后端失败: {e}");
            None
        }
    }
}

pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .manage(BackendProcess(Mutex::new(None)))
        .setup(|app| {
            // 启动 FastAPI 后端并将句柄保存到状态中
            if let Some(child) = start_backend() {
                if let Some(state) = app.try_state::<BackendProcess>() {
                    *state.0.lock().unwrap() = Some(child);
                }
            }

            // 系统托盘
            let quit_i = MenuItem::with_id(app, "quit", "退出", true, None::<&str>)?;
            let open_i = MenuItem::with_id(app, "open", "打开主界面", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&open_i, &quit_i])?;

            let _tray = TrayIconBuilder::new()
                .menu(&menu)
                .show_menu_on_left_click(true)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "quit" => {
                        app.exit(0);
                    }
                    "open" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                    _ => {}
                })
                .build(app)?;

            Ok(())
        })
        .on_window_event(|window, event| {
            // 最小化到托盘而非退出
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                let _ = window.hide();
                api.prevent_close();
            }
        })
        .build(tauri::generate_context!())
        .expect("智简灵析启动失败");

    app.run(|app_handle, event| {
        if let tauri::RunEvent::Exit = event {
            // 退出时清理后端子进程，避免僵尸进程
            if let Some(state) = app_handle.try_state::<BackendProcess>() {
                if let Some(mut child) = state.0.lock().unwrap().take() {
                    let _ = child.kill();
                    let _ = child.wait();
                }
            }
        }
    });
}