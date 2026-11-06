# Crypto Strategy Backtester

> Python backtesting engine for crypto trading strategies. Test ideas on historical market data with realistic fees and slippage before risking real capital.

## Overview

Most trading strategies look great until they meet real market conditions. This backtester simulates a strategy on historical data the way it would have traded live: orders are filled with fees, positions are tracked, and the results are summarized with standard performance and risk metrics.

It is built as a self-initiated project to show how I approach strategy testing: reproducible runs, no lookahead bias, and clear reports.

## Features


- Historical data loading from GateAPI
- Event-driven simulation engine
- Fee model
- Position and PnL tracking long/short, leverage
- Performance metrics: total return, max drawdown, Sharpe ratio, win rate, profit factor
- Reports and charts: equity curve, drawdown, trade list 

## Methodology

A backtest is only useful if it is honest. This project handles the common pitfalls as follows:

- **Lookahead bias:** strategy only sees data available at the time of each candle
- **Costs:** exchange fees applied to every simulated fill
- **Reproducibility:** fixed inputs produce identical results

## Project structure


```
backtester/
├── data/           # historical data loaders
├── strategies/     # strategy definitions
├── engine/         # simulation engine
├── metrics/        # performance and risk metrics
├── reports/        # charts and output
├── tests/
├── requirements.txt
└── main.py
```

## Quick start

```bash
git clone https://github.com/EduardTimush/BackTester.git
cd BackTester
pip install -r requirements.txt


## Tech stack

Python, [pandas, NumPy, matplotlib / plotly, ccxt, ...]

## Limitations

- Backtest results do not guarantee future performance.

## Disclaimer

This software is an engineering tool for testing strategies. It is not investment advice, and it makes no promises about profit.

## Author

Built by Eduard Timush. Open to freelance work on backtesting, risk management and trading automation: [https://www.upwork.com/freelancers/~015fcbfd695964fa34?mp_source=share] or [timuseduard7@gmail.com].


