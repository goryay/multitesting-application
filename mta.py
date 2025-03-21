import tkinter as tk
from tkinter import messagebox
import subprocess
import time
import threading
from PIL import ImageGrab
import GPUtil


class BaseTester:
    def __init__(self, name):
        self.name = name
        self.process = None

    def start(self):
        raise NotImplementedError("Этот метод должен быть переопределен подклассами")

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process = None

    def take_screenshot(self, filename):
        screenshot = ImageGrab.grab()
        screenshot.save(filename)


class AidaBusinessTester(BaseTester):
    def __init__(self, name, gpu_enabled):
        super().__init__(name)
        self.gpu_enabled = gpu_enabled

    def start(self):
        command = ["aida64.exe", "--stress-cpu", "--stress-fpu", "--stress-cache", "--stress-memory"]
        if self.gpu_enabled:
            command.append("--stress-gpu")
        self.process = subprocess.Popen(command)


class FurmarkTester(BaseTester):
    def start(self):
        self.process = subprocess.Popen(["furmark.exe"])


class FioTester(BaseTester):
    def start(self):
        self.process = subprocess.Popen(["fio", "--filename=test.fio", "--size=1G", "--rw=write"])


class CrystalDiskInfoTester(BaseTester):
    def start(self):
        self.process = subprocess.Popen(["CrystalDiskInfo.exe", "--smart"])


class TestManager:
    def __init__(self):
        self.testers = []
        self.test_time = 12 * 60 * 60

    def add_tester(self, tester):
        self.testers.append(tester)

    def start_all(self):
        for tester in self.testers:
            tester.start()
        threading.Timer(self.test_time, self.stop_all).start()

    def stop_all(self):
        for tester in self.testers:
            tester.take_screenshot(f"{tester.name}_screenshot.png")
            tester.stop()


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("MWR")
        self.root.geometry("300x300")

        try:
            self.root.iconbitmap("images/mta.ico")
        except tk.TclError:
            print("Картинка не найдена.")

        self.manager = TestManager()

        # Инициализация переменных для чекбоксов
        self.aida_var = tk.BooleanVar()
        self.furmark_var = tk.BooleanVar()
        self.fio_var = tk.BooleanVar()
        self.crystal_var = tk.BooleanVar()

        # Инициализация виджетов интерфейса
        self.time_label = tk.Label(self.root, text="Время тестирования (часов):")
        self.time_entry = tk.Entry(self.root, width=5)
        self.start_button = tk.Button(self.root, text="Запустить тестирование", command=self.start_tests)
        self.stop_button = tk.Button(self.root, text="Принудительное остановить тест", command=self.stop_tests)

        self.create_widgets()

        # Отслеживание изменений в чекбоксах
        self.aida_var.trace("w", self.update_start_button)
        self.furmark_var.trace("w", self.update_start_button)
        self.fio_var.trace("w", self.update_start_button)
        self.crystal_var.trace("w", self.update_start_button)

        # Начальное состояние кнопки
        self.update_start_button()

    def create_widgets(self):
        tk.Checkbutton(self.root, text="Aida Business", variable=self.aida_var, width=20, anchor="w").pack(fill="both",
                                                                                                           padx=5,
                                                                                                           pady=2)
        tk.Checkbutton(self.root, text="Furmark", variable=self.furmark_var, width=20, anchor="w").pack(fill="both",
                                                                                                        padx=5, pady=2)
        tk.Checkbutton(self.root, text="Fio", variable=self.fio_var, width=20, anchor="w").pack(fill="both", padx=5,
                                                                                                pady=2)
        tk.Checkbutton(self.root, text="CrystalDiskInfo", variable=self.crystal_var, width=20, anchor="w").pack(
            fill="both", padx=5, pady=2)

        self.time_label.pack(pady=5)

        self.time_entry.pack(pady=5)
        self.time_entry.insert(0, "12")

        self.start_button.pack(fill="both", padx=5, pady=10)
        self.stop_button.pack(fill="both", padx=5, pady=10)

    def update_start_button(self, *args):
        # Активируем кнопку только если выбран хотя бы один тест
        any_selected = self.aida_var.get() or self.furmark_var.get() or self.fio_var.get() or self.crystal_var.get()
        self.start_button.config(state=tk.NORMAL if any_selected else tk.DISABLED)

    def start_tests(self):
        try:
            test_time = int(self.time_entry.get())
            if test_time < 12:
                messagebox.showwarning("Слишком короткое время", "Время тестирования должно быть не менее 12 часов.")
                return
            self.manager.test_time = test_time * 60 * 60
        except ValueError:
            messagebox.showerror("Неверно введены кол-во часов.", "Пожалуйста, введите правильное число.")
            return

        gpu_enabled = self.check_gpu()

        if self.aida_var.get():
            self.manager.add_tester(AidaBusinessTester("AidaBusiness", gpu_enabled))
        if self.furmark_var.get():
            self.manager.add_tester(FurmarkTester("Furmark"))
        if self.fio_var.get():
            self.manager.add_tester(FioTester("Fio"))
        if self.crystal_var.get():
            self.manager.add_tester(CrystalDiskInfoTester("CrystalDiskInfo"))

        self.manager.start_all()

    def stop_tests(self):
        if messagebox.askokcancel("Предупреждение", "Вы действительно хотите принудительно остановить тестирование?"):
            self.manager.stop_all()

    def check_gpu(self):
        gpus = GPUtil.getGPUs()
        return len(gpus) > 0


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("Программа была прервана пользователем.")
