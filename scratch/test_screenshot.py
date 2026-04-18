import mss
import mss.tools

def capture():
    with mss.mss() as sct:
        filename = sct.shot(output="scratch/desktop_view.png")
        print(f"Screenshot saved to {filename}")

if __name__ == "__main__":
    capture()
