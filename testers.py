import subprocess
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
