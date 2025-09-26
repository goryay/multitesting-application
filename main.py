import os, sys, json, time, psutil, ctypes, shutil, threading, subprocess
from datetime import datetime
import tkinter as tk

def is_frozen() -> bool:
    return getattr(sys, "frozen", False)

def resource_path(relative_path: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(sys.executable) if is_frozen() else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, relative_path)

# --------- постоянные пути/файлы ---------
APPDIR = os.path.join(os.environ.get("LOCALAPPDATA", os.getcwd()), "TestLauncher")
os.makedirs(APPDIR, exist_ok=True)
STATE_FILE = os.path.join(APPDIR, "test_state.json")
LEGACY_STATE_FILE = os.path.join(os.path.expanduser("~"), "Desktop", "test_state.json")
LOG_FILE = os.path.join(APPDIR, "resume.log")

# ============= быстрые флаги скринера (до локера!) =============
if "--autoscreen" in sys.argv or "--screen" in sys.argv:
    try:
        try:
            import screen as screen_mod
        except Exception:
            import importlib.util
            scr_path = resource_path("screen.py")
            spec = importlib.util.spec_from_file_location("screen", scr_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore
            screen_mod = mod
        screen_mod.capture_test_windows(autoscreen="--autoscreen" in sys.argv)
    except Exception as e:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} [screen] fail: {e}\n")
        except Exception:
            pass
    sys.exit(0)

# ================= лог =================
def log_resume(msg: str):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")
    except Exception:
        pass

# ================= deps =================
def install_dependencies_if_needed():
    req = [
        r"C:\Program Files\PowerShell\7\pwsh.exe",
        r"C:\Program Files\fio\fio.exe",
        r"C:\Program Files\smartmontools\bin\smartctl.exe",
    ]
    if all(os.path.exists(p) for p in req):
        return
    script_path = resource_path("install_dependencies.ps1")
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Не найден скрипт установки: {script_path}")
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\PowerShell\7;" + env.get("PATH", "")
    subprocess.run(["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", script_path], check=True, env=env)

# =============== автозапуск (HKCU\Run) ===============
def _quoted(s: str) -> str:
    return f'"{s}"'

def _current_launcher_command_autorun() -> str:
    if is_frozen():
        return f'{_quoted(sys.executable)} --autorun'
    else:
        return f'{_quoted(sys.executable)} {_quoted(os.path.abspath(__file__))} --autorun'

def ensure_run_registry():
    try:
        import winreg
        run_key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "TestLauncher_AutoResume", 0, winreg.REG_SZ, _current_launcher_command_autorun())
        log_resume("[autostart] Run-key set OK")
    except Exception as e:
        log_resume(f"[autostart] Run-key set fail: {e}")

def remove_run_registry():
    try:
        import winreg
        run_key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key_path, 0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, "TestLauncher_AutoResume")
                log_resume("[autostart] Run-key removed")
            except OSError:
                pass
    except Exception as e:
        log_resume(f"[autostart] Run-key remove fail: {e}")

def nuke_legacy_autostart():
    try:
        subprocess.run(
            ["schtasks", "/Delete", "/TN", "TestLauncher_AutoResume", "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
        )
    except Exception:
        pass
    try:
        startup = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup")
        lnk = os.path.join(startup, "TestLauncher_AutoResume.lnk")
        if lnk and os.path.exists(lnk):
            os.remove(lnk)
    except Exception:
        pass

def diag_autostart():
    try:
        import winreg
        run_key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key_path, 0, winreg.KEY_READ) as key:
            try:
                val, _ = winreg.QueryValueEx(key, "TestLauncher_AutoResume")
                log_resume(f"[diag] Run-key exists: {val}")
            except FileNotFoundError:
                log_resume("[diag] Run-key NOT found")
    except Exception as e:
        log_resume(f"[diag] Run-key read fail: {e}")

