import os, sys, json, time, psutil, ctypes, shutil, threading, subprocess
from datetime import datetime
import tkinter as tk
from tkinter import messagebox


# НЕ ИМПОРТИРУЕМ turtle.delay — это ломает логику с переменной delay


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


def log_resume(msg: str):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")
    except Exception:
        pass


# ================= PowerShell picker =================
_PS_EXE_CACHE = None


def get_powershell_exe() -> str:
    """Возвращает рабочий PowerShell (pwsh, если он реально запускается; иначе powershell.exe).

    На части "чистых" систем pwsh.exe может падать (например, из‑за отсутствующих VC++ runtime),
    и тогда любые отчёты/скрипты отваливаются с rc=3221227010 (0xC0000602).
    """
    global _PS_EXE_CACHE
    if _PS_EXE_CACHE:
        return _PS_EXE_CACHE

    candidates = [
        r"C:\Program Files\PowerShell\7\pwsh.exe",
        "pwsh.exe",
        "powershell.exe",  # Windows PowerShell 5.1
    ]

    for exe in candidates:
        try:
            p = subprocess.run(
                [exe, "-NoProfile", "-NonInteractive", "-Command", "$PSVersionTable.PSVersion.Major"],
                capture_output=True, text=True, timeout=8, shell=False
            )
            if p.returncode == 0:
                _PS_EXE_CACHE = exe
                return exe
            # если pwsh падает, пробуем следующий кандидат
            log_resume(f"[ps] candidate '{exe}' rc={p.returncode} stderr_tail={(p.stderr or '')[-200:]}")
        except FileNotFoundError:
            continue
        except Exception as e:
            log_resume(f"[ps] candidate '{exe}' exception: {e}")

    _PS_EXE_CACHE = "powershell.exe"
    return _PS_EXE_CACHE


def with_ps_env(base_env: dict | None = None) -> dict:
    env = dict(base_env or os.environ)
    # добавим стандартный путь pwsh, если он есть — это не ломает 5.1
    env["PATH"] = r"C:\Program Files\PowerShell\7;" + env.get("PATH", "")
    return env


def calc_autoscreen_delay(duration_seconds: int) -> int:
    """
    Когда делать автоскрин:
    - <=10 минут:   за 30 секунд до конца
    - <=30 минут:   за 2 минуты до конца
    - >30 минут:    за 5 минут до конца
    """
    if duration_seconds <= 600:
        return max(duration_seconds - 120, 10)
    if duration_seconds <= 1800:
        return max(duration_seconds - 240, 60)
    return max(duration_seconds - 600, 300)


def build_screen_cmd(flag: str) -> list[str]:
    """
    Команда для запуска скринера (--screen / --autoscreen):
    - в exe:   main.exe --flag
    - в исходниках: python main.py --flag
    """
    if is_frozen():
        return [sys.executable, flag]
    else:
        return [sys.executable, os.path.abspath(__file__), flag]


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

    # Реальная папка SoftForTest должна лежать рядом с exe (dist\SoftForTest),
    # а не внутри временной _MEI... папки PyInstaller.
    workdir = os.path.dirname(sys.executable) if is_frozen() else os.path.dirname(os.path.abspath(__file__))
    # 1) При onefile PyInstaller папка лежит внутри _MEIPASS
    candidates = [
        resource_path("SoftForTest"),
        os.path.join(workdir, "SoftForTest"),
    ]
    soft_root = next((p for p in candidates if os.path.isdir(p)), "")

    if not soft_root:
        raise FileNotFoundError(
            "Папка SoftForTest не найдена рядом с main.exe.\n"
            f"Ожидалось: {soft_root}\n\n"
            "Проверь, что SoftForTest — это именно ПАПКА (распакованная), а не 'Сжатая архивная папка' (zip)."
        )

    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\PowerShell\7;" + env.get("PATH", "")

    # Запускаем установку и в случае ошибки показываем вывод скрипта
    cp = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            script_path,
            "-SoftRoot",
            soft_root,
        ],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    if cp.returncode != 0:
        out_tail = (cp.stdout or "")[-2000:]
        err_tail = (cp.stderr or "")[-2000:]
        raise RuntimeError(
            "install_dependencies.ps1 завершился с ошибкой.\n"
            f"rc={cp.returncode}\n\n"
            f"STDOUT:\n{out_tail}\n\n"
            f"STDERR:\n{err_tail}"
        )


