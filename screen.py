import os
import time
import win32gui
import win32con
import win32process
import win32api
import win32com.client
from mss import mss
from PIL import Image
import sys

MIN_WIDTH = 300
MIN_HEIGHT = 200


def get_window_process_name(hwnd) -> str:
    """Пытаемся определить имя процесса (exe), которому принадлежит окно."""
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        hproc = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
        try:
            path = win32process.GetModuleFileNameEx(hproc, 0)
        finally:
            try:
                win32api.CloseHandle(hproc)
            except Exception:
                pass
        return os.path.basename(path).lower()
    except Exception:
        return ""


def get_report_directory():
    desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
    computer_name = os.environ.get("COMPUTERNAME", "Unknown")
    base_dir = os.path.join(desktop, computer_name)
    screens_dir = os.path.join(base_dir, "Screens")
    os.makedirs(screens_dir, exist_ok=True)
    return screens_dir


def get_console_content(hwnd):
    """Пытается получить текст из консольного окна."""
    try:
        import ctypes

        # WM_GETTEXT = 0x000D
        WM_GETTEXT = 0x000D
        # Сначала получаем длину текста
        length = ctypes.windll.user32.SendMessageW(hwnd, win32con.WM_GETTEXTLENGTH, 0, 0)
        if length > 0:
            # Создаём буфер для текста
            buffer = ctypes.create_unicode_buffer(length + 1)
            # Получаем текст
            ctypes.windll.user32.SendMessageW(hwnd, WM_GETTEXT, length + 1, ctypes.byref(buffer))
            return buffer.value
    except Exception:
        pass
    return ""


def safe_capture(hwnd, folder, autoscreen: bool = False, aida_only: bool = False):
    if not win32gui.IsWindowVisible(hwnd):
        return

    title = win32gui.GetWindowText(hwnd).strip()
    if not title:
        return

    class_name = win32gui.GetClassName(hwnd).lower()
    title_lower = title.lower()

    # ============ КРИТИЧЕСКО ВАЖНО: Определяем, делать ли скрин ============

    # Режим ТОЛЬКО AIDA64
    if aida_only:
        is_aida = False
        proc_name = get_window_process_name(hwnd)

        if proc_name:
            is_aida_proc = ("aida64" in proc_name) or (proc_name == "aida64port.exe")
            if is_aida_proc:
                is_aida = ("system stability test" in title_lower) or ("aida64" in title_lower)
        else:
            is_aida = (
                    ("system stability test" in title_lower) or
                    title_lower.startswith("aida64") or
                    "aida64 business" in title_lower
            )

        if not is_aida:
            return  # В режиме aida_only только AIDA64

    else:
        # 1. Для автоскринов (во время теста) - только AIDA64
        if autoscreen:
            is_aida = False
            proc_name = get_window_process_name(hwnd)

            if proc_name:
                is_aida_proc = proc_name in ("aida64port.exe", "aida64.exe")
                if is_aida_proc:
                    is_aida = ("system stability test" in title_lower) or ("aida64" in title_lower)
            else:
                is_aida = (
                        ("system stability test" in title_lower) or
                        title_lower.startswith("aida64") or
                        "aida64 business" in title_lower
                )

            if not is_aida:
                return  # Во время автоскрина только AIDA64

        # 2. Для финальных скринов (когда тесты завершены) - ВСЕ CMD окна
        else:
            # Для финальных скринов делаем ВСЕ CMD/консольные окна
            is_cmd_window = (class_name == "consolewindowclass" or
                             "cmd.exe" in title_lower or
                             "windows terminal" in title_lower)

            # Также захватываем AIDA64 и FurMark
            is_aida = False
            proc_name = get_window_process_name(hwnd)

            if proc_name:
                is_aida_proc = proc_name in ("aida64port.exe", "aida64.exe")
                if is_aida_proc:
                    is_aida = ("system stability test" in title_lower) or ("aida64" in title_lower)
            else:
                is_aida = (
                        ("system stability test" in title_lower) or
                        title_lower.startswith("aida64") or
                        "aida64 business" in title_lower
                )

            is_furmark = "furmark" in title_lower

            # Делаем скрин если: CMD окно ИЛИ AIDA64 ИЛИ FurMark
            if not (is_cmd_window or is_aida or is_furmark):
                return

    # ============ ДЕЛАЕМ СКРИН ============
    try:
        print(f"[DEBUG] Делаем скрин окна: '{title}'")

        # Развернуть/показать окно
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            shell = win32com.client.Dispatch("WScript.Shell")
            shell.SendKeys('%')  # магия, чтобы SetForegroundWindow сработал
            time.sleep(0.5)

            for _ in range(3):
                try:
                    win32gui.SetForegroundWindow(hwnd)
                    break
                except Exception:
                    time.sleep(0.3)
        except Exception:
            pass  # Не критично если не удалось активировать

        # Получаем размеры окна
        try:
            rect = win32gui.GetWindowRect(hwnd)
            x, y, x1, y1 = rect
            width = x1 - x
            height = y1 - y

            print(f"[DEBUG] Размер окна: {width}x{height}")

            if width < MIN_WIDTH or height < MIN_HEIGHT:
                print(f"[DEBUG] Пропуск: слишком маленькое окно")
                return
        except Exception as e:
            print(f"[DEBUG] Ошибка получения размеров: {e}")
            return

        # Делаем скриншот
        with mss() as sct:
            time.sleep(0.5)  # Короткая задержка для стабилизации
            monitor = {"left": x, "top": y, "width": width, "height": height}
            try:
                shot = sct.grab(monitor)
                img = Image.frombytes("RGB", (shot.width, shot.height), shot.rgb)
            except Exception as e:
                print(f"[DEBUG] Ошибка захвата экрана: {e}")
                return

        # Определяем имя файла
        if "system stability test" in title_lower or "aida64" in title_lower:
            safe_title = "aida64_system_stability_test"
        elif "furmark" in title_lower:
            safe_title = "furmark_results"
        elif class_name == "consolewindowclass" or "cmd.exe" in title_lower:
            # Для CMD окон проверяем содержимое
            content = get_console_content(hwnd).lower()

            # Пытаемся определить, что за тест в консоли
            if "run status group" in content or "clat percentiles" in content or "iops=" in content:
                safe_title = "fio_results"
            elif "furmark" in content or "fps:" in content or "gpu:" in content:
                safe_title = "furmark_results"
            else:
                safe_title = "cmd_output"
        else:
            safe_title = "".join(
                c if c.isalnum() or c in " _-()" else "_" for c in title
            )

        # Добавляем суффикс и timestamp
        suffix = "auto" if autoscreen else "end"
        timestamp = int(time.time())
        filename = f"{safe_title}_{suffix}_{timestamp}.png"
        path = os.path.join(folder, filename)

        # Сохраняем
        img.save(path)
        print(f"[SUCCESS] Скрин сохранён: {filename} ({width}x{height})")

    except Exception as e:
        print(f"[ERROR] Ошибка при создании скриншота: {e}")
        import traceback
        traceback.print_exc()


