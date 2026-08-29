from pathlib import Path
from datetime import date, timedelta
import sqlite3
import subprocess
import sys

import pandas as pd
import streamlit as st


# ==========================================================
# PAGE CONFIG
# ==========================================================

st.set_page_config(
    page_title="Kraken Trade Analysis",
    layout="wide",
)


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
# DATABASE CONNECTION
# ==========================================================

def get_connection():

    return sqlite3.connect(
        DATABASE_FILE,
        check_same_thread=False,
        timeout=30,
    )


# ==========================================================
# DATABASE CHECK
# ==========================================================

if not DATABASE_FILE.exists():

    st.error(
        f"Database not found:\n{DATABASE_FILE}"
    )

    st.stop()


# ==========================================================
# CLEAN CONTRACT NAME FOR DISPLAY
# ==========================================================

def display_contract(contract):

    if contract == "All":
        return "All"

    return (
        str(contract)
        .replace("pf_", "")
        .replace("pi_", "")
        .upper()
    )


# ==========================================================
# LOAD FILTER OPTIONS
# ==========================================================

@st.cache_data
def load_filter_data():

    conn = get_connection()

    contracts = pd.read_sql_query(
        """
        SELECT DISTINCT contract
        FROM completed_trades
        WHERE contract IS NOT NULL
        ORDER BY contract
        """,
        conn
    )

    directions = pd.read_sql_query(
        """
        SELECT DISTINCT direction
        FROM completed_trades
        WHERE direction IS NOT NULL
        ORDER BY direction
        """,
        conn
    )

    date_range = pd.read_sql_query(
        """
        SELECT
            MIN(DATE(close_time)) AS min_date,
            MAX(DATE(close_time)) AS max_date
        FROM completed_trades
        """,
        conn
    )

    conn.close()

    return (
        contracts,
        directions,
        date_range
    )


# ==========================================================
# LOAD FILTERED TRADES
# ==========================================================

@st.cache_data
def load_trades(
    start_date,
    end_date,
    contract,
    direction
):

    conn = get_connection()

    query = """
        SELECT
            trade_id,
            contract,
            direction,
            close_time,
            quantity,
            average_entry_price,
            average_exit_price,
            gross_realized_pnl,
            realized_funding,
            liquidation_fees,
            net_pnl,
            result,
            reversal_close
        FROM completed_trades
        WHERE DATE(close_time) >= ?
          AND DATE(close_time) <= ?
    """

    params = [
        str(start_date),
        str(end_date),
    ]


    # ------------------------------------------------------
    # CONTRACT FILTER
    # ------------------------------------------------------

    if contract != "All":

        query += """
            AND contract = ?
        """

        params.append(
            contract
        )


    # ------------------------------------------------------
    # DIRECTION FILTER
    # ------------------------------------------------------

    if direction != "All":

        query += """
            AND direction = ?
        """

        params.append(
            direction
        )


    query += """
        ORDER BY close_time ASC, trade_id ASC
    """


    trades = pd.read_sql_query(
        query,
        conn,
        params=params
    )

    conn.close()

    return trades


# ==========================================================
# HEADER
# ==========================================================

header_left, header_right = st.columns(
    [5, 1]
)


with header_left:

    st.title(
        "Kraken Trade Analysis"
    )

    st.caption(
        "Analysis based on Kraken Futures "
        "realized closing trades."
    )


with header_right:

    st.write("")
    st.write("")

    if st.button("🔄 Refresh Data"):

        with st.spinner("Refreshing Kraken data..."):

            try:
                subprocess.run(
                    [
                        sys.executable,
                        str(PROJECT_ROOT / "scripts" / "download_kraken_data.py"),
                    ],
                    cwd=PROJECT_ROOT,
                    check=True,
                )

                subprocess.run(
                    [
                        sys.executable,
                        str(PROJECT_ROOT / "scripts" / "import_kraken_data.py"),
                    ],
                    cwd=PROJECT_ROOT,
                    check=True,
                )

                subprocess.run(
                    [
                        sys.executable,
                        str(PROJECT_ROOT / "scripts" / "build_trades.py"),
                    ],
                    cwd=PROJECT_ROOT,
                    check=True,
                )

                st.cache_data.clear()
                st.success("Data refreshed successfully.")
                st.rerun()

            except subprocess.CalledProcessError as error:

                st.error(
                    f"Refresh failed: {error}"
                )


