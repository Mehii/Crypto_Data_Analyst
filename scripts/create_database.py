from pathlib import Path
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_DIR = PROJECT_ROOT / "database"
DATABASE_FILE = DATABASE_DIR / "trading.db"

DATABASE_DIR.mkdir(exist_ok=True)


connection = sqlite3.connect(DATABASE_FILE)

print("Database created successfully:")
print(DATABASE_FILE)

connection.close()