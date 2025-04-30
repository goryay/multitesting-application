import os
import time
from datetime import datetime
import win32gui
import win32con
import win32com.client
from mss import mss
from PIL import Image

TARGET_KEYWORDS = ["aida64", "furmark", "fio", "console", "System Stability Test", "FurMark",
                   "cmd.exe", "fio.exe"]


# TARGET_KEYWORDS = ["aida64", "furmark", "fio", "cmd", "console", "cmd.exe"]


def get_report_directory():
    desktop = os.path.join(os.path.join(os.environ["USERPROFILE"]), "Desktop")
    computer_name = os.environ["COMPUTERNAME"]
    report_directory = os.path.join(desktop, "Report", computer_name)
    if not os.path.exists(report_directory):
        os.makedirs(report_directory)
    return report_directory


def capture_window(hwnd, folder):
    if not win32gui.IsWindowVisible(hwnd):
        return

    title = win32gui.GetWindowText(hwnd)
    if not any(keyword in title.lower() for keyword in TARGET_KEYWORDS):
        return

    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.SendKeys('%')  # Чтобы избежать Access Denied
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.5)

        rect = win32gui.GetWindowRect(hwnd)
        x, y, x1, y1 = rect
        width = x1 - x
        height = y1 - y

        with mss() as sct:
            screenshot = sct.grab({"left": x, "top": y, "width": width, "height": height})
            image = Image.frombytes("RGB", (screenshot.width, screenshot.height), screenshot.rgb)

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)
            filename = f"{safe_title}_{x}_{y}_{timestamp}.png"
            path = os.path.join(folder, filename)
            image.save(path)

            print(f"Скриншот окна '{title}' сохранён как: {filename}")
    except Exception as e:
        print(f"Ошибка при работе с окном '{title}': {e}")


def capture_test_windows():
    print("Получение списка окон тестирования...")
    folder = get_report_directory()
    win32gui.EnumWindows(lambda hwnd, _: capture_window(hwnd, folder), None)
    print("Скриншоты окон тестирования успешно сделаны.")


if __name__ == "__main__":
    # time.sleep(300)  # Подождать 5 секунд перед началом
    time.sleep(600)  # Подождать 5 секунд перед началом
    capture_test_windows()