# ==========================================================
# LOAD FILTER DATA
# ==========================================================

try:

    (
        contracts_df,
        directions_df,
        date_range_df
    ) = load_filter_data()

except Exception as error:

    st.error(
        "Could not read completed_trades."
    )

    st.exception(
        error
    )

    st.stop()


# ==========================================================
# CHECK AVAILABLE DATA
# ==========================================================

if (
    date_range_df.empty
    or
    date_range_df.loc[
        0,
        "min_date"
    ] is None
    or
    date_range_df.loc[
        0,
        "max_date"
    ] is None
):

    st.warning(
        "No realized trades are available."
    )

    st.stop()


# ==========================================================
# AVAILABLE DATE RANGE
# ==========================================================

min_date = pd.to_datetime(
    date_range_df.loc[
        0,
        "min_date"
    ]
).date()


max_date = pd.to_datetime(
    date_range_df.loc[
        0,
        "max_date"
    ]
).date()


# ==========================================================
# DYNAMIC DEFAULT PERIOD
# ==========================================================
#
# Automatically starts from the first day
# of the latest month in the database.
#
# Nothing is hardcoded.
#
# ==========================================================

default_start_date = max_date.replace(
    day=1
)

default_end_date = max_date


# ==========================================================
# DYNAMIC FILTER VALUES
# ==========================================================

contracts = (
    ["All"]
    +
    contracts_df[
        "contract"
    ].tolist()
)


directions = (
    ["All"]
    +
    directions_df[
        "direction"
    ].tolist()
)


# ==========================================================
# FILTERS
# ==========================================================

st.subheader(
    "Filters"
)


# ----------------------------------------------------------
# QUICK PERIOD FILTER
# ----------------------------------------------------------

period_option = st.selectbox(
    "Quick Period",
    [
        "Custom",
        "Today",
        "This Week",
        "Last Week",
        "This Month",
        "Last Month",
        "Last 3 Months",
        "This Year",
    ],
    index=4,
)


today = date.today()


if period_option == "Today":

    quick_start_date = today
    quick_end_date = today


elif period_option == "This Week":

    quick_start_date = (
        today
        -
        timedelta(days=today.weekday())
    )

    quick_end_date = today


elif period_option == "Last Week":

    this_week_start = (
        today
        -
        timedelta(days=today.weekday())
    )

    quick_start_date = (
        this_week_start
        -
        timedelta(days=7)
    )

    quick_end_date = (
        this_week_start
        -
        timedelta(days=1)
    )


elif period_option == "This Month":

    quick_start_date = today.replace(
        day=1
    )

    quick_end_date = today


elif period_option == "Last Month":

    this_month_start = today.replace(
        day=1
    )

    quick_end_date = (
        this_month_start
        -
        timedelta(days=1)
    )

    quick_start_date = quick_end_date.replace(
        day=1
    )


elif period_option == "Last 3 Months":

    quick_start_date = (
        pd.Timestamp(today)
        -
        pd.DateOffset(months=3)
    ).date()

    quick_end_date = today


elif period_option == "This Year":

    quick_start_date = date(
        today.year,
        1,
        1
    )

    quick_end_date = today


else:

    quick_start_date = default_start_date
    quick_end_date = default_end_date


col1, col2, col3, col4 = st.columns(
    4
)


with col1:

    start_date = st.date_input(
        "From",
        value=quick_start_date,
        format="DD/MM/YYYY",
        key=f"start_date_{period_option}",
        disabled=period_option != "Custom",
    )


with col2:

    end_date = st.date_input(
        "To",
        value=quick_end_date,
        format="DD/MM/YYYY",
        key=f"end_date_{period_option}",
        disabled=period_option != "Custom",
    )


with col3:

    selected_contract = st.selectbox(
        "Contract",
        contracts,
        format_func=display_contract
    )


