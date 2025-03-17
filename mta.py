import tkinter as tk
from tkinter import ttk


class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("MTA")
        self.iconbitmap("images/mta.ico")
        self.geometry("500x600")



if __name__ == '__main__':
    app = MainApp()
    app.mainloop()
