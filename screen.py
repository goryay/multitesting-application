import os
import time
import win32gui
import win32con
import win32com.client
from mss import mss
from PIL import Image

TARGET_KEYWORDS = [
    "aida64",
    "system stability test",
    "furmark",
    "fio",
    "fio.exe",
    "cmd.exe - pause",
    "read-write-test",
]

MIN_WIDTH = 300
MIN_HEIGHT = 200


def get_report_directory():
    desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
    computer_name = os.environ.get("COMPUTERNAME", "Unknown")
    base_dir = os.path.join(desktop, computer_name)
    screens_dir = os.path.join(base_dir, "Screens")
    os.makedirs(screens_dir, exist_ok=True)
    return screens_dir


def safe_capture(hwnd, folder, autoscreen: bool = False):
    if not win32gui.IsWindowVisible(hwnd):
        return

    title = win32gui.GetWindowText(hwnd).strip()
    if not title:
        return

    class_name = win32gui.GetClassName(hwnd).lower()
    is_cmd = class_name == "consolewindowclass"

    title_lower = title.lower()
    is_aida = "system stability test" in title_lower or "aida64" in title_lower
    is_furmark = "furmark" in title_lower

    is_target = (
        is_cmd
        or is_aida
        or is_furmark
        or any(k in title_lower for k in TARGET_KEYWORDS)
    )
    if not is_target:
        return

    try:
        # Развернуть/показать окно
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.SendKeys('%')  # магия, чтобы SetForegroundWindow сработал
        time.sleep(1.0)

        for _ in range(5):
            try:
                win32gui.SetForegroundWindow(hwnd)
                break
            except Exception:
                time.sleep(0.5)

        rect = win32gui.GetWindowRect(hwnd)
        x, y, x1, y1 = rect
        width = x1 - x
        height = y1 - y

        if width < MIN_WIDTH or height < MIN_HEIGHT:
            print(f"Пропуск '{title}': слишком маленькое окно ({width}x{height})")
            return

        with mss() as sct:
            # короткая задержка, чтобы окно перерисовалось
            time.sleep(2.0)
            monitor = {"left": x, "top": y, "width": width, "height": height}
            shot = sct.grab(monitor)
            img = Image.frombytes("RGB", (shot.width, shot.height), shot.rgb)

        if is_cmd:
            safe_title = f"cmd_{hwnd}"
        else:
            safe_title = "".join(
                c if c.isalnum() or c in " _-" else "_" for c in title
            )

        suffix = "auto" if autoscreen else "end"
        filename = f"{safe_title}_{suffix}.png"
        path = os.path.join(folder, filename)
        img.save(path)
        print(f"Скрин '{title}' сохранён как {filename}")

    except Exception as e:
        print(f"Ошибка при работе с окном '{title}': {e}")


def capture_test_windows(autoscreen: bool = False):
    print("Получение списка окон тестирования...")
    folder = get_report_directory()
    hwnds = []

    def enum_cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            hwnds.append(hwnd)

    win32gui.EnumWindows(enum_cb, None)

    def window_priority(h):
        t = win32gui.GetWindowText(h).lower()
        cls = win32gui.GetClassName(h).lower()
        if "system stability test" in t or "aida64" in t:
            return 0
        if cls == "consolewindowclass":
            return 1
        return 2

    for hwnd in sorted(hwnds, key=window_priority):
        safe_capture(hwnd, folder, autoscreen=autoscreen)

    print("Скриншоты окон тестирования сделаны.")


if __name__ == "__main__":
    print("Ожидание перед началом захвата окон...")
    time.sleep(15)
    capture_test_windows()
