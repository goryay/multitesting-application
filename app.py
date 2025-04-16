import tkinter as tk
from tkinter import messagebox
from test_manager import TestManager
from testers import AidaBusinessTester, FurmarkTester, FioTester
import GPUtil
import subprocess
import ctypes


def run_as_admin(command):
    params = f'/c {command}'
    ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell", params, None, 1)


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("MWR")
        self.root.geometry("500x600")

        try:
            self.root.iconbitmap("images/mta.ico")
        except tk.TclError:
            print("Картинка не найдена.")

        self.manager = TestManager()

        self.aida_var = tk.BooleanVar()
        self.furmark_var = tk.BooleanVar()
        self.fio_var = tk.BooleanVar()
        self.stress_gpu_var = tk.BooleanVar()

        self.time_label = tk.Label(self.root, text="Время тестирования (часов):")
        self.time_entry = tk.Entry(self.root, width=5)
        self.start_button = tk.Button(self.root, text="Запустить тестирование", command=self.start_tests)
        self.stop_button = tk.Button(self.root, text="Принудительное остановить тест", command=self.stop_tests)

        self.create_widgets()

        self.aida_var.trace("w", self.update_ui)
        self.furmark_var.trace("w", self.update_ui)
        self.fio_var.trace("w", self.update_ui)
        self.stress_gpu_var.trace("w", self.update_ui)

        self.check_gpu()
        self.update_ui()

    def create_widgets(self):
        tk.Checkbutton(self.root, text="Aida Business", variable=self.aida_var, width=20, anchor="w").pack(fill="both",
                                                                                                           padx=5,
                                                                                                           pady=2)

        self.stress_gpu_checkbutton = tk.Checkbutton(self.root, text="\u2514 Stress GPU(s) для AIDA64",
                                                     variable=self.stress_gpu_var, width=25, anchor="w")
        self.stress_gpu_checkbutton.pack(fill="both", padx=20, pady=2)

        self.furmark_checkbutton = tk.Checkbutton(self.root, text="Furmark", variable=self.furmark_var, width=20,
                                                  anchor="w")
        self.furmark_checkbutton.pack(fill="both", padx=5, pady=2)

        tk.Checkbutton(self.root, text="Fio", variable=self.fio_var, width=20, anchor="w").pack(fill="both", padx=5,
                                                                                                pady=2)

        self.time_label.pack(pady=5)
        self.time_entry.pack(pady=5)
        self.time_entry.insert(0, "1")
        self.start_button.pack(fill="both", padx=5, pady=10)
        self.stop_button.pack(fill="both", padx=5, pady=10)

    def update_ui(self, *args):
        any_selected = self.aida_var.get() or self.furmark_var.get() or self.fio_var.get()
        self.start_button.config(state=tk.NORMAL if any_selected else tk.DISABLED)

        if self.aida_var.get():
            self.stress_gpu_checkbutton.config(state=tk.NORMAL)
        else:
            self.stress_gpu_var.set(False)
            self.stress_gpu_checkbutton.config(state=tk.DISABLED)

        if self.stress_gpu_var.get():
            self.furmark_var.set(False)
            self.furmark_checkbutton.config(state=tk.DISABLED)
        else:
            self.furmark_checkbutton.config(state=tk.NORMAL)

    def start_tests(self):
        install_command = (
            "Start-Process PowerShell -Wait -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File SoftForTest\\PowerShell-7.5.0.msi'"
        )
        run_as_admin(install_command)

        try:
            test_time = int(self.time_entry.get())
            if test_time < 1:
                messagebox.showwarning("Слишком короткое время", "Время тестирования должно быть не менее 1 часа.")
                return
            self.manager.test_time = test_time * 60 * 60
        except ValueError:
            messagebox.showerror("Неверно введены кол-во часов.", "Пожалуйста, введите правильное число.")
            return

        if self.aida_var.get():
            self.manager.add_tester(AidaBusinessTester("AidaBusiness", self.stress_gpu_var.get()))
        if self.furmark_var.get():
            self.manager.add_tester(FurmarkTester("Furmark"))
        if self.fio_var.get():
            self.manager.add_tester(FioTester("Fio"))

        self.manager.start_all()

    def stop_tests(self):
        if messagebox.askokcancel("Предупреждение", "Вы действительно хотите принудительно остановить тестирование?"):
            self.manager.stop_all()

    def check_gpu(self):
        gpus = GPUtil.getGPUs()
        self.has_discrete_gpu = any("NVIDIA" in gpu.name or "AMD" in gpu.name for gpu in gpus)
        self.has_integrated_gpu = any("Intel" in gpu.name for gpu in gpus)

        return self.has_discrete_gpu