# ============ мягкое завершение окон тестов ============
def _activate_window_by_title(title_substr: str) -> bool:
    import win32gui, win32con
    def cb(hwnd, result):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title_substr.lower() in title.lower():
                result.append(hwnd)
    hwnds = []
    win32gui.EnumWindows(cb, hwnds)
    if hwnds:
        win32gui.ShowWindow(hwnds[0], win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnds[0])
        return True
    return False

def gracefully_finish_tests():
    import pyautogui, time as _t
    fur_closed = False
    if _activate_window_by_title("FurMark"):
        _t.sleep(0.5); pyautogui.press("esc"); fur_closed = True; _t.sleep(1)
    fio_closed = False
    if _activate_window_by_title("fio"):
        _t.sleep(0.5); pyautogui.hotkey("ctrl", "c"); fio_closed = True; _t.sleep(1)
    elif _activate_window_by_title("cmd"):
        _t.sleep(0.5); pyautogui.hotkey("ctrl", "c"); fio_closed = True; _t.sleep(1)
    _t.sleep(3)
    print(f"FurMark closed: {fur_closed}, fio closed: {fio_closed}")

# ================= состояние =================
def _log_state_location():
    log_resume(f"[state] primary={STATE_FILE}")
    log_resume(f"[state] legacy={LEGACY_STATE_FILE}")

def save_state(params: dict):
    try:
        params = dict(params)
        params.setdefault("launcher_path", sys.executable if is_frozen() else sys.executable)
        params.setdefault("workdir", os.path.dirname(sys.executable) if is_frozen() else os.path.dirname(os.path.abspath(__file__)))

        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(params, f, ensure_ascii=False)
            f.flush(); os.fsync(f.fileno())

        _log_state_location()
        ensure_run_registry()
        diag_autostart()
        log_resume("[state] saved OK")
    except Exception as e:
        log_resume(f"[state] save failed: {e}")

