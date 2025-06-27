import sys
import screen

if "--screen" in sys.argv:
    hourly = "--hourly" in sys.argv

    screen.capture_test_windows(hourly=hourly)
    sys.exit()

import tkinter as tk
from tkinter import messagebox
import subprocess
import os
import psutil
import time
import threading
import ctypes
import shutil

import pyautogui
from datetime import datetime


def is_frozen():
    return getattr(sys, 'frozen', False)


def install_dependencies_if_needed():
    required_paths = [
        r"C:\Program Files\PowerShell\7\pwsh.exe",
        r"C:\Program Files\fio\fio.exe",
        r"C:\Program Files\smartmontools\bin\smartctl.exe"
    ]

    all_installed = all(os.path.exists(path) for path in required_paths)

    if not all_installed:
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable)) if is_frozen() else os.path.dirname(
            __file__)
        script_path = os.path.join(base_dir, "install_dependencies.ps1")
        if os.path.exists(script_path):
            subprocess.run([
                "powershell.exe",
                "-ExecutionPolicy", "Bypass",
                "-File", script_path
            ], check=True)
        else:
            raise FileNotFoundError(f"Не найден скрипт установки: {script_path}")


install_dependencies_if_needed()


class TestLauncherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Меню тестирования")
        self.root.geometry("500x1000")

        self.test_choice = tk.StringVar(value="1")
        self.time_choice = tk.StringVar(value="3")
        self.custom_time = tk.StringVar(value="")
        self.gpu2_enabled = tk.BooleanVar(value=False)
        self.custom_hours = tk.StringVar(value="0")
        self.custom_minutes = tk.StringVar(value="0")

        self.selected_disks = []

        self.checkbuttons = []
        self.check_vars = []

        self.create_widgets()

    def create_widgets(self):
        tk.Label(self.root, text="=== МЕНЮ ТЕСТИРОВАНИЯ ===", font=("Arial", 12, "bold")).pack(pady=10)

        tests = [
            ("1) Только AIDA64", "1"),
            ("2) AIDA64 + FurMark", "2"),
            ("3) AIDA64 + FurMark + FIO", "3"),
            ("4) AIDA64 + FIO", "4")
        ]
        for text, val in tests:
            tk.Radiobutton(self.root, text=text, variable=self.test_choice, value=val,
                           command=self.update_disk_checkboxes).pack(anchor="w", padx=20)

        tk.Checkbutton(self.root, text="Использовать 2 видеокарты", variable=self.gpu2_enabled).pack(
            anchor="w", padx=20, pady=(0, 10))

        tk.Label(self.root, text="Выберите длительность теста:").pack()

        durations = [
            ("1) 10 минут", "1"),
            ("2) 30 минут", "2"),
            ("3) 1 час", "3"),
            ("4) 8 часов", "4"),
            ("5) 12 часов", "5"),
            ("6) Ввести своё значение", "6")
        ]
        for text, val in durations:
            tk.Radiobutton(self.root, text=text, variable=self.time_choice, value=val,
                           command=self.toggle_custom).pack(anchor="w", padx=20)

        # Создаём поля для часов и минут
        custom_time_frame = tk.Frame(self.root)
        custom_time_frame.pack()

        tk.Label(custom_time_frame, text="Часы:").grid(row=0, column=0)
        self.custom_hours = tk.IntVar(value=0)
        self.custom_hours_spin = tk.Spinbox(custom_time_frame, from_=0, to=24, width=5, textvariable=self.custom_hours,
                                            state="disabled")
        self.custom_hours_spin.grid(row=0, column=1)

        # tk.Label(custom_time_frame, text="Минуты:").grid(row=0, column=2)
        # self.custom_minutes = tk.IntVar(value=0)
        # self.custom_minutes_spin = tk.Spinbox(custom_time_frame, from_=0, to=59, width=5,
        #                                       textvariable=self.custom_minutes, state="disabled")
        # self.custom_minutes_spin.grid(row=0, column=3)

        self.disk_frame = tk.LabelFrame(self.root, text="Выберите диски для FIO:")
        self.disk_frame.pack(pady=10, fill="x", padx=10)
        self.populate_disks()

        tk.Button(self.root, text="Запустить тест", command=self.run_test).pack(pady=10)
        tk.Button(self.root, text="Сделать скриншот", command=self.take_screenshot).pack(pady=5)
        tk.Button(self.root, text="Создать отчёт", command=self.generate_report).pack(pady=5)
        tk.Button(self.root, text="Удалить установленные компоненты", command=self.run_uninstall_script).pack(pady=5)
        tk.Button(self.root, text="Выход", command=self.root.quit).pack(pady=5)

    def toggle_custom(self):
        state = "normal" if self.time_choice.get() == "6" else "disabled"
        self.custom_hours_spin.config(state=state)
        # self.custom_minutes_spin.config(state=state)

    def populate_disks(self):
        for widget in self.disk_frame.winfo_children():
            widget.destroy()

        self.checkbuttons.clear()
        self.check_vars.clear()

        def get_drive_info(path):
            volume_name_buf = ctypes.create_unicode_buffer(1024)
            fs_name_buf = ctypes.create_unicode_buffer(1024)
            try:
                ctypes.windll.kernel32.GetVolumeInformationW(
                    ctypes.c_wchar_p(path),
                    volume_name_buf,
                    ctypes.sizeof(volume_name_buf),
                    None, None, None,
                    fs_name_buf,
                    ctypes.sizeof(fs_name_buf)
                )
                return volume_name_buf.value
            except:
                return "Без имени"

        for part in psutil.disk_partitions():
            if "cdrom" in part.opts or not os.path.exists(part.mountpoint):
                continue
            var = tk.BooleanVar()
            dev = part.device.rstrip(":\\")
            try:
                label = get_drive_info(part.device)
            except Exception:
                label = "Без имени"

            try:
                total = shutil.disk_usage(part.mountpoint).total
                size_gb = f"{total // (1024 ** 3)} GB"
            except:
                size_gb = "?"

            display_name = f"{dev}: ({label}, {size_gb})"
            cb = tk.Checkbutton(self.disk_frame, text=display_name, variable=var)
            cb.pack(anchor="w")
            self.checkbuttons.append(cb)
            self.check_vars.append((var, dev))

        self.update_disk_checkboxes()

    def update_disk_checkboxes(self):
        enable = self.test_choice.get() in ("3", "4")
        state = "normal" if enable else "disabled"
        for cb in self.checkbuttons:
            cb.config(state=state)

    def run_test(self):
        test_map = {
            "1": ["AIDA"],
            "2": ["AIDA", "FURMARK"],
            "3": ["AIDA", "FURMARK", "FIO"],
            "4": ["AIDA", "FIO"]
        }

        time_map = {
            "1": "10",
            "2": "30",
            "3": "60",
            "4": "480",
            "5": "720"
        }

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
                hours = int(self.custom_hours.get())
                minutes = int(self.custom_minutes.get())
                duration = str(hours * 60 + minutes)
                if int(duration) <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Ошибка", "Введите корректное количество часов и минут")
                return

        else:
            time_map = {
                "1": "10",
                "2": "30",
                "3": "60",
                "4": "480",
                "5": "720"
            }
            duration = time_map.get(self.time_choice.get(), "60")

        args.append(duration)

        duration_seconds = int(duration) * 60

        def hourly_screenshot_loop(total_duration):
            interval = 3600  # 1 час
            elapsed = interval  # первый снимок через 1 час
            while elapsed < total_duration:
                time.sleep(interval)
                try:
                    exe_path = sys.executable if is_frozen() else os.path.abspath("main.py")
                    subprocess.Popen([exe_path, "--screen", "--hourly"], shell=True)
                    print(f"[СКРИН] Ежечасный скриншот сделан (спустя {elapsed // 60} мин)")
                except Exception as e:
                    print(f"Ошибка при попытке сделать ежечасный скриншот: {e}")
                elapsed += interval

        threading.Thread(target=hourly_screenshot_loop, args=(duration_seconds,), daemon=True).start()

        half_duration = duration_seconds // 2
        near_end = max(5, duration_seconds - 30)
        pwsh_path = r'C:\Program Files\PowerShell\7\pwsh.exe'
        script_full_path = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)),
                                        "aida_fio_furmark.ps1")
        cmd = f'"{pwsh_path}" -ExecutionPolicy Bypass -File "{script_full_path}" {" ".join(args)}'

        # Автоматический вызов скриншотов
        try:
            subprocess.Popen([pwsh_path, "-ExecutionPolicy", "Bypass", "-File", script_full_path, *args])

            time.sleep(30)  # Подождать появления окон

            def screenshot_after_delay(delay_sec):
                time.sleep(delay_sec)
                exe_path = sys.executable if is_frozen() else os.path.abspath("main.py")
                subprocess.Popen([exe_path, "--screen", "--hourly"], shell=True)

            # screen.capture_test_windows()
            # Один ближе к середине, один в самом конце, один — через 5 секунд после завершения (последний результат FIO)
            threading.Thread(target=screenshot_after_delay, args=(half_duration,), daemon=True).start()
            threading.Thread(target=screenshot_after_delay, args=(near_end,), daemon=True).start()
            threading.Thread(target=screenshot_after_delay, args=(duration_seconds + 5,), daemon=True).start()

        except Exception as e:
            print(f"Ошибка вызова screen.capture_test_windows(): {e}")

    def run_uninstall_script(self):
        try:
            script_path = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)), "AllUnin.ps1")
            pwsh_path = r"C:\Program Files\PowerShell\7\pwsh.exe"
            subprocess.run([pwsh_path, "-ExecutionPolicy", "Bypass", "-File", script_path], check=True)
            messagebox.showinfo("Готово", "Удаление завершено.")
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Ошибка", f"Сценарий удаления вернул ошибку:\n{e}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при запуске удаления:\n{e}")

    def take_screenshot(self):
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        computer_name = os.environ.get("COMPUTERNAME", "Unknown")
        base_path = os.path.join(os.path.expanduser("~"), "Desktop", "Report", computer_name)
        os.makedirs(base_path, exist_ok=True)
        screenshot = pyautogui.screenshot()
        path = os.path.join(base_path, f"screenshot_{now}.png")
        screenshot.save(path)
        print(f"Скриншот сохранён: {path}")

    def generate_report(self):
        try:
            base_dir = os.path.dirname(__file__) if not is_frozen() else getattr(sys, "_MEIPASS",
                                                                                 os.path.dirname(sys.executable))

            computer_name = os.environ.get("COMPUTERNAME", "Unknown")
            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
            report_dir = os.path.join(desktop_path, "Report", computer_name)
            os.makedirs(report_dir, exist_ok=True)

            aida_path = os.path.abspath("SoftForTest\\AIDA64\\AIDA64Port.exe")
            script_path = os.path.join(base_dir, "aida_fio_furmark.ps1")
            smart_script = os.path.join(base_dir, "smart.ps1")
            pwsh_path = r"C:\Program Files\PowerShell\7\pwsh.exe"

            # 1. Генерация отчета AIDA64 (асинхронно)
            ps_aida = (
                f". '{script_path}'; "
                f"Generate-Report -computerName '{computer_name}' "
                f"-desktopPath '{desktop_path}' "
                f"-aida64FullPath '{aida_path}'"
            )
            subprocess.Popen([pwsh_path, "-ExecutionPolicy", "Bypass", "-Command", ps_aida])

            # 2. Скриншот
            try:
                screen.capture_test_windows()
            except Exception as e:
                print(f"Ошибка при запуске screen.py: {e}")
                self.take_screenshot()

            # 3. Генерация SMART-отчёта
            smart_output = os.path.join(report_dir, f"smart_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt")
            smart_command = f"& '{smart_script}' '{smart_output}'"
            subprocess.run([pwsh_path, "-ExecutionPolicy", "Bypass", "-Command", smart_command], check=True)

            messagebox.showinfo("Успешно", f"Все отчёты и скриншоты сохранены в:\n{report_dir}")

        except subprocess.CalledProcessError as e:
            messagebox.showerror("Ошибка", f"Команда вернула ошибку:\n{e}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при создании отчета:\n{e}")


if __name__ == '__main__':
    root = tk.Tk()
    app = TestLauncherApp(root)
    root.mainloop()
