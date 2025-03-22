import threading


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