def load_state():
    try:
        _log_state_location()
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                log_resume("[state] loaded from primary")
                return json.load(f)
        if os.path.exists(LEGACY_STATE_FILE):
            with open(LEGACY_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            try:
                with open(STATE_FILE, "w", encoding="utf-8") as w:
                    json.dump(data, w, ensure_ascii=False)
                os.remove(LEGACY_STATE_FILE)
                log_resume("[state] migrated legacy -> primary")
            except Exception as e:
                log_resume(f"[state] migrate fail: {e}")
            return data
        log_resume("[state] not found")
    except Exception as e:
        log_resume(f"[state] load failed: {e}")
    return None

def clear_state():
    try:
        for path in (STATE_FILE, LEGACY_STATE_FILE):
            try:
                if os.path.exists(path):
                    os.remove(path)
                    log_resume(f"[state] removed: {path}")
            except Exception as e:
                log_resume(f"[state] remove failed ({path}): {e}")
        remove_run_registry()
    except Exception as e:
        log_resume(f"[state] clear failed: {e}")

# ============== SINGLE INSTANCE ==============
def acquire_single_instance_lock():
    import msvcrt
    os.makedirs(APPDIR, exist_ok=True)
    lockpath = os.path.join(APPDIR, "instance.lock")
    f = open(lockpath, "w")
    try:
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        return f
    except OSError:
        return None

# ============== HEADLESS RESUME ==============
def headless_resume(state: dict):
    try:
        log_resume("[resume] start")
        install_dependencies_if_needed()
        log_resume("[resume] deps ok")
    except Exception as e:
        log_resume(f"[resume] deps error: {e}")
        return

    args = state.get("args", [])
    duration_seconds = state.get("duration_seconds", 0)

    pwsh_path = r"C:\Program Files\PowerShell\7\pwsh.exe"
    script_full_path = resource_path("aida_fio_furmark.ps1")

    # безопасно выбираем рабочую папку
    desired_workdir = state.get("workdir") or (
        os.path.dirname(sys.executable) if is_frozen()
        else os.path.dirname(os.path.abspath(__file__))
    )
    if not os.path.isdir(desired_workdir):
        log_resume(f"[resume] desired workdir missing: {desired_workdir}")
        desired_workdir = os.path.dirname(sys.executable) if is_frozen() else os.path.dirname(os.path.abspath(__file__))
        log_resume(f"[resume] fallback workdir: {desired_workdir}")
        # обновим state
        try:
            state["workdir"] = desired_workdir
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False)
        except Exception as e:
            log_resume(f"[resume] state rewrite fail: {e}")

    workdir = desired_workdir

    log_resume(f"[resume] script_full_path={script_full_path} exists={os.path.exists(script_full_path)}")
    log_resume(f"[resume] workdir={workdir} exists={os.path.isdir(workdir)}")
    if not os.path.exists(script_full_path):
        log_resume("[resume][FATAL] PS1 not found; stop")
        return

    try:
        os.chdir(workdir)
    except Exception as e:
        log_resume(f"[resume] chdir fail: {e}")

    # лог всегда в APPDIR
    os.makedirs(APPDIR, exist_ok=True)
    logfile_path = os.path.join(APPDIR, "test_launcher_log.txt")

    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\PowerShell\7;" + env.get("PATH", "")
    pwsh_args = [pwsh_path, "-ExecutionPolicy", "Bypass", "-File", script_full_path, *args]

    with open(logfile_path, "a", encoding="utf-8") as logfile:
        log_resume(f"[resume] launching: {pwsh_args}")
        try:
            test_proc = subprocess.Popen(
                pwsh_args,
                stdout=logfile, stderr=subprocess.STDOUT,
                shell=False, env=env, cwd=workdir
            )
        except FileNotFoundError as e:
            log_resume(f"[resume][FATAL] cannot start pwsh: {e}")
            return

    # <<< ВАЖНО: создаём флаг до воркера
    stop_flag = threading.Event()

    def autoscreen_worker():
        exe_path = state.get("launcher_path") or (
            sys.executable if is_frozen() else os.path.abspath("main.py")
        )
        hour = 3600
        elapsed = 0
        while not stop_flag.is_set() and elapsed < duration_seconds:
            to_sleep = min(hour, duration_seconds - elapsed)
            if to_sleep <= 0:
                break
            if stop_flag.wait(to_sleep):
                break
            try:
                subprocess.Popen([exe_path, "--autoscreen"], shell=True, cwd=workdir)
            except Exception as e:
                log_resume(f"[resume] autoscreen fail: {e}")
            elapsed += to_sleep

    threading.Thread(target=autoscreen_worker, daemon=True).start()
    log_resume("[resume] threads spawned OK")

    rc = test_proc.wait()
    log_resume(f"[resume] pwsh finished rc={rc}")

    try:
        exe_path = state.get("launcher_path") or (
            sys.executable if is_frozen() else os.path.abspath("main.py")
        )
        subprocess.run([exe_path, "--screen"], shell=True, cwd=workdir, check=False)
    except Exception as e:
        log_resume(f"[resume] final screen fail: {e}")
    finally:
        stop_flag.set()
        clear_state()
        log_resume("[resume] state cleared")