with col4:

    selected_direction = st.selectbox(
        "Direction",
        directions
    )


# ==========================================================
# DATE VALIDATION
# ==========================================================

if start_date > end_date:

    st.error(
        "The From date cannot be after the To date."
    )

    st.stop()


# ==========================================================
# LOAD FILTERED DATA
# ==========================================================

trades = load_trades(
    start_date=start_date,
    end_date=end_date,
    contract=selected_contract,
    direction=selected_direction,
)


# ==========================================================
# NO RESULTS
# ==========================================================

if trades.empty:

    st.divider()

    st.warning(
        "No realized trades match "
        "the selected filters."
    )

    st.stop()


# ==========================================================
# NUMERIC CLEANING
# ==========================================================

numeric_columns = [
    "quantity",
    "average_entry_price",
    "average_exit_price",
    "gross_realized_pnl",
    "realized_funding",
    "liquidation_fees",
    "net_pnl",
]


for column in numeric_columns:

    trades[column] = pd.to_numeric(
        trades[column],
        errors="coerce"
    ).fillna(0)


# ==========================================================
# PERFORMANCE CALCULATIONS
# ==========================================================

trade_count = len(
    trades
)


wins = (
    trades["result"] == "WIN"
).sum()


losses = (
    trades["result"] == "LOSS"
).sum()


breakeven = (
    trades["result"] == "BREAKEVEN"
).sum()


decided = (
    wins
    +
    losses
)


win_rate = (
    wins
    /
    decided
    *
    100
    if decided > 0
    else 0
)


gross_pnl = (
    trades[
        "gross_realized_pnl"
    ].sum()
)


funding = (
    trades[
        "realized_funding"
    ].sum()
)


liquidation_fees = (
    trades[
        "liquidation_fees"
    ].sum()
)


net_pnl = (
    trades[
        "net_pnl"
    ].sum()
)


# ==========================================================
# PERFORMANCE
# ==========================================================

st.divider()

st.subheader(
    "Performance"
)


m1, m2, m3, m4 = st.columns(
    4
)


m1.metric(
    "Net P&L",
    f"${net_pnl:,.2f}"
)


m2.metric(
    "Trades",
    f"{trade_count}"
)


m3.metric(
    "Win Rate",
    f"{win_rate:.2f}%"
)


m4.metric(
    "Wins / Losses",
    f"{wins} / {losses}"
)


m5, m6, m7, m8 = st.columns(
    4
)


m5.metric(
    "Gross P&L",
    f"${gross_pnl:,.2f}"
)


m6.metric(
    "Execution Funding",
    f"${funding:,.2f}"
)


m7.metric(
    "Liquidation Fees",
    f"${liquidation_fees:,.2f}"
)


m8.metric(
    "Breakeven",
    f"{breakeven}"
)


# ==========================================================
# STATISTICS
# ==========================================================

st.divider()

st.subheader(
    "Statistics"
)


winning_trades = trades[
    trades["net_pnl"] > 0
]


losing_trades = trades[
    trades["net_pnl"] < 0
]


average_trade = (
    trades[
        "net_pnl"
    ].mean()
)


average_win = (
    winning_trades[
        "net_pnl"
    ].mean()
    if not winning_trades.empty
    else 0
)


average_loss = (
    losing_trades[
        "net_pnl"
    ].mean()
    if not losing_trades.empty
    else 0
)


best_trade = (
    trades[
        "net_pnl"
    ].max()
)


worst_trade = (
    trades[
        "net_pnl"
    ].min()
)


gross_profit = (
    winning_trades[
        "net_pnl"
    ].sum()
)


gross_loss = abs(
    losing_trades[
        "net_pnl"
    ].sum()
)


profit_factor = (
    gross_profit
    /
    gross_loss
    if gross_loss > 0
    else 0
)


s1, s2, s3 = st.columns(
    3
)


s1.metric(
    "Average Trade",
    f"${average_trade:,.2f}"
)


s2.metric(
    "Average Win",
    f"${average_win:,.2f}"
)


s3.metric(
    "Average Loss",
    f"${average_loss:,.2f}"
)


