import subprocess
import time
import pyautogui
from PIL import ImageGrab


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
    def __init__(self, name, stress_gpu):
        super().__init__(name)
        self.stress_gpu = stress_gpu

    def start(self):
        self.process = subprocess.Popen(["SoftForTest\\AIDA64\\AIDA64Port.exe"])
        time.sleep(5)  # Подождать запуск интерфейса

        # Открываем меню Сервис -> Тест стабильности системы
        pyautogui.hotkey("alt", "с")  # Сервис
        time.sleep(0.5)
        pyautogui.press(["down"] * 6)  # Тест стабильности системы — 6 раз вниз
        pyautogui.press("enter")
        time.sleep(2)

        # Если включена опция стресс-теста GPU, то активируем чекбокс GPU
        if self.stress_gpu:
            # Координаты нужно подстроить под расположение окна AIDA64
            pyautogui.moveTo(400, 420)  # Примерные координаты чекбокса "Stress GPU(s)"
            pyautogui.click()
            time.sleep(0.3)

        # Нажимаем "Start"
        pyautogui.moveTo(100, 680)  # Примерная координата кнопки Start
        pyautogui.click()


class FurmarkTester(BaseTester):
    def start(self):
        self.process = subprocess.Popen(["SoftForTest\\FurMark\\furmark.exe"])


class FioTester(BaseTester):
    def start(self):
        self.process = subprocess.Popen(["SoftForTest\\fio.msi", "--filename=test.fio", "--size=1G", "--rw=write"])
