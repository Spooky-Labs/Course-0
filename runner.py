#!/usr/bin/env python3
import backtrader as bt
import yfinance as yf
import pandas as pd
import datetime  # For datetime objects
import sys
import os
from agent import Agent

CACHE_DIR = "data"
os.makedirs(CACHE_DIR, exist_ok=True)

def run_backtest(symbols, start_date, end_date, fast_period, slow_period):
    cerebro = bt.Cerebro()
    cerebro.addstrategy(Agent, fast_period=fast_period, slow_period=slow_period)
    cerebro.broker.setcash(10000.0)
    
    for symbol in symbols:
        # Download data from cache or internet

        cache_file = os.path.join(CACHE_DIR, f"{symbol}_{start_date}_{end_date}.pkl")
        if os.path.exists(cache_file):
            print(f"Loading cached data for {symbol}...")
            data = pd.read_pickle(cache_file)
        else:
            data = yf.download(symbol, start=start_date, end=end_date)
            data.to_pickle(cache_file)
        
        # Handle case where Yahoo returns multi-index columns
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [col[0] for col in data.columns]
        
        # Create a properly structured dataframe with standard column names
        feed_data = pd.DataFrame(index=data.index)
        
        # Map standard column names - ensure all required fields exist
        if 'Open' in data.columns:
            feed_data['open'] = data['Open']
        if 'High' in data.columns:
            feed_data['high'] = data['High']
        if 'Low' in data.columns:
            feed_data['low'] = data['Low']
        if 'Close' in data.columns:
            feed_data['close'] = data['Close']
        if 'Volume' in data.columns:
            feed_data['volume'] = data['Volume']
        
        # Add a dummy openinterest column (required by backtrader)
        feed_data['openinterest'] = 0
        
        # Create PandasData feed with explicit column mapping
        feed = bt.feeds.PandasData(
            dataname=data,
            name=symbol
        )
        cerebro.adddata(feed)
    
    # Run backtest
    initial_value = cerebro.broker.getvalue()
    results = cerebro.run()
    final_value = cerebro.broker.getvalue()
    
    # Print results
    return_pct = ((final_value - initial_value) / initial_value) * 100
    print(f"Initial: ${initial_value:.2f}")
    print(f"Final: ${final_value:.2f}")
    print(f"Return: {return_pct:.2f}%")
    
    return final_value, return_pct

if __name__ == "__main__":
    symbols = ["AAPL", "MSFT", "X", "SUN", "T", "COF", "F", "FORD"]
    start_date = "1990-01-01"
    end_date = "2025-01-01"
    fast_period = 10
    slow_period = 30
    
    run_backtest(symbols, start_date, end_date, fast_period, slow_period)