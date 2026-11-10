import ccxt
import pathlib
import time
import pandas as pd

class ParquetCandleStore:
    def __init__(self, storage_dir="data_parquet"):
        self.storage_dir = pathlib.Path(
        storage_dir)  # Python standard for working with paths (adapts the file path to the operating system)
        self.storage_dir.mkdir(parents=True, exist_ok=True)  # Create the folder if it doesn't exist; exist_ok prevents an error
        self.exchange = ccxt.gate({'enableRateLimit': True})  # Built-in delay manager in case the exchange has rate limits. Otherwise - BAN

    def _get_file_path(self, symbol: str, timeframe: str) -> pathlib.Path:
        clean_symbol = symbol.replace('/', '_').replace(':', '_')
        return self.storage_dir / f"{clean_symbol}_{timeframe}.parquet"  # It turns out that the '/' symbol, in the presence of pathlib.Path, acts as os.join_path(). This looks much more concise

    def fetch_and_update(self, symbol: str, timeframe: str, start_date="2013-03-25T00:00:00Z"):
        """Downloads only the missing candles and updates the Parquet file."""
        file_path = self._get_file_path(symbol, timeframe)
        existing_df = None
        since_ms = self.exchange.parse8601(start_date) # Convert string data "2021-01-01T00:00:00Z" in ISO 8601 format to milliseconds

        # 1. If the file already exists, read it and determine the time of the last candle
        if file_path.exists():
            existing_df = pd.read_parquet(file_path)
            if not existing_df.empty:
                last_ts = existing_df['timestamp'].max() # Find the last bar by time
                since_ms = int(last_ts.timestamp() * 1000) + 1
                print(f"[{symbol}] Existing file found. Resuming download from {last_ts}")

        # 2. Download the missing bars from the exchange
        new_bars = []
        while True:
            try:
                bars = self.exchange.fetch_ohlcv(symbol, timeframe, since=since_ms, limit=1000)
                if not bars:
                    break

                new_bars.extend(bars)
                since_ms = bars[-1][0] + 1

                print(f"[{symbol}] Loaded {len(bars)} candles...")

                # If the exchange returned fewer than the limit, we have reached the current moment
                if len(bars) < 1000:
                    break

            except Exception as e:
                print(f"Error fetching data: {e}")
                time.sleep(3)
                break

        # 3. If there is new data, merge and save it
        if new_bars:
            new_df = pd.DataFrame(new_bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            new_df['timestamp'] = pd.to_datetime(new_df['timestamp'], unit='ms', utc=True)

            if existing_df is not None:
                full_df = pd.concat([existing_df, new_df], ignore_index=True)
            else:
                full_df = new_df

            # Remove accidental duplicates by time and sort
            full_df = full_df.drop_duplicates(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)

            # Save to Parquet with snappy compression
            full_df.to_parquet(file_path, engine='pyarrow', compression='snappy')
            print(f"[{symbol}] File updated successfully! Total candles: {len(full_df)}")
        else:
            print(f"[{symbol}] Data is already up to date.")

    def load(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Instant loading of data from a local Parquet file."""
        file_path = self._get_file_path(symbol, timeframe)
        if not file_path.exists():
            raise FileNotFoundError(f"File {file_path} not found. Run fetch_and_update() first.")

        return pd.read_parquet(file_path)


# Usage example
if __name__ == "__main__":
    store = ParquetCandleStore()

    # Collect data for several pairs
    symbols = ['BTC/USDT'] #, 'ETH/USDT', 'SOL/USDT'
    for sym in symbols:
        store.fetch_and_update(sym, timeframe='1w')

    # # Load the ready-made dataset for the backtester
    # df_eth = store.load('ETH/USDT', '1h')
    # print(df_eth.head())
