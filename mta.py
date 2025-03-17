import tkinter as tk
from tkinter import ttk


class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("MTA")
        self.iconbitmap("images/mta.ico")
        self.geometry("200x300")

        self.label = ttk.Label(text='Выберите тест', font=('Arial', 20))
        self.label.pack(anchor='center')

        self.btn1 = ttk.Button(text='Тест GPU')
        self.btn1.pack(anchor='center')
        self.btn2 = ttk.Button(text='Тест CPU')
        self.btn2.pack(anchor='center')
        self.btn3 = ttk.Button(text='Тест RAM')
        self.btn3.pack(anchor='center')
        self.btn4 = ttk.Button(text='Тест ROM')
        self.btn4.pack(anchor='center')

        self.btn5 = ttk.Button(text='Собрать отчёт')
        self.btn5.pack(anchor='center')

if __name__ == '__main__':
    app = MainApp()
    app.mainloop()
