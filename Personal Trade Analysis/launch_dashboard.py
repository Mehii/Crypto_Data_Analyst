from pathlib import Path
import ctypes
import shutil
import socket
import subprocess
import sys
import time
import webbrowser


# ==========================================================
# GET REAL EXE / SCRIPT LOCATION
# ==========================================================

def get_real_executable_path():

    if getattr(sys, "frozen", False):

        buffer = ctypes.create_unicode_buffer(32768)

        ctypes.windll.kernel32.GetModuleFileNameW(
            None,
            buffer,
            len(buffer)
        )

        return Path(buffer.value).resolve()

    return Path(__file__).resolve()


# ==========================================================
# PROJECT ROOT
# ==========================================================

REAL_EXECUTABLE = get_real_executable_path()

PROJECT_ROOT = REAL_EXECUTABLE.parent

DASHBOARD_FILE = (
    PROJECT_ROOT
    / "dashboard"
    / "app.py"
)


HOST = "127.0.0.1"
PORT = 8501

DASHBOARD_URL = f"http://{HOST}:{PORT}"


# ==========================================================
# FIND REAL PYTHON
# ==========================================================

def find_python():

    # First try normal PATH
    python_path = shutil.which("python")

    if python_path:

        return python_path


    # Known installation on this computer
    known_python = Path(
        r"C:\Users\kisha\AppData\Local\Python"
        r"\pythoncore-3.14-64"
        r"\python.exe"
    )

    if known_python.exists():

        return str(known_python)


    return None


# ==========================================================
# CHECK PORT
# ==========================================================

def is_port_open(host, port):

    with socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    ) as sock:

        sock.settimeout(0.5)

        return (
            sock.connect_ex(
                (host, port)
            )
            == 0
        )


# ==========================================================
# EXISTING DASHBOARD
# ==========================================================

if is_port_open(HOST, PORT):

    print(
        "Dashboard is already running."
    )

    webbrowser.open(
        DASHBOARD_URL
    )

    sys.exit(0)


# ==========================================================
# CHECK PROJECT
# ==========================================================

print("=" * 60)
print("KRAKEN TRADE DASHBOARD")
print("=" * 60)

print()
print(
    f"Project folder: {PROJECT_ROOT}"
)

print(
    f"Dashboard file: {DASHBOARD_FILE}"
)

print()


if not DASHBOARD_FILE.exists():

    print("ERROR:")
    print()

    print(
        "Dashboard file not found:"
    )

    print(
        DASHBOARD_FILE
    )

    print()
    print(
        "KrakenTradeDashboard.exe must be placed "
        "directly inside:"
    )

    print(
        r"F:\Personal Trade Analysis"
    )

    input(
        "\nPress Enter to close..."
    )

    sys.exit(1)


# ==========================================================
# FIND PYTHON
# ==========================================================

PYTHON_EXECUTABLE = find_python()


if not PYTHON_EXECUTABLE:

    print("ERROR:")
    print()

    print(
        "Python could not be found."
    )

    input(
        "\nPress Enter to close..."
    )

    sys.exit(1)


print(
    f"Python: {PYTHON_EXECUTABLE}"
)


# ==========================================================
# START STREAMLIT
# ==========================================================

print()
print(
    "Starting dashboard..."
)


command = [
    PYTHON_EXECUTABLE,
    "-m",
    "streamlit",
    "run",
    str(DASHBOARD_FILE),
    "--server.headless=true",
    f"--server.port={PORT}",
]


process = subprocess.Popen(
    command,
    cwd=str(PROJECT_ROOT)
)


# ==========================================================
# WAIT FOR DASHBOARD
# ==========================================================

print(
    "Waiting for Streamlit..."
)


dashboard_ready = False


for _ in range(40):

    if is_port_open(
        HOST,
        PORT
    ):

        dashboard_ready = True

        break

    if process.poll() is not None:

        break

    time.sleep(0.5)


# ==========================================================
# OPEN BROWSER
# ==========================================================

if dashboard_ready:

    print()
    print(
        "Dashboard started successfully."
    )

    webbrowser.open(
        DASHBOARD_URL
    )

else:

    print()
    print("ERROR:")
    print(
        "Streamlit failed to start."
    )

    input(
        "\nPress Enter to close..."
    )

    sys.exit(1)


# ==========================================================
# KEEP SERVER RUNNING
# ==========================================================

try:

    process.wait()

except KeyboardInterrupt:

    process.terminate()