import pandas as pd
import pandas_ta as ta
import numpy as np
from parquet_DC import ParquetCandleStore

# 1. Load data from Parquet
store = ParquetCandleStore()
df = store.load('BTC/USDT', '1h')

# --- BACKTEST PERIOD SETTINGS ---
START_DATE = "2026-02-01"
END_DATE = "2026-03-01"

# 2. Calculate indicators on the FULL dataset (to remove NaN / warm up EMA)
df['ema_fast'] = ta.ema(df['close'], length=20)
df['ema_slow'] = ta.ema(df['close'], length=50)
df['rsi_14'] = ta.rsi(df['close'], length=14)
df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)

# ADX
adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
df['adx'] = adx_df["ADX_14"]

# MACD
macd = ta.macd(df['close'], fast=12,slow=26, signal=9)
df['macd'] = macd['MACD_12_26_9']
df['macd_hist'] = macd['MACDh_12_26_9']
df['macd_signal'] = macd['MACDs_12_26_9']

# Bollinger Bands
bb_df = ta.bbands(df['close'], length=20, lower_std=2.0, upper_std=2.0)
df['bb_lower'] = bb_df['BBL_20_2.0_2.0']
df['bb_middle'] = bb_df['BBM_20_2.0_2.0']
df['bb_upper'] = bb_df['BBU_20_2.0_2.0']

# 3. Filter by dates AFTER calculating indicators
df['timestamp'] = pd.to_datetime(df['timestamp'])

if START_DATE:
    df = df[df['timestamp'] >= pd.to_datetime(START_DATE, utc=True)]
if END_DATE:
    df = df[df['timestamp'] <= pd.to_datetime(END_DATE, utc=True)]

df = df.reset_index(drop=True)

if df.empty:
    raise ValueError(f"No data for the period from {START_DATE} to {END_DATE}")

print(f"Backtest period: from {df['timestamp'].min()} to {df['timestamp'].max()} (total candles: {len(df)})")

# 4. Prepare NumPy arrays
ema_fast = df['ema_fast'].to_numpy()
ema_slow = df['ema_slow'].to_numpy()
rsi = df['rsi_14'].to_numpy()
adx = df['adx'].to_numpy()
macd = df['macd'].to_numpy()
macd_hist = df['macd_hist'].to_numpy()
macd_signal = df['macd_signal'].to_numpy()
bb_lower = df['bb_lower'].to_numpy()
bb_middle = df['bb_middle'].to_numpy()
bb_upper = df['bb_upper'].to_numpy()


high = df['high'].to_numpy()
low = df['low'].to_numpy()
close = df['close'].to_numpy()
timestamps = df['timestamp'].to_numpy()

# Shift to detect the crossover without leaking the edge element (fixes the np.roll bug)
prev_fast = np.empty_like(ema_fast)
prev_slow = np.empty_like(ema_slow)

# Fill the first candle with the original value to avoid a phantom crossover
prev_fast[0] = ema_fast[0]
prev_slow[0] = ema_slow[0]

# Fill the remaining elements with a shift of 1
prev_fast[1:] = ema_fast[:-1]
prev_slow[1:] = ema_slow[:-1]

# Vectorized entry condition
buy_signals = (prev_fast <= prev_slow) & (ema_fast > ema_slow) & (rsi <= 60)
# Explicitly zero out the signal on the very first bar of the selected range
buy_signals[0] = False

# 5. Fast backtest loop
balance = 1000.0
position = None
STOP_LOSS_PCT = 0.03
TAKE_PROFIT_PCT = 0.05
trades = []

n_rows = len(df)
for i in range(1, n_rows):

    # ENTRY CHECK
    if position is None:
        if buy_signals[i]:
            entry_price = close[i]
            position = {
                'entry_price': entry_price,
                'tp_level': entry_price * (1 + TAKE_PROFIT_PCT),
                'sl_level': entry_price * (1 - STOP_LOSS_PCT),
                'time': timestamps[i]
            }

    # EXIT CHECK
    else:
        curr_high = high[i]
        curr_low = low[i]
        tp_level = position['tp_level']
        sl_level = position['sl_level']

        take_profit = curr_high >= tp_level
        stop_loss = curr_low <= sl_level

        if take_profit or stop_loss:
            # Conservative estimate: if both TP and SL are hit on the same candle, assume SL
            exit_price = sl_level if (stop_loss and take_profit) else (tp_level if take_profit else sl_level)

            pnl_pct = (exit_price - position['entry_price']) / position['entry_price']
            profit = balance * pnl_pct
            balance += profit

            trades.append({
                'entry': position['entry_price'],
                'exit': exit_price,
                'pnl': profit,
                'balance': balance
            })
            position = None

# Output results
profit_trades = [t['pnl'] for t in trades if t['pnl'] > 0]
lose_trades = [t['pnl'] for t in trades if t['pnl'] <= 0]

print(f"Final balance: ${balance:.2f}")
print(f"Total trades: {len(trades)}")
print(f"Profitable trades: {len(profit_trades)} | Losing trades: {len(lose_trades)}")
