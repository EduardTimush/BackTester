import pandas as pd
import pandas_ta as ta
import numpy as np
from parquet_DC import ParquetCandleStore

# 1. Загрузка данных из Parquet
store = ParquetCandleStore()
df = store.load('BTC/USDT', '1h')

# --- НАСТРОЙКА ПЕРИОДА БЭКТЕСТА ---
START_DATE = "2026-02-01"
END_DATE = "2026-03-01"

# 2. Расчет индикаторов на ПОЛНОМ датасете (чтобы убрать NaN / прогреть EMA)
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

# 3. Фильтрация по датам ПОСЛЕ расчета индикаторов
df['timestamp'] = pd.to_datetime(df['timestamp'])

if START_DATE:
    df = df[df['timestamp'] >= pd.to_datetime(START_DATE, utc=True)]
if END_DATE:
    df = df[df['timestamp'] <= pd.to_datetime(END_DATE, utc=True)]

df = df.reset_index(drop=True)

if df.empty:
    raise ValueError(f"Нет данных за период с {START_DATE} по {END_DATE}")

print(f"Период бэктеста: с {df['timestamp'].min()} по {df['timestamp'].max()} (всего свечей: {len(df)})")

# 4. Подготовка NumPy массивов
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

# Сдвиг для поиска пересечения без утечки крайнего элемента (устраняем баг np.roll)
prev_fast = np.empty_like(ema_fast)
prev_slow = np.empty_like(ema_slow)

# Первую свечу заполняем исходным значением, чтобы не было фантомного пересечения
prev_fast[0] = ema_fast[0]
prev_slow[0] = ema_slow[0]

# Заполняем остальные элементы со сдвигом 1
prev_fast[1:] = ema_fast[:-1]
prev_slow[1:] = ema_slow[:-1]

# Векторное условие входа
buy_signals = (prev_fast <= prev_slow) & (ema_fast > ema_slow) & (rsi <= 60)
# Явно зануляем сигнал на самый первый бар выбранного отрезка
buy_signals[0] = False

# 5. Быстрый цикл бэктеста
balance = 1000.0
position = None
STOP_LOSS_PCT = 0.03
TAKE_PROFIT_PCT = 0.05
trades = []

n_rows = len(df)
for i in range(1, n_rows):

    # ПРОВЕРКА ВХОДА
    if position is None:
        if buy_signals[i]:
            entry_price = close[i]
            position = {
                'entry_price': entry_price,
                'tp_level': entry_price * (1 + TAKE_PROFIT_PCT),
                'sl_level': entry_price * (1 - STOP_LOSS_PCT),
                'time': timestamps[i]
            }

    # ПРОВЕРКА ВЫХОДА
    else:
        curr_high = high[i]
        curr_low = low[i]
        tp_level = position['tp_level']
        sl_level = position['sl_level']

        take_profit = curr_high >= tp_level
        stop_loss = curr_low <= sl_level

        if take_profit or stop_loss:
            # Консервативная оценка: если задело и TP и SL на одной свече — считаем SL
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

# Вывод результатов
profit_trades = [t['pnl'] for t in trades if t['pnl'] > 0]
lose_trades = [t['pnl'] for t in trades if t['pnl'] <= 0]

print(f"Итоговый баланс: ${balance:.2f}")
print(f"Всего сделок: {len(trades)}")
print(f"Профитные сделки: {len(profit_trades)} | Убыточные: {len(lose_trades)}")