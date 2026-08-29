from pathlib import Path
import sqlite3
import pandas as pd


# ==========================================================
# PATHS
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATABASE_FILE = (
    PROJECT_ROOT
    / "database"
    / "trading.db"
)


# ==========================================================
# CONNECT
# ==========================================================

conn = sqlite3.connect(
    DATABASE_FILE,
    timeout=30
)


# ==========================================================
# LOAD RAW KRAKEN DATA
# ==========================================================
#
# rowid is important because it preserves the order in which
# the Kraken CSV was imported.
#
# ==========================================================

raw = pd.read_sql_query(
    """
    SELECT
        rowid AS raw_rowid,
        *
    FROM raw_ledger
    ORDER BY raw_rowid ASC
    """,
    conn
)


print(
    f"Raw Kraken rows loaded: "
    f"{len(raw)}"
)


# ==========================================================
# CLEAN DATA TYPES
# ==========================================================

raw["datetime"] = pd.to_datetime(
    raw["datetime"],
    errors="coerce"
)


numeric_columns = [
    "change",
    "new_balance",
    "new_average_entry_price",
    "trade_price",
    "mark_price",
    "funding_rate",
    "realized_pnl",
    "fee",
    "realized_funding",
    "liquidation_fee",
]


for column in numeric_columns:

    if column in raw.columns:

        raw[column] = pd.to_numeric(
            raw[column],
            errors="coerce"
        )


# ==========================================================
# POSITION MOVEMENT ROWS
# ==========================================================

positions = raw[
    (raw["symbol"] == raw["contract"])
    &
    raw["type"].isin(
        [
            "futures trade",
            "futures partial liquidation",
            "futures liquidation",
        ]
    )
].copy()


positions = positions.dropna(
    subset=[
        "datetime",
        "contract",
        "change",
        "new_balance",
    ]
)


print(
    f"Position movements loaded: "
    f"{len(positions)}"
)


# ==========================================================
# USD REALIZED PNL ROWS
# ==========================================================
#
# Kraken normally records a closing execution as something
# similar to:
#
#   kfee applied
#   futures trade / USD     <- realized P&L
#   futures trade / contract <- position movement
#
# We match the financial row to the position row using:
#
# contract + datetime + trade price + nearest raw row
#
# ==========================================================

financial_rows = raw[
    (raw["type"] == "futures trade")
    &
    (raw["symbol"].str.lower() == "usd")
    &
    (raw["contract"].notna())
    &
    (raw["trade_price"].notna())
].copy()


# Keep track of financial rows already matched
used_financial_rows = set()


# ==========================================================
# HELPER: MATCH FINANCIAL ROW
# ==========================================================

def find_financial_row(position_row):

    contract = position_row["contract"]
    timestamp = position_row["datetime"]
    trade_price = position_row["trade_price"]
    position_rowid = position_row["raw_rowid"]


    candidates = financial_rows[
        (financial_rows["contract"] == contract)
        &
        (financial_rows["datetime"] == timestamp)
    ].copy()


    if pd.notna(trade_price):

        candidates = candidates[
            (
                candidates["trade_price"]
                -
                trade_price
            ).abs()
            <
            1e-12
        ]


    if candidates.empty:

        return None


    # Remove rows already assigned to another execution
    candidates = candidates[
        ~candidates["raw_rowid"].isin(
            used_financial_rows
        )
    ]


    if candidates.empty:

        return None


    # Kraken execution-related rows normally sit next to
    # each other in the original export.
    candidates[
        "_distance"
    ] = (
        candidates["raw_rowid"]
        -
        position_rowid
    ).abs()


    matched = candidates.sort_values(
        "_distance"
    ).iloc[0]


    used_financial_rows.add(
        int(
            matched["raw_rowid"]
        )
    )


    return matched


# ==========================================================
# RECONSTRUCT KRAKEN-STYLE REALIZED TRADES
# ==========================================================

completed = []

trade_id = 1

reversal_closures = 0

unmatched_financials = 0


