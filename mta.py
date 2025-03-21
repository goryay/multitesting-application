import tkinter as tk
from tkinter import messagebox


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("MWR")
        self.root.geometry("300x300")

        try:
            self.root.iconbitmap("images/mta.ico")
        except tk.TclError:
            print("Картинка не найдена.")

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


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("Программа была прервана пользователем.")