def capture_test_windows(autoscreen: bool = False, aida_only: bool = False):
    print("=" * 60)
    if aida_only:
        print("ЗАХВАТ СКРИНОВ ТОЛЬКО AIDA64")
    else:
        print(f"ЗАХВАТ СКРИНОВ ОКОН ({'AUTO' if autoscreen else 'END'})")
    print("=" * 60)

    # Для финальных скринов даём больше времени на появление окон
    if not autoscreen and not aida_only:
        print("[INFO] Ожидание финальных окон тестов (7 секунд)...")
        time.sleep(7)

    folder = get_report_directory()

    # Собираем все окна
    hwnds = []

    def enum_cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            hwnds.append(hwnd)

    win32gui.EnumWindows(enum_cb, None)

    print(f"Найдено окон: {len(hwnds)}")

    # Сортируем: AIDA64 и CMD окна сначала
    priority_hwnds = []
    other_hwnds = []

    for hwnd in hwnds:
        title = win32gui.GetWindowText(hwnd).lower()
        class_name = win32gui.GetClassName(hwnd).lower()

        # Приоритетные окна:
        # 1. AIDA64
        # 2. CMD/консольные окна (где могут быть результаты FIO/FurMark)
        # 3. FurMark
        if "system stability test" in title or "aida64" in title:
            priority_hwnds.insert(0, hwnd)  # AIDA64 на первое место
        elif class_name == "consolewindowclass" or "cmd.exe" in title:
            priority_hwnds.append(hwnd)  # CMD окна следующие
        elif "furmark" in title:
            priority_hwnds.append(hwnd)  # FurMark тоже приоритет
        else:
            other_hwnds.append(hwnd)

    # Объединяем списки
    sorted_hwnds = priority_hwnds + other_hwnds

    print(f"Будет обработано окон: {len(sorted_hwnds)} (приоритетных: {len(priority_hwnds)})")

    # Обрабатываем окна
    for i, hwnd in enumerate(sorted_hwnds, 1):
        print(f"\n[Обработка {i}/{len(sorted_hwnds)}]")
        safe_capture(hwnd, folder, autoscreen=autoscreen, aida_only=aida_only)

        # Небольшая пауза между окнами
        if i < len(sorted_hwnds):
            time.sleep(0.3)

    print("=" * 60)
    print("ЗАХВАТ ЗАВЕРШЁН")
    print("=" * 60)


if __name__ == "__main__":
    # Парсим аргументы командной строки
    autoscreen = "--autoscreen" in sys.argv
    aida_only = "--aida-only" in sys.argv

    print("Запуск скриншотера...")
    capture_test_windows(autoscreen=autoscreen, aida_only=aida_only)