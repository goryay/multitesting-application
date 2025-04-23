import tkinter as tk
from tkinter import messagebox
import subprocess
import os
import psutil
import threading
import time
import pyautogui
from datetime import datetime


class TestLauncherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Меню тестирования")
        self.root.geometry("500x1000")

        self.test_choice = tk.StringVar(value="1")
        self.time_choice = tk.StringVar(value="3")
        self.custom_time = tk.StringVar(value="")
        self.gpu2_enabled = tk.BooleanVar(value=False)
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

        self.custom_time_entry = tk.Entry(self.root, textvariable=self.custom_time, state="disabled")
        self.custom_time_entry.pack(pady=5)

        self.disk_frame = tk.LabelFrame(self.root, text="Выберите диски для FIO:")
        self.disk_frame.pack(pady=10, fill="x", padx=10)
        self.populate_disks()

        tk.Button(self.root, text="Запустить тест", command=self.run_test).pack(pady=10)
        tk.Button(self.root, text="Сделать скриншот", command=self.take_screenshot).pack(pady=5)
        tk.Button(self.root, text="Создать отчёт", command=self.generate_report).pack(pady=5)
        tk.Button(self.root, text="Выход", command=self.root.quit).pack(pady=5)

    def toggle_custom(self):
        if self.time_choice.get() == "6":
            self.custom_time_entry.config(state="normal")
        else:
            self.custom_time_entry.config(state="disabled")

    def populate_disks(self):
        for widget in self.disk_frame.winfo_children():
            widget.destroy()

        self.checkbuttons.clear()
        self.check_vars.clear()

        for part in psutil.disk_partitions():
            if "cdrom" in part.opts or not os.path.exists(part.mountpoint):
                continue
            var = tk.BooleanVar()
            dev = part.device.rstrip(":\\")
            cb = tk.Checkbutton(self.disk_frame, text=f"{dev} ({part.mountpoint})", variable=var)
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
            if not self.custom_time.get().isdigit():
                messagebox.showerror("Ошибка", "Введите корректное число минут")
                return
            duration = self.custom_time.get()
        else:
            duration = time_map.get(self.time_choice.get(), "60")

        args.append(duration)

        duration_seconds = int(duration) * 60
        self.schedule_screenshots(duration_seconds)

        pwsh_path = r'"C:\\Program Files\\PowerShell\\7\\pwsh.exe"'
        script_full_path = os.path.abspath("aida_fio_furmark.ps1")
        cmd = f'{pwsh_path} -ExecutionPolicy Bypass -File "{script_full_path}" {" ".join(args)}'

        try:
            subprocess.Popen(cmd, shell=True)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось запустить скрипт:\n{e}")

    def schedule_screenshots(self, duration_seconds):
        if duration_seconds > 300:
            threading.Timer(duration_seconds - 300, self.take_screenshot).start()
        threading.Timer(duration_seconds, self.take_screenshot).start()

    def take_screenshot(self):
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        screenshot = pyautogui.screenshot()
        path = os.path.join(os.path.expanduser("~"), "Pictures", f"test_screenshot_{now}.png")
        screenshot.save(path)
        print(f"Скриншот сохранён: {path}")

    def generate_report(self):
        try:
            import platform
            import psutil
            import pathlib

            now = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            doc_path = pathlib.Path.home() / "Documents" / "TestReports"
            doc_path.mkdir(parents=True, exist_ok=True)

            with open("system_report.html", "r", encoding="utf-8") as f:
                html = f.read()

            # Подставим актуальные данные
            cpu_info = platform.processor()
            ram_total = f"{round(psutil.virtual_memory().total / (1024 ** 3), 2)} GB"
            os_info = platform.platform()

            disk_html = ""
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    disk_html += f"<li>{part.device} ({part.mountpoint}): {round(usage.total / (1024 ** 3), 2)} GB</li>"
                except Exception:
                    continue

            # Меняем данные в шаблоне
            html = html.replace("{{cpu_info}}", cpu_info)
            html = html.replace("{{ram_total}}", ram_total)
            html = html.replace("{{os_info}}", os_info)
            html = html.replace("{{disk_info}}", disk_html)

            report_path = doc_path / f"system_report_{now}.html"
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(html)

            messagebox.showinfo("Готово", f"Отчёт сохранён: {report_path}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при генерации отчета: {e}")


if __name__ == '__main__':
    root = tk.Tk()
    app = TestLauncherApp(root)
    root.mainloop()
