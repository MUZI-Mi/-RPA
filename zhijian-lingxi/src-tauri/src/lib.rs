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
    // 打包后壳 exe 位置：<安装/分发目录>/智简灵析.exe
    let base_dir = exe.parent()?.to_path_buf();

    // 后端打包产物按如下候选位置查找（顺序匹配第一个存在的）：
    //   1) exe 同级 backend/智简灵析后端.exe   —— 推荐分发布局
    //   2) exe 同级 智简灵析后端.exe           —— 直接与壳放同一目录
    //   3) exe 同级 backend/main(.exe)         —— 旧约定（兼容）
    // 开发模式（target/debug、无后端产物）自然跳过，不会误拉起。
    let mut candidates = vec![base_dir.join("backend").join("智简灵析后端.exe")];
    if cfg!(windows) {
        candidates.push(base_dir.join("智简灵析后端.exe"));
        candidates.push(base_dir.join("backend").join("main.exe"));
    } else {
        candidates.push(base_dir.join("智简灵析后端"));
        candidates.push(base_dir.join("backend").join("main"));
    }

    let mut backend_exe = None;
    for cand in &candidates {
        if cand.exists() {
            backend_exe = Some(cand.clone());
            break;
        }
    }

    let backend_exe = match backend_exe {
        Some(path) => path,
        None => {
            eprintln!("[智简灵析] 未找到后端可执行文件，跳过启动（开发模式属正常）");
            return None;
        }
    };

    match Command::new(&backend_exe)
        .current_dir(backend_exe.parent().unwrap_or(&base_dir))
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