import os
import time
import win32gui
import win32con
import ctypes
from mss import mss as mss_module
import mss.tools

# --- Папка для сохранения ---
desktop_path = os.path.join(os.environ["USERPROFILE"], "Desktop")
report_folder = os.path.join(desktop_path, "report")
os.makedirs(report_folder, exist_ok=True)

# --- Игнорируемые заголовки ---
IGNORED_TITLES = {
    "Program Manager",
    "Начальный экран",
    "Проводник",
    "Microsoft Text Input Application",
    "Default IME",
    "Windows Shell Experience Host",
    "SearchPreloadHelper",
    "Input Indicator Window"
}

# --- Список для обязательной проверки всех терминалов ---
TERMINAL_KEYWORDS = {
    "cmd", "powershell", "command prompt", "windows terminal"
}

def enum_windows_callback(hwnd, windows):
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        if title:
            windows.append((hwnd, title))
    return True

def allow_set_foreground_window(process_id):
    ASFW_ANY = 0xFFFFFFFF
    ctypes.windll.user32.AllowSetForegroundWindow(ASFW_ANY)

def take_screenshot_of_window(hwnd, title):
    try:
        # Активируем окно
        allow_set_foreground_window(os.getpid())
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(1)  # Задержка перед созданием скриншота

        rect = win32gui.GetWindowRect(hwnd)
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]

        if width <= 0 or height <= 0:
            print(f"Пропускаем окно '{title}': нулевой размер.")
            return

        with mss_module() as sct:
            monitor = {
                "top": rect[1],
                "left": rect[0],
                "width": width,
                "height": height
            }
            screenshot = sct.grab(monitor)

            safe_title = "".join(c if c.isalnum() or c in (" ", "_", "-") else "_" for c in title)
            filename = f"{safe_title}_{rect[1]}_{rect[0]}.png"  # Используем координаты для уникальности
            output_path = os.path.join(report_folder, filename)

            mss.tools.to_png(screenshot.rgb, screenshot.size, output=output_path)
            print(f"Скриншот окна '{title}' сохранён как: {filename}")

    except Exception as e:
        print(f"Ошибка при работе с окном '{title}': {e}")

def is_terminal_window(title):
    title_lower = title.lower()
    for keyword in TERMINAL_KEYWORDS:
        if keyword in title_lower:
            return True
    return False

def main():
    print("Получение списка открытых окон...")

    windows = []
    win32gui.EnumWindows(enum_windows_callback, windows)

    if not windows:
        print("Нет видимых окон для съемки.")
        return

    for hwnd, title in windows:
        title = title.strip()

        if not title or title in IGNORED_TITLES:
            continue

        print(f"Обрабатываю окно: {title}")
        take_screenshot_of_window(hwnd, title)

    print("Скриншоты всех подходящих окон успешно сделаны.")

if __name__ == "__main__":
    main()