for _, row in positions.iterrows():

    position_change = float(
        row["change"]
    )

    position_after = float(
        row["new_balance"]
    )


    # ------------------------------------------------------
    # CALCULATE POSITION BEFORE THIS EXECUTION
    # ------------------------------------------------------
    #
    # after = before + change
    #
    # therefore:
    #
    # before = after - change
    #
    # ------------------------------------------------------

    position_before = (
        position_after
        -
        position_change
    )


    # No existing position = this execution only opens/adds
    if position_before == 0:

        continue


    # ======================================================
    # DETERMINE CLOSED QUANTITY
    # ======================================================

    closed_quantity = 0.0


    # ------------------------------------------------------
    # EXISTING LONG
    # ------------------------------------------------------

    if position_before > 0:

        # Selling reduces/closes the long
        if position_change < 0:

            closed_quantity = min(
                abs(position_change),
                abs(position_before)
            )


    # ------------------------------------------------------
    # EXISTING SHORT
    # ------------------------------------------------------

    elif position_before < 0:

        # Buying reduces/closes the short
        if position_change > 0:

            closed_quantity = min(
                abs(position_change),
                abs(position_before)
            )


    # Nothing was realized
    if closed_quantity <= 0:

        continue


    # ======================================================
    # DIRECTION OF THE POSITION BEING CLOSED
    # ======================================================

    direction = (
        "LONG"
        if position_before > 0
        else "SHORT"
    )


    # ======================================================
    # ENTRY / EXIT
    # ======================================================

    entry_price = (
        float(
            row[
                "new_average_entry_price"
            ]
        )
        if pd.notna(
            row[
                "new_average_entry_price"
            ]
        )
        else None
    )


    exit_price = (
        float(
            row[
                "trade_price"
            ]
        )
        if pd.notna(
            row[
                "trade_price"
            ]
        )
        else None
    )


    # ======================================================
    # MATCH KRAKEN REALIZED PNL ROW
    # ======================================================

    financial = find_financial_row(
        row
    )


    if financial is not None:

        gross_pnl = (
            float(
                financial[
                    "realized_pnl"
                ]
            )
            if pd.notna(
                financial[
                    "realized_pnl"
                ]
            )
            else 0.0
        )


        realized_funding = (
            float(
                financial[
                    "realized_funding"
                ]
            )
            if pd.notna(
                financial[
                    "realized_funding"
                ]
            )
            else 0.0
        )


        financial_rowid = int(
            financial[
                "raw_rowid"
            ]
        )

    else:

        gross_pnl = 0.0
        realized_funding = 0.0
        financial_rowid = None

        unmatched_financials += 1


    # ======================================================
    # LIQUIDATION FEE
    # ======================================================

    liquidation_fee = (
        float(
            row[
                "liquidation_fee"
            ]
        )
        if pd.notna(
            row[
                "liquidation_fee"
            ]
        )
        else 0.0
    )


    # ======================================================
    # NET PNL
    # ======================================================
    #
    # KFee is intentionally ignored.
    #
    # ======================================================

    net_pnl = (
        gross_pnl
        +
        realized_funding
        -
        liquidation_fee
    )


    if net_pnl > 0:

        result = "WIN"

    elif net_pnl < 0:

        result = "LOSS"

    else:

        result = "BREAKEVEN"


    # ======================================================
    # REVERSAL INFORMATION
    # ======================================================

    reversed_position = (
        position_after != 0
        and
        (
            (position_before > 0)
            !=
            (position_after > 0)
        )
    )


    if reversed_position:

        reversal_closures += 1


    # ======================================================
    # SAVE REALIZED TRADE
    # ======================================================

    completed.append(
        {
            "trade_id": trade_id,

            "contract": row[
                "contract"
            ],

            "direction": direction,

            # For filtering/reporting
            "close_time": row[
                "datetime"
            ],

            "quantity": closed_quantity,

            "average_entry_price": entry_price,

            "average_exit_price": exit_price,

            "gross_realized_pnl": gross_pnl,

            "realized_funding": realized_funding,

            "liquidation_fees": liquidation_fee,

            "net_pnl": net_pnl,

            "result": result,

            # Useful audit fields
            "position_before": position_before,

            "position_after": position_after,

            "position_change": position_change,

            "position_rowid": int(
                row[
                    "raw_rowid"
                ]
            ),

            "financial_rowid": financial_rowid,

            "reversal_close": (
                1
                if reversed_position
                else 0
            ),
        }
    )


    trade_id += 1


# ==========================================================
# CREATE DATAFRAME
# ==========================================================

trades = pd.DataFrame(
    completed
)


# ==========================================================
# STANDALONE FUNDING
# ==========================================================
#
# We deliberately DO NOT assign standalone funding-rate
# events to individual realized fills yet.
#
# They stay in raw_ledger and can later be analyzed
# separately.
#
# This keeps realized-trade validation clean against Kraken's
# closed-position screen.
#
# ==========================================================


# ==========================================================
# SAVE COMPLETED TRADES
# ==========================================================

if trades.empty:

    print(
        "No realized trades found."
    )

else:

    trades.to_sql(
        "completed_trades",
        conn,
        if_exists="replace",
        index=False
    )

    conn.commit()


# ==========================================================
# SUMMARY
# ==========================================================

print()
print("=" * 60)
print("KRAKEN-STYLE TRADE RECONSTRUCTION COMPLETE")
print("=" * 60)


print(
    f"Realized trades: "
    f"{len(trades)}"
)


if not trades.empty:

    long_count = (
        trades[
            "direction"
        ]
        ==
        "LONG"
    ).sum()


    short_count = (
        trades[
            "direction"
        ]
        ==
        "SHORT"
    ).sum()


    wins = (
        trades[
            "result"
        ]
        ==
        "WIN"
    ).sum()


    losses = (
        trades[
            "result"
        ]
        ==
        "LOSS"
    ).sum()


    breakeven = (
        trades[
            "result"
        ]
        ==
        "BREAKEVEN"
    ).sum()


    gross_pnl = trades[
        "gross_realized_pnl"
    ].sum()


    realized_funding = trades[
        "realized_funding"
    ].sum()


    liquidation_fees = trades[
        "liquidation_fees"
    ].sum()


    net_pnl = trades[
        "net_pnl"
    ].sum()


    print(
        f"Long trades: "
        f"{long_count}"
    )

    print(
        f"Short trades: "
        f"{short_count}"
    )

    print()

    print(
        f"Reversal closing fills: "
        f"{reversal_closures}"
    )

    print(
        f"Unmatched financial rows: "
        f"{unmatched_financials}"
    )

    print()

    print(
        f"Gross realized P&L: "
        f"${gross_pnl:.4f}"
    )

    print(
        f"Execution realized funding: "
        f"${realized_funding:.4f}"
    )

    print(
        f"Liquidation fees: "
        f"${liquidation_fees:.4f}"
    )

    print()

    print(
        f"NET P&L: "
        f"${net_pnl:.4f}"
    )

    print()

    print(
        f"Wins: "
        f"{wins}"
    )

    print(
        f"Losses: "
        f"{losses}"
    )

    print(
        f"Breakeven: "
        f"{breakeven}"
    )


    decided = (
        wins
        +
        losses
    )


    if decided > 0:

        win_rate = (
            wins
            /
            decided
            *
            100
        )

        print(
            f"Win rate: "
            f"{win_rate:.2f}%"
        )


# ==========================================================
# CLOSE DATABASE
# ==========================================================

conn.close()