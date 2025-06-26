import screen
import sys

if __name__ == "__main__":
    hourly = "--hourly" in sys.argv
    screen.capture_test_windows(hourly=hourly)