# ================= GUI =================
def run_gui():
    class TestLauncherApp:
        def __init__(self, root):
            self.root = root
            self.root.title("Меню тестирования")
            self.root.geometry("523x1350")

            self.test_choice = tk.StringVar(value="1")
            self.time_choice = tk.StringVar(value="3")
            self.custom_time = tk.StringVar(value="")
            self.gpu2_enabled = tk.BooleanVar(value=False)
            self.custom_hour = tk.IntVar(value=0)

            self.selected_disks = []
            self.checkbuttons = []
            self.check_vars = []

            self.test_proc = None
            self.stop_flag = None
            self.autoscreen_thread = None

            self.create_widgets()

        def create_widgets(self):
            tk.Label(self.root, text="=== МЕНЮ ТЕСТИРОВАНИЯ ===", font=("Arial", 12, "bold")).pack(pady=10)
            tests = [
                ("1) Только AIDA64", "1"),
                ("2) AIDA64 + FurMark", "2"),
                ("3) AIDA64 + FurMark + FIO", "3"),
                ("4) AIDA64 + FIO", "4"),
            ]
            for text, val in tests:
                tk.Radiobutton(self.root, text=text, variable=self.test_choice, value=val,
                               command=self.update_disk_checkboxes).pack(anchor="w", padx=20)

            tk.Checkbutton(self.root, text="Использовать 2 видеокарты",
                           variable=self.gpu2_enabled).pack(anchor="w", padx=20, pady=(0, 10))

            tk.Label(self.root, text="Выберите длительность теста:").pack()
            durations = [
                ("1) 10 минут", "1"),
                ("2) 30 минут", "2"),
                ("3) 1 час", "3"),
                ("4) 8 часов", "4"),
                ("5) 12 часов", "5"),
                ("6) Ввести своё значение", "6"),
            ]
            for text, val in durations:
                tk.Radiobutton(self.root, text=text, variable=self.time_choice, value=val,
                               command=self.toggle_custom).pack(anchor="w", padx=20)

            custom_time_frame = tk.Frame(self.root)
            custom_time_frame.pack()
            tk.Label(custom_time_frame, text="Часы: ").grid(row=0, column=0)
            self.custom_hour_spin = tk.Spinbox(custom_time_frame, from_=0, to=24, width=5, state="disabled",
                                               textvariable=self.custom_hour)
            self.custom_hour_spin.grid(row=0, column=1)

            self.disk_frame = tk.LabelFrame(self.root, text="Выберите диски для FIO:")
            self.disk_frame.pack(pady=10, fill="x", padx=10)
            self.populate_disks()

            tk.Button(self.root, text="Запустить тест", command=self.run_test).pack(pady=10)
            self.stop_btn = tk.Button(self.root, text="Завершить тестирование",
                                      command=self.stop_test, state="disabled")
            self.stop_btn.pack(pady=5)

            tk.Button(self.root, text="Сделать скриншот", command=self.take_screenshot).pack(pady=5)
            tk.Button(self.root, text="Создать отчёт", command=self.generate_report).pack(pady=5)
            tk.Button(self.root, text="Удалить установленные компоненты",
                      command=self.run_uninstall_script).pack(pady=5)
            tk.Button(self.root, text="Выход", command=self.root.quit).pack(pady=5)

        def toggle_custom(self):
            self.custom_hour_spin.config(state=("normal" if self.time_choice.get() == "6" else "disabled"))

        def populate_disks(self):
            for w in self.disk_frame.winfo_children():
                w.destroy()
            self.checkbuttons.clear()
            self.check_vars.clear()

            def get_drive_info(path):
                vol = ctypes.create_unicode_buffer(1024)
                fs = ctypes.create_unicode_buffer(1024)
                try:
                    ctypes.windll.kernel32.GetVolumeInformationW(
                        ctypes.c_wchar_p(path), vol, ctypes.sizeof(vol),
                        None, None, None, fs, ctypes.sizeof(fs)
                    )
                    return vol.value
                except Exception:
                    return "Без имени"

            for part in psutil.disk_partitions():
                if "cdrom" in part.opts or not os.path.exists(part.mountpoint):
                    continue
                var = tk.BooleanVar()
                dev = part.device.rstrip(":\\")
                try:
                    label = get_drive_info(part.mountpoint)
                except Exception:
                    label = "Без названия"
                try:
                    total = shutil.disk_usage(part.mountpoint).total
                    size_gb = f"{total // (1024 ** 3)} GB"
                except Exception:
                    size_gb = "?"
                cb = tk.Checkbutton(self.disk_frame, text=f"{dev}: {label}, {size_gb}", variable=var)
                cb.pack(anchor="w")
                self.checkbuttons.append(cb)
                self.check_vars.append((var, dev))
            self.update_disk_checkboxes()

        def update_disk_checkboxes(self):
            enable = self.test_choice.get() in ("3", "4")
            for cb in self.checkbuttons:
                cb.config(state=("normal" if enable else "disabled"))

        def run_test(self):
            from tkinter import messagebox
            try:
                install_dependencies_if_needed()
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось подготовить окружение:\n{e}")
                return

            test_map = {
                "1": ["AIDA"],
                "2": ["AIDA", "FURMARK"],
                "3": ["AIDA", "FURMARK", "FIO"],
                "4": ["AIDA", "FIO"],
            }
            time_map = {"1": "10", "2": "30", "3": "60", "4": "480", "5": "720"}

            args = test_map.get(self.test_choice.get(), [])
            if self.gpu2_enabled.get():
                args.append("GPU2")
            if "FIO" in args:
                self.selected_disks = [dev for var, dev in self.check_vars if var.get()]
                if not self.selected_disks:
                    messagebox.showerror("Ошибка", "Выберите хотя бы один диск для теста FIO")
                    return
                args.extend([d[0] for d in self.selected_disks])

            if self.time_choice.get() == "6":
                try:
                    minutes = int(self.custom_hour.get()) * 60
                    if minutes <= 0:
                        raise ValueError
                except Exception:
                    messagebox.showerror("Ошибка", "Введите корректное число часов (больше 0)")
                    return
                duration = str(minutes)
            else:
                duration = time_map.get(self.time_choice.get(), "60")

            args.append(duration)
            duration_seconds = int(duration) * 60

            save_state({"args": args, "duration_seconds": duration_seconds})

            pwsh_path = r"C:\Program Files\PowerShell\7\pwsh.exe"
            script_full_path = resource_path("aida_fio_furmark.ps1")
            workdir = os.path.dirname(sys.executable) if is_frozen() else os.path.dirname(os.path.abspath(__file__))
            logfile_path = os.path.join(workdir, "test_launcher_log.txt")
            env = os.environ.copy()
            env["PATH"] = r"C:\Program Files\PowerShell\7;" + env.get("PATH", "")

            try:
                with open(logfile_path, "w", encoding="utf-8") as logfile:
                    self.test_proc = subprocess.Popen(
                        [pwsh_path, "-ExecutionPolicy", "Bypass", "-File", script_full_path, *args],
                        stdout=logfile, stderr=subprocess.STDOUT,
                        shell=False, env=env, cwd=workdir
                    )
                time.sleep(45)
                self.stop_flag = threading.Event()
                self.stop_btn.config(state="normal")

                def autoscreen_worker():
                    exe_path = sys.executable if is_frozen() else os.path.abspath("main.py")
                    hour = 3600; elapsed = 0
                    while not self.stop_flag.is_set() and elapsed < duration_seconds:
                        to_sleep = min(hour, duration_seconds - elapsed)
                        if to_sleep <= 0: break
                        if self.stop_flag.wait(to_sleep): break
                        subprocess.Popen([exe_path, "--autoscreen"], shell=True, cwd=workdir)
                        elapsed += to_sleep

                self.autoscreen_thread = threading.Thread(target=autoscreen_worker, daemon=True)
                self.autoscreen_thread.start()

                def wait_and_final_screens():
                    self.test_proc.wait()
                    self.stop_flag.set()
                    self.stop_btn.config(state="disabled")
                    time.sleep(2)
                    exe_path = sys.executable if is_frozen() else os.path.abspath("main.py")
                    subprocess.run([exe_path, "--screen"], shell=True, cwd=workdir, check=False)
                    clear_state()

                threading.Thread(target=wait_and_final_screens, daemon=True).start()
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось запустить тесты:\n{e}")

        def stop_test(self):
            gracefully_finish_tests()
            if self.stop_flag:
                self.stop_flag.set()
            self.stop_btn.config(state="disabled")
            time.sleep(2)
            workdir = os.path.dirname(sys.executable) if is_frozen() else os.path.dirname(os.path.abspath(__file__))
            exe_path = sys.executable if is_frozen() else os.path.abspath("main.py")
            subprocess.run([exe_path, "--screen"], shell=True, cwd=workdir, check=False)
            clear_state()

        def run_uninstall_script(self):
            from tkinter import messagebox
            try:
                script_path = resource_path("AllUnin.ps1")
                pwsh_path = r"C:\Program Files\PowerShell\7\pwsh.exe"
                env = os.environ.copy()
                env["PATH"] = r"C:\Program Files\PowerShell\7;" + env.get("PATH", "")
                subprocess.run([pwsh_path, "-ExecutionPolicy", "Bypass", "-File", script_path],
                               check=True, env=env)
                messagebox.showinfo("Готово", "Удаление завершено.")
            except subprocess.CalledProcessError as e:
                messagebox.showerror("Ошибка", f"Сценарий удаления вернул ошибку:\n{e}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка при запуске:\n{e}")

        def take_screenshot(self):
            now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            computer_name = os.environ.get("COMPUTERNAME", "Unknown")
            base_path = os.path.join(os.path.expanduser("~"), "Desktop", "Report", computer_name)
            os.makedirs(base_path, exist_ok=True)
            import pyautogui
            img = pyautogui.screenshot()
            img.save(os.path.join(base_path, f"screenshot_{now}.png"))

        def generate_report(self):
            from tkinter import messagebox
            try:
                computer_name = os.environ.get("COMPUTERNAME", "Unknown")
                desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
                report_dir = os.path.join(desktop_path, "Report", computer_name)
                os.makedirs(report_dir, exist_ok=True)

                aida_path = resource_path(r"SoftForTest\AIDA64\AIDA64Port.exe")
                script_path = resource_path("aida_fio_furmark.ps1")
                smart_script = resource_path("smart.ps1")
                pwsh_path = r"C:\Program Files\PowerShell\7\pwsh.exe"
                env = os.environ.copy()
                env["PATH"] = r"C:\Program Files\PowerShell\7;" + env.get("PATH", "")

                ps_aida = (
                    f". '{script_path}'; "
                    f"Generate-Report -computerName '{computer_name}' "
                    f"-desktopPath '{desktop_path}' "
                    f"-aida64FullPath '{aida_path}'"
                )
                subprocess.Popen([pwsh_path, "-ExecutionPolicy", "Bypass", "-Command", ps_aida], env=env)

                try:
                    import screen as screen_mod
                    screen_mod.capture_test_windows()
                except Exception:
                    self.take_screenshot()

                smart_output = os.path.join(report_dir, f"smart_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt")
                subprocess.run([pwsh_path, "-ExecutionPolicy", "Bypass", "-File", smart_script, smart_output],
                               check=True, env=env)

                messagebox.showinfo("Успешно", f"Все отчёты и скриншоты сохранены в:\n{report_dir}")
            except subprocess.CalledProcessError as e:
                messagebox.showerror("Ошибка", f"Команда вернула ошибку:\n{e}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка при создании отчета:\n{e}")

    root = tk.Tk()
    app = TestLauncherApp(root)
    root.mainloop()

# ==================== ВХОД ====================
if __name__ == "__main__":
    nuke_legacy_autostart()
    _lock = acquire_single_instance_lock()
    if _lock is None:
        log_resume("[single] another instance is running — exit")
        sys.exit(0)

    autorun_mode = ("--autorun" in sys.argv)

    state = load_state()
    if state:
        headless_resume(state)
    else:
        if autorun_mode:
            log_resume("[autorun] no state -> silent exit")
            sys.exit(0)
        else:
            run_gui()
