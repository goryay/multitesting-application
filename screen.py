import os
import time
import win32gui
import win32con
import win32com.client
from mss import mss
from PIL import Image, ImageStat

# ---------- ЛОГИКА ДЛЯ AIDA64 (СТАРАЯ, КОТОРАЯ У ТЕБЯ РАБОТАЛА) ----------

def is_chart_drawn(img: Image.Image) -> bool:
    """Проверка, что нижняя часть окна AIDA64 НЕ полностью чёрная."""
    width, height = img.size
    bottom_crop = img.crop((0, int(height * 2 / 3), width, height))
    stat = ImageStat.Stat(bottom_crop)
    avg = stat.mean
    return not (avg[0] < 10 and avg[1] < 10 and avg[2] < 10)


def wait_for_aida_ready(sct, rect, max_wait: int = 10) -> Image.Image:
    """
    Ждём, пока окно AIDA64 нормально отрисуется:
    - фон не чисто белый
    - графики внизу не полностью чёрные.
    """
    img = None
    for attempt in range(max_wait):
        shot = sct.grab(rect)
        img = Image.frombytes("RGB", (shot.width, shot.height), shot.rgb)
        stat = ImageStat.Stat(img)
        avg = stat.mean

        # если окно НЕ полностью белое и графики уже есть — ок
        if not (avg[0] > 250 and avg[1] > 250 and avg[2] > 250) and is_chart_drawn(img):
            print(f"[AIDA64] окно готово (attempt={attempt + 1}, avg={avg})")
            return img

        print(f"[AIDA64] попытка {attempt + 1}: окно ещё не отрисовано (avg={avg})")
        time.sleep(15.0)

    print("[AIDA64] предупреждение: окно возможно не отрисовано полностью, берём последнее изображение")
    return img


# -------------------------------------------------------------------------

TARGET_KEYWORDS = [
    "aida64", "System Stability Test",
    "furmark", "fio", "fio.exe", "console",
    "cmd.exe", "pause", "Read-Write-test"
]

MIN_WIDTH = 300
MIN_HEIGHT = 200


def get_report_directory() -> str:
    desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
    computer_name = os.environ.get("COMPUTERNAME", "Unknown")
    base_dir = os.path.join(desktop, computer_name)
    screens_dir = os.path.join(base_dir, "Screens")
    os.makedirs(screens_dir, exist_ok=True)
    return screens_dir


def safe_capture(hwnd, folder: str, autoscreen: bool = False):
    if not win32gui.IsWindowVisible(hwnd):
        return

    title = win32gui.GetWindowText(hwnd).strip()
    class_name = win32gui.GetClassName(hwnd).lower()

    # cmd-консоли
    is_cmd = class_name == "consolewindowclass"

    # Скринить все cmd.exe (консоли) + нужные заголовки
    is_target = (
        is_cmd
        or "FurMark GPU 0" in title
        or "FurMark GPU 1" in title
        or "FIO" in title
        or "System Stability Test" in title
        or any(keyword.lower() in title.lower() for keyword in TARGET_KEYWORDS)
    )
    if not is_target:
        return

    try:
        # AIDA/FurMark лучше разворачивать на максимум
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.SendKeys('%')  # чтобы SetForegroundWindow сработал

        # даём окну время перерисоваться
        time.sleep(2.5 if is_cmd else 6.5)

        for _ in range(3):
            try:
                win32gui.SetForegroundWindow(hwnd)
                break
            except Exception:
                time.sleep(2.0)

        rect = win32gui.GetWindowRect(hwnd)
        x, y, x1, y1 = rect
        width = x1 - x
        height = y1 - y
        if width < MIN_WIDTH or height < MIN_HEIGHT:
            print(f"Пропуск: окно '{title}' слишком маленькое ({width}x{height})")
            return

        with mss() as sct:
            monitor = {"left": x, "top": y, "width": width, "height": height}

            # Для AIDA ждём нормальной отрисовки графиков
            if "System Stability Test" in title or "AIDA64" in title:
                print(f"[AIDA64] окно {width}x{height}, ждём отрисовки графиков")
                image = wait_for_aida_ready(sct, monitor)
            else:
                time.sleep(1.5 if is_cmd else 2.5)
                screenshot = sct.grab(monitor)
                image = Image.frombytes("RGB", (screenshot.width, screenshot.height), screenshot.rgb)

        # имя файла: cmd_XXXX_*.png либо по заголовку
        if is_cmd:
            safe_title = f"cmd_{hwnd}"
        else:
            safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)

        suffix = "auto" if autoscreen else "end"
        filename = f"{safe_title}_{suffix}.png"
        path = os.path.join(folder, filename)
        image.save(path)
        print(f"Скриншот окна '{title}' сохранён как: {filename}")

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

    # Сначала AIDA, потом консоли, потом всё остальное
    def window_priority(h):
        title = win32gui.GetWindowText(h).lower()
        class_name = win32gui.GetClassName(h).lower()
        if "system stability test" in title or "aida64" in title:
            return 0
        if class_name == "consolewindowclass":
            return 1
        return 2

    hwnds_sorted = sorted(hwnds, key=window_priority)

    for hwnd in hwnds_sorted:
        safe_capture(hwnd, folder, autoscreen=autoscreen)

    print("Скриншоты окон тестирования успешно сделаны.")


if __name__ == "__main__":
    print("Ожидание перед началом захвата окон...")
    time.sleep(15)
    capture_test_windows()
