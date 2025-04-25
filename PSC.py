import sys
import os
import win32gui
import win32con
import win32api
import argparse
from PyQt5.QtWidgets import QApplication
from datetime import datetime
from PIL import ImageGrab


class WindowScreenshotTool:
    def __init__(self, output_dir=None):
        self.output_dir = output_dir or os.getcwd()
        os.makedirs(self.output_dir, exist_ok=True)

    def get_window_handle_at_cursor(self):
        """Получить handle окна под курсором мыши"""
        cursor_pos = win32gui.GetCursorPos()
        return win32gui.WindowFromPoint(cursor_pos)

    def get_all_visible_windows(self):
        """Получить список всех видимых окон"""
        windows = []

        def enum_windows_callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                windows.append(hwnd)
            return True

        win32gui.EnumWindows(enum_windows_callback, None)
        return windows

    def get_window_rect(self, hwnd):
        """Получить координаты окна с учетом DPI"""
        try:
            # Получаем реальные координаты с учетом DPI
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            return (left, top, right, bottom)
        except:
            return None

    def take_window_screenshot(self, hwnd, prefix=""):
        """Сделать скриншот указанного окна"""
        try:
            rect = self.get_window_rect(hwnd)
            if not rect:
                print(f"Не удалось получить координаты окна {hwnd}")
                return False

            left, top, right, bottom = rect
            if right <= left or bottom <= top:
                print(f"Некорректные координаты окна {hwnd}")
                return False

            # Создаем скриншот области экрана
            screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))

            # Генерируем имя файла
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            window_title = win32gui.GetWindowText(hwnd)
            safe_title = "".join(c if c.isalnum() else "_" for c in window_title)[:50]
            filename = f"{prefix}screenshot_{safe_title}_{timestamp}.png"
            filepath = os.path.join(self.output_dir, filename)

            # Сохраняем скриншот
            screenshot.save(filepath)
            print(f"Скриншот сохранен: {filepath}")
            return True
        except Exception as e:
            print(f"Ошибка при создании скриншота окна {hwnd}: {str(e)}")
            return False

    def screenshot_all_windows(self):
        """Сделать скриншоты всех видимых окон"""
        windows = self.get_all_visible_windows()
        print(f"Найдено {len(windows)} окон для скриншотов")

        success_count = 0
        for i, hwnd in enumerate(windows, 1):
            window_title = win32gui.GetWindowText(hwnd)
            print(f"[{i}/{len(windows)}] Делаю скриншот: '{window_title}' (hwnd: {hwnd})")
            if self.take_window_screenshot(hwnd, f"window_{i}_"):
                success_count += 1

        print(f"\nГотово! Успешно сохранено {success_count} из {len(windows)} скриншотов")
        return success_count

    def add_screenshot_to_context_menu(self):
        """Добавить пункт в контекстное меню окна"""
        hwnd = self.get_window_handle_at_cursor()
        window_title = win32gui.GetWindowText(hwnd)

        if not window_title:
            print("Не удалось определить окно под курсором")
            return

        print(f"Выбрано окно: '{window_title}' (hwnd: {hwnd})")

        # Создаем временное меню
        menu = win32gui.CreatePopupMenu()
        win32gui.AppendMenu(menu, win32con.MF_STRING, 1, "Сделать скриншот окна")

        # Показываем меню
        pos = win32gui.GetCursorPos()
        win32gui.SetForegroundWindow(hwnd)
        selection = win32gui.TrackPopupMenu(
            menu,
            win32con.TPM_RETURNCMD | win32con.TPM_NONOTIFY,
            pos[0], pos[1], 0, hwnd, None
        )

        if selection == 1:
            self.take_window_screenshot(hwnd)


def main():
    parser = argparse.ArgumentParser(
        description="Утилита для создания скриншотов окон Windows",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Сделать скриншоты всех видимых окон'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Папка для сохранения скриншотов (по умолчанию - текущая директория)'
    )
    parser.add_argument(
        '--context',
        action='store_true',
        help='Добавить пункт в контекстное меню (ПКМ по окну)'
    )

    args = parser.parse_args()

    tool = WindowScreenshotTool(output_dir=args.output)

    if args.all:
        tool.screenshot_all_windows()
    elif args.context:
        app = QApplication(sys.argv)
        tool.add_screenshot_to_context_menu()
        sys.exit(app.exec_())
    else:
        print("Используйте один из параметров:")
        print("  --all      - сделать скриншоты всех окон")
        print("  --context  - добавить пункт в контекстное меню")
        print("  --output   - указать папку для сохранения")


if __name__ == "__main__":
    main()