# ================= helpers: PowerShell / reports (headless-safe) =================
def get_pwsh_exe() -> str:
    """Prefer PowerShell 7 if installed, otherwise fallback to Windows PowerShell."""
    pwsh = r"C:\Program Files\PowerShell\7\pwsh.exe"
    return pwsh if os.path.exists(pwsh) else "powershell.exe"


def _ps_env() -> dict:
    env = os.environ.copy()
    # Add PS7 folder to PATH (harmless if not installed)
    env["PATH"] = r"C:\Program Files\PowerShell\7;" + env.get("PATH", "")
    return env


def kill_processes_by_name(names: list[str]):
    """Best-effort: kill processes if they exist (no exception if not)."""
    for n in names:
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", n],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass


def generate_reports_headless(workdir: str):
    """
    Генерация отчётов БЕЗ GUI (важно для режима автоперезапуска/--autorun).
    Делает:
      1) Generate_SoftwareReport.ps1
      2) AIDA64 HTML через функцию Generate-AidaReport из aida_fio_furmark.ps1
      3) SMART (smart.ps1)
    """
    try:
        install_dependencies_if_needed()
    except Exception as e:
        log_resume(f"[headless][report] deps fail: {e}")
        return

    computer_name = os.environ.get("COMPUTERNAME", "Unknown")
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    base_dir = os.path.join(desktop_path, computer_name)
    reports_dir = os.path.join(base_dir, "Reports")
    screens_dir = os.path.join(base_dir, "Screens")
    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(screens_dir, exist_ok=True)

    # Важно: SoftForTest должен браться из ПАПКИ РЯДОМ С EXE (workdir), а не из _MEI...
    aida_exe = os.path.join(workdir, "SoftForTest", "AIDA64", "AIDA64Port.exe")

    html_report = resource_path("Generate_SoftwareReport.ps1")
    script_path = resource_path("aida_fio_furmark.ps1")
    smart_script = resource_path("smart.ps1")

    pwsh = get_pwsh_exe()
    env = _ps_env()

    log_resume(f"[headless][report] start -> {reports_dir}")
    log_resume(f"[headless][report] pwsh={pwsh}")
    log_resume(f"[headless][report] aida_exe={aida_exe} exists={os.path.exists(aida_exe)}")

    # На практике AIDA может быть ещё открыта (окно/лаунчер) и блокирует запуск отчёта.
    kill_processes_by_name([
        "AIDA64.exe",
        "AIDA64Port.exe",
        "AIDA64BusinessPortableLauncher.exe",
        "AIDA64BusinessPortable.exe",
    ])
    time.sleep(2)

    # 1) Программный отчёт
    try:
        r1 = subprocess.run(
            [
                pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", html_report,
                "-ComputerName", computer_name,
                "-OutputFolder", reports_dir,
                "-IncludeSoftware",
            ],
            capture_output=True,
            text=True,
            env=env,
            cwd=workdir,
        )
        log_resume(f"[headless][report] software rc={r1.returncode}")
        if r1.stdout:
            log_resume(f"[headless][report] software stdout tail: {r1.stdout[-800:]}")
        if r1.stderr:
            log_resume(f"[headless][report] software stderr tail: {r1.stderr[-800:]}")
        if r1.returncode != 0:
            return
    except Exception as e:
        log_resume(f"[headless][report] software exception: {e}")
        return

    # 2) AIDA64 HTML
    try:
        ps_aida = (
            f". '{script_path}'; "
            f"Generate-AidaReport -computerName '{computer_name}' "
            f"-outputFolder '{reports_dir}' "
            f"-aida64FullPath '{aida_exe}'"
        )
        r2 = subprocess.run(
            [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_aida],
            capture_output=True,
            text=True,
            env=env,
            cwd=workdir,
        )
        log_resume(f"[headless][report] aida rc={r2.returncode}")
        if r2.stdout:
            log_resume(f"[headless][report] aida stdout tail: {r2.stdout[-800:]}")
        if r2.stderr:
            log_resume(f"[headless][report] aida stderr tail: {r2.stderr[-800:]}")
        if r2.returncode != 0:
            return
    except Exception as e:
        log_resume(f"[headless][report] aida exception: {e}")
        return

    # 3) SMART
    try:
        smart_output = os.path.join(reports_dir, f"smart_{datetime.now():%Y-%m-%d_%H-%M-%S}.txt")
        r3 = subprocess.run(
            [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", smart_script, smart_output],
            capture_output=True,
            text=True,
            env=env,
            cwd=workdir,
        )
        log_resume(f"[headless][report] smart rc={r3.returncode}")
        if r3.stdout:
            log_resume(f"[headless][report] smart stdout tail: {r3.stdout[-800:]}")
        if r3.stderr:
            log_resume(f"[headless][report] smart stderr tail: {r3.stderr[-800:]}")
    except Exception as e:
        log_resume(f"[headless][report] smart exception: {e}")
        return

    log_resume("[headless][report] DONE OK")



def archive_results_headless(workdir: str):
    """Создать ZIP-архив папки Desktop\\<COMPUTERNAME> без GUI."""
    try:
        computer_name = os.environ.get("COMPUTERNAME", "Unknown")
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        base_dir = os.path.join(desktop, computer_name)

        if not os.path.isdir(base_dir):
            log_resume(f"[headless][archive] base_dir not found: {base_dir}")
            return

        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        archive_base = os.path.join(desktop, f"{computer_name}_{ts}")
        log_resume(f"[headless][archive] start -> {archive_base}.zip")

        shutil.make_archive(archive_base, "zip", root_dir=desktop, base_dir=computer_name)

        log_resume(f"[headless][archive] DONE OK: {archive_base}.zip")
    except Exception as e:
        log_resume(f"[headless][archive] fail: {e}")


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
        _t.sleep(0.5)
        pyautogui.press("esc")
        fur_closed = True
        _t.sleep(1)

    fio_closed = False
    if _activate_window_by_title("fio"):
        _t.sleep(0.5)
        pyautogui.hotkey("ctrl", "c")
        fio_closed = True
        _t.sleep(1)
    elif _activate_window_by_title("cmd"):
        _t.sleep(0.5)
        pyautogui.hotkey("ctrl", "c")
        fio_closed = True
        _t.sleep(1)

    _t.sleep(3)
    print(f"FurMark closed: {fur_closed}, fio closed: {fio_closed}")


# ================= состояние =================
def _log_state_location():
    log_resume(f"[state] primary={STATE_FILE}")
    log_resume(f"[state] legacy={LEGACY_STATE_FILE}")


def save_state(params: dict):
    try:
        params = dict(params)
        params.setdefault("launcher_path", sys.executable)
        params.setdefault(
            "workdir",
            os.path.dirname(sys.executable) if is_frozen() else os.path.dirname(os.path.abspath(__file__))
        )

        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(params, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

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
        print(f"[DEBUG] Запуск headless_resume")
        print(f"[DEBUG] Состояние: {state}")

        install_dependencies_if_needed()
        log_resume("[resume] deps ok")
    except Exception as e:
        log_resume(f"[resume] deps error: {e}")
        return

    args = state.get("args", [])
    duration_seconds = int(state.get("duration_seconds", 0))

    print(f"[DEBUG] Длительность теста: {duration_seconds} секунд ({duration_seconds / 60:.1f} минут)")
    print(f"[DEBUG] Аргументы: {args}")
    log_resume(f"[resume] duration_seconds: {duration_seconds}")
    log_resume(f"[resume] args: {args}")

    pwsh_path = get_powershell_exe()
    script_full_path = resource_path("aida_fio_furmark.ps1")

    desired_workdir = state.get("workdir") or (
        os.path.dirname(sys.executable) if is_frozen()
        else os.path.dirname(os.path.abspath(__file__))
    )
    if not os.path.isdir(desired_workdir):
        log_resume(f"[resume] desired workdir missing: {desired_workdir}")
        desired_workdir = os.path.dirname(sys.executable) if is_frozen() else os.path.dirname(os.path.abspath(__file__))
        log_resume(f"[resume] fallback workdir: {desired_workdir}")
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

    stop_flag = threading.Event()

    # ✅ ВАЖНО: раньше delay не был определён → поток автоскрина падал
    delay = calc_autoscreen_delay(duration_seconds)
    log_resume(f"[autoscreen] computed delay={delay}s for duration={duration_seconds}s")

    def autoscreen_worker():
        """Один автоскрин за N секунд до конца теста"""
        try:
            log_resume(f"[autoscreen] START: duration={duration_seconds}, delay={delay}")

            if stop_flag.wait(delay):
                log_resume("[autoscreen] CANCELLED by stop_flag")
                return

            cmd = build_screen_cmd("--autoscreen")
            log_resume(f"[autoscreen] EXECUTING: {cmd}")

            max_retries = 2
            for retry in range(max_retries):
                try:
                    result = subprocess.run(
                        cmd,
                        shell=False,
                        cwd=workdir,
                        timeout=30,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="ignore"
                    )
                    log_resume(f"[autoscreen] COMPLETE (attempt {retry + 1}): rc={result.returncode}")

                    if result.stdout:
                        log_resume(f"[autoscreen] stdout tail: {result.stdout[-500:]}")
                    if result.stderr:
                        log_resume(f"[autoscreen] stderr tail: {result.stderr[-500:]}")

                    break
                except subprocess.TimeoutExpired:
                    log_resume(f"[autoscreen] TIMEOUT on attempt {retry + 1}")
                except Exception as e:
                    log_resume(f"[autoscreen] ERROR on attempt {retry + 1}: {e}")

        except Exception as e:
            log_resume(f"[autoscreen] CRITICAL ERROR: {e}")
            import traceback
            log_resume(traceback.format_exc())

    threading.Thread(target=autoscreen_worker, daemon=True).start()
    log_resume("[resume] autoscreen thread spawned")

    rc = test_proc.wait()
    log_resume(f"[resume] pwsh finished rc={rc}")

    # ===== ФИНАЛЬНЫЕ СКРИНЫ ПОСЛЕ RESUME (чтобы был FurMark/FIO) =====
    try:
        log_resume("[resume] final screens: waiting 10s before capture")
        time.sleep(10)

        cmd = build_screen_cmd("--screen")  # ВАЖНО: именно --screen, не --autoscreen
        log_resume(f"[resume] final screens cmd={cmd}")

        # несколько попыток, чтобы не промахнуться по появлению окон
        for attempt in range(3):
            r = subprocess.run(cmd, shell=False, cwd=workdir, check=False)
            log_resume(f"[resume] final screen attempt {attempt + 1} rc={r.returncode}")
            time.sleep(3)
    except Exception as e:
        log_resume(f"[resume] final screens failed: {e}")

    try:
        generate_reports_headless(workdir)
        archive_results_headless(workdir)
    except Exception as e:
        log_resume(f"[resume] headless reports fail: {e}")

    stop_flag.set()
    clear_state()
    log_resume("[resume] state cleared")

    print("[INFO] PowerShell скрипт завершён. Ожидайте окончания тестов...")


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
            self.last_archive_path = None

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
            self.custom_hour_spin = tk.Spinbox(
                custom_time_frame, from_=0, to=24, width=5, state="disabled",
                textvariable=self.custom_hour
            )
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
            tk.Button(self.root, text="Архив", command=self.archive_results).pack(pady=5)
            tk.Button(self.root, text="Удалить установленные компоненты",
                      command=self.run_uninstall_script).pack(pady=5)
            tk.Button(self.root, text="Отправка архива на сервер", command=self.upload_last_archive).pack(pady=5)
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
                # ✅ FIX: не d[0], а сами значения
                args.extend(self.selected_disks)

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

            pwsh_path = get_powershell_exe()
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

                def autoscreen_once():
                    """Один автоскрин за N секунд до конца теста."""
                    try:
                        delay = calc_autoscreen_delay(duration_seconds)
                        log_resume(f"[gui][autoscreen] delay={delay}s duration={duration_seconds}s")

                        if self.stop_flag.wait(delay):
                            log_resume("[gui][autoscreen] cancelled by stop_flag")
                            return

                        cmd = build_screen_cmd("--autoscreen")
                        log_resume(f"[gui][autoscreen] cmd={cmd}")

                        try:
                            p = subprocess.run(cmd, shell=False, cwd=workdir, check=False)
                            log_resume(f"[gui][autoscreen] done rc={p.returncode}")
                        except Exception as e2:
                            log_resume(f"[gui][autoscreen] run fail: {e2}")
                    except Exception as e:
                        log_resume(f"[gui][autoscreen] fail: {e}")

                threading.Thread(target=autoscreen_once, daemon=True).start()

                def wait_and_final_screens():
                    self.test_proc.wait()
                    self.stop_flag.set()
                    self.stop_btn.config(state="disabled")

                    # ===== 1. ФИНАЛЬНЫЕ СКРИНЫ =====
                    print("[INFO] Ожидание финальных окон тестов...")
                    time.sleep(10)  # Увеличиваем задержку

                    # Делаем несколько попыток скриншотов
                    for attempt in range(1):
                        print(f"[INFO] Попытка скрина #{attempt + 1}")
                        try:
                            cmd = build_screen_cmd("--screen")
                            subprocess.run(cmd, shell=False, cwd=workdir, check=False)
                        except Exception as e:
                            log_resume(f"[gui] screen attempt {attempt + 1} fail: {e}")
                        time.sleep(3)

                    # ===== 2. АВТОМАТИЧЕСКИЕ ОТЧЁТЫ =====
                    print("[INFO] Автоматическое создание отчётов...")

                    # Даём время для завершения всех процессов
                    time.sleep(5)

                    # ВЫЗЫВАЕМ НАПРЯМУЮ, без root.after()
                    try:
                        self.generate_report()
                    except Exception as e:
                        print(f"[ERROR] Ошибка создания отчёта: {e}")
                        log_resume(f"[gui] auto-generate_report fail: {e}")

                    # Даём время для создания отчётов
                    time.sleep(3)

                    # ===== 3. АВТОМАТИЧЕСКИЙ АРХИВ =====
                    print("[INFO] Автоматическое создание архива...")
                    try:
                        self.archive_results()
                    except Exception as e:
                        print(f"[ERROR] Ошибка создания архива: {e}")
                        log_resume(f"[gui] auto-archive fail: {e}")

                    # ===== 4. ОЧИСТКА =====
                    print("[INFO] Очистка состояния...")
                    clear_state()

                    # ===== 5. УВЕДОМЛЕНИЕ ПОЛЬЗОВАТЕЛЯ =====
                    print("[INFO] Тестирование полностью завершено!")

                    # Показываем сообщение пользователю
                    try:
                        # Используем after для показа сообщения в GUI потоке
                        self.root.after(1000, lambda: messagebox.showinfo(
                            "Завершено",
                            "Тестирование полностью завершено!\n\n" +
                            "Все отчёты и архивы сохранены на рабочем столе."
                        ))
                    except Exception as e:
                        print(f"[INFO] Не удалось показать сообщение: {e}")

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
            try:
                cmd = build_screen_cmd("--screen")
                subprocess.run(cmd, shell=False, cwd=workdir, check=False)
            except Exception as e:
                log_resume(f"[gui] stop_test screen fail: {e}")
            clear_state()

        def run_uninstall_script(self):
            try:
                script_path = resource_path("AllUnin.ps1")
                pwsh_path = get_powershell_exe()
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
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            base_dir = os.path.join(desktop, computer_name)
            screens_dir = os.path.join(base_dir, "Screens")
            os.makedirs(screens_dir, exist_ok=True)

            import pyautogui
            img = pyautogui.screenshot()
            img.save(os.path.join(screens_dir, f"screenshot_{now}.png"))

        def generate_report(self):
            try:
                computer_name = os.environ.get("COMPUTERNAME", "Unknown")
                desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
                base_dir = os.path.join(desktop_path, computer_name)
                reports_dir = os.path.join(base_dir, "Reports")
                screens_dir = os.path.join(base_dir, "Screens")

                os.makedirs(reports_dir, exist_ok=True)
                os.makedirs(screens_dir, exist_ok=True)

                # 🔴 ИСПРАВЛЕНО: правильные пути
                html_report = resource_path("Generate_SoftwareReport.ps1")
                aida_path = resource_path(r"SoftForTest\AIDA64\AIDA64Port.exe")  # Прямой путь к AIDA64
                script_path = resource_path("aida_fio_furmark.ps1")
                smart_script = resource_path("smart.ps1")
                pwsh_path = get_powershell_exe()
                env = os.environ.copy()
                env["PATH"] = r"C:\Program Files\PowerShell\7;" + env.get("PATH", "")

                # 🔴 ИСПРАВЛЕНО: вызываем правильную функцию с правильными параметрами
                ps_aida = (
                    f". '{script_path}'; "
                    f"Generate-AidaReport -computerName '{computer_name}' "
                    f"-outputFolder '{reports_dir}' "
                    f"-aida64FullPath '{aida_path}'"
                )

                # 1. Сначала генерируем программный отчет
                result = subprocess.run(
                    [pwsh_path, "-ExecutionPolicy", "Bypass", "-File", html_report,
                     "-ComputerName", computer_name,
                     "-OutputFolder", reports_dir,
                     "-IncludeSoftware"],
                    capture_output=True, text=True, check=True
                )

                print("STDOUT:", result.stdout)
                print("STDERR:", result.stderr)

                # 2. Генерируем отчет AIDA64
                subprocess.run(
                    [pwsh_path, "-ExecutionPolicy", "Bypass", "-Command", ps_aida],
                    env=env,
                    check=True  # Ждем завершения!
                )

                # 3. Скриншоты окон
                # try:
                #     import screen as screen_mod
                #     screen_mod.capture_test_windows()
                # except Exception as e:
                #     log_resume(f"[gui] generate_report screen fail: {e}")
                #     self.take_screenshot()

                # 4. SMART информация
                smart_output = os.path.join(
                    reports_dir, f"smart_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
                )
                subprocess.run(
                    [pwsh_path, "-ExecutionPolicy", "Bypass", "-File", smart_script, smart_output],
                    check=True, env=env
                )

                messagebox.showinfo("Успешно", f"Все отчёты и скриншоты сохранены в:\n{reports_dir}")
            except subprocess.CalledProcessError as e:
                messagebox.showerror("Ошибка", f"Команда вернула ошибку:\n{e}")
                print("STDOUT:", e.stdout)
                print("STDERR:", e.stderr)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка при создании отчета:\n{e}")
            except FileNotFoundError:
                print("Ошибка: скрипт Generate_SoftwareReport.ps1 не найден")

        def archive_results(self):
            try:
                computer_name = os.environ.get("COMPUTERNAME", "Unknown")
                desktop = os.path.join(os.path.expanduser("~"), "Desktop")
                base_dir = os.path.join(desktop, computer_name)

                if not os.path.exists(base_dir):
                    messagebox.showerror("Ошибка", f"Папка не найдена:\n{base_dir}")
                    return

                ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                archive_base = os.path.join(desktop, f"{computer_name}_{ts}")
                shutil.make_archive(archive_base, "zip", root_dir=desktop, base_dir=computer_name)

                self.last_archive_path = f"{archive_base}.zip"
                messagebox.showinfo('Готово', f'Архив создан:\n{self.last_archive_path}')
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось создать архив:\n{e}")

        def upload_last_archive(self):
            try:
                archive_path = self.last_archive_path
                if not archive_path or not os.path.isfile(archive_path):
                    computer_name = os.environ.get("COMPUTERNAME", "Unknown")
                    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
                    pattern_prefix = f"{computer_name}_"
                    candidates = [
                        os.path.join(desktop, f) for f in os.listdir(desktop)
                        if f.startswith(pattern_prefix) and f.endswith(".zip")
                    ]
                    if not candidates:
                        messagebox.showerror("Ошибка", "Архив не найден. Сначала создайте архив.")
                        return
                    archive_path = max(candidates, key=os.path.getmtime)
                    self.last_archive_path = archive_path

                url = "http://10.0.6.41:3000/ulrep"
                args = ["cmd", "/c", "curl", "-sS", "-f", "-F", f'file=@{archive_path}', url]

                completed = subprocess.run(args, capture_output=True, text=True)

                if completed.returncode == 0:
                    msg = completed.stdout.strip() or "Файл успешно загружен."
                    messagebox.showinfo("Отправлено", f"{os.path.basename(archive_path)}\n\nОтвет сервера:\n{msg}")
                else:
                    err = (completed.stderr or completed.stdout or "").strip()
                    raise RuntimeError(f"curl вернул код {completed.returncode}\n{err}")
            except FileNotFoundError:
                messagebox.showerror("Ошибка", "Не найден 'curl'. Убедись, что он доступен в PATH.")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось отправить архив:\n{e}")

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
