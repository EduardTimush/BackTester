import ccxt
import pathlib
import time
import pandas as pd

class ParquetCandleStore:
    def __init__(self, storage_dir="data_parquet"):
        self.storage_dir = pathlib.Path(
        storage_dir)  # Стандарт python для работы с путями (подстраивает путь к файлу под операционную систему)
        self.storage_dir.mkdir(parents=True, exist_ok=True)  # Создание папки, если ее нет exist_ok предотвращает ошибку
        self.exchange = ccxt.gate({'enableRateLimit': True})  # Встроенный менеджер задержек, если есть лимиты у биржы. Иначе - БАН

    def _get_file_path(self, symbol: str, timeframe: str) -> pathlib.Path:
        clean_symbol = symbol.replace('/', '_').replace(':', '_')
        return self.storage_dir / f"{clean_symbol}_{timeframe}.parquet"  # Оказывается '/' этот символ в присутствии pathlib.Path выполняет роль os.join_path(). Это выглядит намного лаконичнее

    def fetch_and_update(self, symbol: str, timeframe: str, start_date="2013-03-25T00:00:00Z"):
        """Докачивает только недостающие свечи и обновляет Parquet-файл."""
        file_path = self._get_file_path(symbol, timeframe)
        existing_df = None
        since_ms = self.exchange.parse8601(start_date) # Перевод строковых данных "2021-01-01T00:00:00Z" формата ISO 8601 в миллисекунды

        # 1. Если файл уже есть — считываем его и определяем время последней свечи
        if file_path.exists():
            existing_df = pd.read_parquet(file_path)
            if not existing_df.empty:
                last_ts = existing_df['timestamp'].max() # Поиск последнего бара по времени
                since_ms = int(last_ts.timestamp() * 1000) + 1
                print(f"[{symbol}] Найден существующий файл. Докачка с {last_ts}")

        # 2. Скачиваем недостающие бары с биржи
        new_bars = []
        while True:
            try:
                bars = self.exchange.fetch_ohlcv(symbol, timeframe, since=since_ms, limit=1000)
                if not bars:
                    break

                new_bars.extend(bars)
                since_ms = bars[-1][0] + 1

                print(f"[{symbol}] Загружено {len(bars)} свечей...")

                # Если биржа вернула меньше лимита, значит мы дошли до текущего момента
                if len(bars) < 1000:
                    break

            except Exception as e:
                print(f"Ошибка получения данных: {e}")
                time.sleep(3)
                break

        # 3. Если появились новые данные — склеиваем и сохраняем
        if new_bars:
            new_df = pd.DataFrame(new_bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            new_df['timestamp'] = pd.to_datetime(new_df['timestamp'], unit='ms', utc=True)

            if existing_df is not None:
                full_df = pd.concat([existing_df, new_df], ignore_index=True)
            else:
                full_df = new_df

            # Удаляем случайные дубликаты по времени и сортируем
            full_df = full_df.drop_duplicates(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)

            # Сохраняем в Parquet со сжатием snappy
            full_df.to_parquet(file_path, engine='pyarrow', compression='snappy')
            print(f"[{symbol}] Файл успешно обновлен! Всего свечей: {len(full_df)}")
        else:
            print(f"[{symbol}] Данные уже в актуальном состоянии.")

    def load(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Моментальная загрузка данных из локального Parquet-файла."""
        file_path = self._get_file_path(symbol, timeframe)
        if not file_path.exists():
            raise FileNotFoundError(f"Файл {file_path} не найден. Сначала запустите fetch_and_update().")

        return pd.read_parquet(file_path)


# Пример использования
if __name__ == "__main__":
    store = ParquetCandleStore()

    # Сбор данных по нескольким парам
    symbols = ['BTC/USDT'] #, 'ETH/USDT', 'SOL/USDT'
    for sym in symbols:
        store.fetch_and_update(sym, timeframe='1w')

    # # Загрузка готового датасета под бэктестер
    # df_eth = store.load('ETH/USDT', '1h')
    # print(df_eth.head())