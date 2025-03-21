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


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("Программа была прервана пользователем.")
