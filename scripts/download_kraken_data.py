import os
from pathlib import Path

from dotenv import load_dotenv
from kraken.futures import User


# ==========================================================
# PATHS
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = (
    PROJECT_ROOT
    / "data"
)

ENV_FILE = (
    PROJECT_ROOT
    / ".env"
)

OUTPUT_FILE = (
    DATA_DIR
    / "kraken_futures_account_log.csv"
)


DATA_DIR.mkdir(
    exist_ok=True
)


# ==========================================================
# API CREDENTIALS
# ==========================================================

load_dotenv(
    ENV_FILE
)


api_key = os.getenv(
    "KRAKEN_FUTURES_API_KEY"
)

api_secret = os.getenv(
    "KRAKEN_FUTURES_API_SECRET"
)


if not api_key or not api_secret:

    raise ValueError(
        "Kraken API keys were not found in .env"
    )


# ==========================================================
# KRAKEN CONNECTION
# ==========================================================

kraken = User(
    key=api_key,
    secret=api_secret,
)


# ==========================================================
# DOWNLOAD
# ==========================================================

print("=" * 60)
print("KRAKEN FUTURES ACCOUNT LOG DOWNLOAD")
print("=" * 60)

print()
print(
    "Downloading complete Kraken Futures "
    "account history..."
)


response = kraken.get_account_log_csv()


# ==========================================================
# WRITE DIRECTLY TO FIXED FILE
# ==========================================================
#
# The filename NEVER changes.
#
# If the file already exists, opening it with "wb"
# automatically replaces the old version.
#
# ==========================================================

with open(
    OUTPUT_FILE,
    "wb"
) as file:

    for chunk in response.iter_content(
        chunk_size=8192
    ):

        if chunk:

            file.write(
                chunk
            )


# ==========================================================
# VALIDATE FILE
# ==========================================================

if not OUTPUT_FILE.exists():

    raise RuntimeError(
        "Kraken download failed. "
        "The CSV file was not created."
    )


file_size = (
    OUTPUT_FILE.stat().st_size
)


if file_size == 0:

    raise RuntimeError(
        "Kraken returned an empty CSV file."
    )


# ==========================================================
# DONE
# ==========================================================

print()
print("SUCCESS!")

print(
    f"Saved to: "
    f"{OUTPUT_FILE}"
)

print(
    f"File size: "
    f"{file_size / 1024:.1f} KB"
)

print()
print(
    "The previous Kraken CSV has been replaced "
    "with the latest complete account history."
)