from pathlib import Path
import sqlite3
import pandas as pd


# ==========================================================
# PATHS
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_FILE = (
    PROJECT_ROOT
    / "data"
    / "kraken_futures_account_log.csv"
)

DATABASE_FILE = (
    PROJECT_ROOT
    / "database"
    / "trading.db"
)


# ==========================================================
# CHECK SOURCE FILE
# ==========================================================

if not DATA_FILE.exists():

    raise FileNotFoundError(
        "Kraken account log was not found:\n"
        f"{DATA_FILE}"
    )


print("=" * 60)
print("KRAKEN DATABASE IMPORT")
print("=" * 60)

print()
print(
    f"Reading: {DATA_FILE.name}"
)


# ==========================================================
# READ FULL KRAKEN EXPORT
# ==========================================================

df = pd.read_csv(
    DATA_FILE
)


if df.empty:

    raise ValueError(
        "The Kraken CSV is empty. "
        "Database import cancelled."
    )


# ==========================================================
# CLEAN COLUMN NAMES
# ==========================================================

df.columns = (
    df.columns
    .str.strip()
    .str.lower()
    .str.replace(
        " ",
        "_"
    )
)


# ==========================================================
# VALIDATE REQUIRED COLUMNS
# ==========================================================

required_columns = [
    "uid",
    "datetime",
    "type",
]


missing_columns = [
    column
    for column in required_columns
    if column not in df.columns
]


if missing_columns:

    raise ValueError(
        "Kraken CSV is missing required columns: "
        + ", ".join(missing_columns)
    )


# ==========================================================
# REMOVE DUPLICATE UIDS
# ==========================================================

rows_received = len(df)

df = df.drop_duplicates(
    subset=["uid"],
    keep="first"
)

unique_rows = len(df)

duplicates_removed = (
    rows_received
    -
    unique_rows
)


print(
    f"Rows received: "
    f"{rows_received}"
)

print(
    f"Unique rows: "
    f"{unique_rows}"
)

print(
    f"Columns: "
    f"{len(df.columns)}"
)


if duplicates_removed > 0:

    print(
        f"Duplicate UIDs removed: "
        f"{duplicates_removed}"
    )


# ==========================================================
# CONNECT TO SQLITE
# ==========================================================

conn = sqlite3.connect(
    DATABASE_FILE,
    timeout=30
)


try:

    # ======================================================
    # CHECK WHETHER RAW_LEDGER EXISTS
    # ======================================================

    raw_table_exists = conn.execute(
        """
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'raw_ledger'
        """
    ).fetchone()[0]


    # ======================================================
    # CREATE TABLE IF IT DOES NOT EXIST
    # ======================================================

    if not raw_table_exists:

        df.head(0).to_sql(
            "raw_ledger",
            conn,
            if_exists="replace",
            index=False
        )


    # ======================================================
    # VERIFY DATABASE COLUMNS
    # ======================================================

    database_columns = [
        row[1]
        for row in conn.execute(
            """
            PRAGMA table_info(raw_ledger)
            """
        ).fetchall()
    ]


    csv_columns = list(
        df.columns
    )


    if database_columns != csv_columns:

        raise RuntimeError(
            "The Kraken CSV structure does not match "
            "the existing raw_ledger table.\n\n"
            f"Database columns: {database_columns}\n\n"
            f"CSV columns: {csv_columns}"
        )


    # ======================================================
    # REPLACE CONTENTS
    # ======================================================
    #
    # Important:
    #
    # We DO NOT drop raw_ledger.
    #
    # We only empty it and refill it.
    #
    # This means all existing SQLite views remain valid.
    #
    # ======================================================

    conn.execute(
        """
        DELETE FROM raw_ledger
        """
    )


    # ======================================================
    # INSERT FULL FRESH DATASET
    # ======================================================

    columns = list(
        df.columns
    )

    column_names = ",".join(
        f'"{column}"'
        for column in columns
    )

    placeholders = ",".join(
        ["?"] * len(columns)
    )


    insert_sql = f"""
        INSERT INTO raw_ledger
        ({column_names})
        VALUES ({placeholders})
    """


    values = (
        df.where(
            pd.notnull(df),
            None
        )
        .values
        .tolist()
    )


    conn.executemany(
        insert_sql,
        values
    )


    # ======================================================
    # UNIQUE UID INDEX
    # ======================================================

    conn.execute(
        """
        CREATE UNIQUE INDEX
        IF NOT EXISTS idx_raw_ledger_uid
        ON raw_ledger(uid)
        """
    )


    # ======================================================
    # VERIFY IMPORT
    # ======================================================

    final_rows = conn.execute(
        """
        SELECT COUNT(*)
        FROM raw_ledger
        """
    ).fetchone()[0]


    if final_rows != unique_rows:

        raise RuntimeError(
            "Import verification failed.\n"
            f"Expected {unique_rows} rows, "
            f"but SQLite contains {final_rows}."
        )


    # ======================================================
    # COMMIT
    # ======================================================

    conn.commit()


    print()
    print("SUCCESS!")
    print()

    print(
        "raw_ledger refreshed successfully."
    )

    print(
        f"Database rows: "
        f"{final_rows}"
    )

    print()
    print(
        "The raw database now matches "
        "kraken_futures_account_log.csv."
    )


except Exception:

    conn.rollback()

    print()
    print(
        "ERROR: Import failed."
    )

    print(
        "Existing database changes were rolled back."
    )

    raise


finally:

    conn.close()