s4, s5, s6 = st.columns(
    3
)


s4.metric(
    "Best Trade",
    f"${best_trade:,.2f}"
)


s5.metric(
    "Worst Trade",
    f"${worst_trade:,.2f}"
)


s6.metric(
    "Profit Factor",
    f"{profit_factor:.2f}"
)


# ==========================================================
# TRADE TABLE
# ==========================================================

st.divider()

st.subheader(
    "Realized Trades"
)


display = trades.copy()


# ----------------------------------------------------------
# CLEAN CONTRACT NAME
# ----------------------------------------------------------

display["contract"] = (
    display["contract"]
    .apply(
        display_contract
    )
)


# ----------------------------------------------------------
# CLEAN DATE
# ----------------------------------------------------------

display["close_time"] = pd.to_datetime(
    display["close_time"],
    errors="coerce"
)


display["close_time"] = (
    display["close_time"]
    .dt.strftime(
        "%d/%m/%Y %H:%M:%S"
    )
)


# ----------------------------------------------------------
# RENAME COLUMNS
# ----------------------------------------------------------

display = display.rename(
    columns={
        "trade_id": "Trade",
        "contract": "Contract",
        "direction": "Side",
        "close_time": "Closed",
        "quantity": "Quantity",
        "average_entry_price": "Entry",
        "average_exit_price": "Exit",
        "gross_realized_pnl": "Gross P&L",
        "realized_funding": "Funding",
        "liquidation_fees": "Liquidation Fees",
        "net_pnl": "Net P&L",
        "result": "Result",
    }
)


display = display[
    [
        "Trade",
        "Closed",
        "Contract",
        "Side",
        "Quantity",
        "Entry",
        "Exit",
        "Gross P&L",
        "Funding",
        "Liquidation Fees",
        "Net P&L",
        "Result",
    ]
]


# ==========================================================
# TABLE FORMATTING
# ==========================================================

st.dataframe(
    display,
    use_container_width=True,
    hide_index=True,
    column_config={

        "Quantity": st.column_config.NumberColumn(
            format="%.4f"
        ),

        "Entry": st.column_config.NumberColumn(
            format="%.8f"
        ),

        "Exit": st.column_config.NumberColumn(
            format="%.8f"
        ),

        "Gross P&L": st.column_config.NumberColumn(
            format="$%.4f"
        ),

        "Funding": st.column_config.NumberColumn(
            format="$%.4f"
        ),

        "Liquidation Fees": st.column_config.NumberColumn(
            format="$%.4f"
        ),

        "Net P&L": st.column_config.NumberColumn(
            format="$%.4f"
        ),
    }
)


# ==========================================================
# P&L BY TRADE
# ==========================================================

st.divider()

st.subheader(
    "P&L by Trade"
)


pnl_chart = trades[
    [
        "trade_id",
        "net_pnl"
    ]
].copy()


pnl_chart = pnl_chart.set_index(
    "trade_id"
)


pnl_chart = pnl_chart.rename(
    columns={
        "net_pnl": "Net P&L"
    }
)


st.bar_chart(
    pnl_chart
)


# ==========================================================
# CUMULATIVE P&L
# ==========================================================

st.subheader(
    "Cumulative P&L"
)


cumulative = trades[
    [
        "close_time",
        "net_pnl"
    ]
].copy()


cumulative[
    "close_time"
] = pd.to_datetime(
    cumulative[
        "close_time"
    ],
    errors="coerce"
)


cumulative = cumulative.sort_values(
    "close_time"
)


cumulative[
    "Cumulative P&L"
] = cumulative[
    "net_pnl"
].cumsum()


cumulative = cumulative.set_index(
    "close_time"
)


st.line_chart(
    cumulative[
        [
            "Cumulative P&L"
        ]
    ]
)


# ==========================================================
# DATA INFO
# ==========================================================

st.divider()


st.caption(
    f"Available period: "
    f"{min_date.strftime('%d/%m/%Y')} "
    f"→ "
    f"{max_date.strftime('%d/%m/%Y')}"
)

 
st.caption(
    f"Currently showing "
    f"{trade_count} realized Kraken trades."
)