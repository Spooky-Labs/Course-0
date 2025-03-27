#!/usr/bin/env python3
import backtrader as bt
import backtrader.analyzers as btanalyzers # Import analyzers
import yfinance as yf
import pandas as pd
import datetime  # For datetime objects
import sys
import os
import json  # Import the json library
import math # For checking NaN

from agent.agent import Agent

# Data directory within the container/workspace
# This data MUST be populated during the build process, not at runtime.
# CACHE_DIR = "/workspace/data" # Use absolute path matching build step
# OUTPUT_FILE = "/workspace/output.json"  # Output file path
CACHE_DIR = "data"
OUTPUT_FILE = "./output.json"  # Output file path

os.makedirs(CACHE_DIR, exist_ok=True)


def run_backtest(symbols, start_date, end_date, fast_period, slow_period, risk_free_rate=0.0):
    """
    Runs the backtest and returns results as a dictionary.
    Expects data to be pre-cached in CACHE_DIR.
    """
    results_data = {
        "parameters": {
            "symbols": symbols,
            "start_date": start_date,
            "end_date": end_date,
            "fast_period": fast_period,
            "slow_period": slow_period,
        },
        "results": {},
        "error": None,
    }

    try:
        cerebro = bt.Cerebro()
        cerebro.addstrategy(Agent, fast_period=fast_period, slow_period=slow_period)
        cerebro.broker.setcash(10000.0)

        # --- Add Analyzers ---
        cerebro.addanalyzer(btanalyzers.SharpeRatio, _name='sharpe', riskfreerate=risk_free_rate, timeframe=bt.TimeFrame.Days, compression=1) # Adjust timeframe/compression as needed
        # cerebro.addanalyzer(btanalyzers.SortinoRatio, _name='sortino', riskfreerate=risk_free_rate) # Added Sortino
        cerebro.addanalyzer(btanalyzers.DrawDown, _name='drawdown')
        cerebro.addanalyzer(btanalyzers.TradeAnalyzer, _name='trades')
        cerebro.addanalyzer(btanalyzers.Returns, _name='returns')
        cerebro.addanalyzer(btanalyzers.Calmar, _name='calmar') # Added Calmar
        cerebro.addanalyzer(btanalyzers.SQN, _name='sqn') # Added SQN
        cerebro.addanalyzer(btanalyzers.AnnualReturn, _name='annualreturn') # Added AnnualReturn

        # Add more analyzers here if desired (e.g., SQN)
        # cerebro.addanalyzer(btanalyzers.SQN, _name='sqn')

        for symbol in symbols:
            # Download data from cache or internet
            cache_file = os.path.join(CACHE_DIR, f"{symbol}_{start_date}_{end_date}.pkl")
            if not os.path.exists(cache_file):
                # Keeping these lines for when we need to download more symbols from Yahoo Finance.
                # Uncomment lines 48 & 49 and then comment line 52 when running outside.
                data = yf.download(symbol, start=start_date, end=end_date)
                data.to_pickle(cache_file)

                # CRITICAL: Fail if data is not pre-cached
                # raise FileNotFoundError(f"CRITICAL ERROR: Pre-cached data file not found: {cache_file}. Download must happen during build.")
            else:
                print(f"Loading cached data for {symbol} from {cache_file}")
                data = pd.read_pickle(cache_file)

            # Handle case where Yahoo returns multi-index columns
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = [col[0] for col in data.columns]

            # Create a properly structured dataframe with standard column names
            feed_data = pd.DataFrame(index=data.index)

            # Map standard column names - ensure all required fields exist
            if "Open" in data.columns:
                feed_data["open"] = data["Open"]
            if "High" in data.columns:
                feed_data["high"] = data["High"]
            if "Low" in data.columns:
                feed_data["low"] = data["Low"]
            if "Close" in data.columns:
                feed_data["close"] = data["Close"]
            if "Volume" in data.columns:
                feed_data["volume"] = data["Volume"]

            # Add a dummy openinterest column (required by backtrader)
            feed_data["openinterest"] = 0

            # Create PandasData feed with explicit column mapping
            feed = bt.feeds.PandasData(dataname=feed_data, name=symbol)
            cerebro.adddata(feed)

        # Run backtest
        print("Running backtest...")
        initial_value = cerebro.broker.getvalue()
        results = cerebro.run()
        final_value = cerebro.broker.getvalue()
        return_pct = ((final_value - initial_value) / initial_value) * 100 if initial_value != 0 else 0
        print("Backtest finished.")
        
        # --- Retrieve and format analysis results ---
        strategyResult = results[0] # Get the first strategy instance
        sharpe_analysis = strategyResult.analyzers.sharpe.get_analysis()
        # sortino_analysis = strategyResult.analyzers.sortino.get_analysis() # Get Sortino
        drawdown_analysis = strategyResult.analyzers.drawdown.get_analysis()
        trade_analysis = strategyResult.analyzers.trades.get_analysis()
        returns_analysis = strategyResult.analyzers.returns.get_analysis()
        calmar_analysis = strategyResult.analyzers.calmar.get_analysis() # Get Calmar
        sqn_analysis = strategyResult.analyzers.sqn.get_analysis() # Get SQN
        annual_return_analysis = strategyResult.analyzers.annualreturn.get_analysis() # Get AnnualReturn

        # Helper function to safely get metric, handling None analysis objects
        def safe_get(analysis, keys, default=None):
            if analysis is None: return default
            if not isinstance(keys, (list, tuple)): keys = [keys]
            val = analysis
            try:
                for k in keys:
                    if isinstance(val, dict): val = val.get(k)
                    else: val = getattr(val, k, None)
                    if val is None: return default
                # Check for NaN specifically if the result might be float
                if isinstance(val, float) and math.isnan(val): return default
                return val
            except (AttributeError, KeyError):
                return default

        # Consolidate results
        results_data["results"] = {
            "initial_value": initial_value,
            "final_value": final_value,
            "return_pct": return_pct,
            "annualized_return_pct": safe_get(returns_analysis, 'rannually'),

            # Risk-Adjusted
            "sharpe_ratio": safe_get(sharpe_analysis, 'sharperatio'),
            # "sortino_ratio": safe_get(sortino_analysis, 'sortinoratio'), # Added
            "calmar_ratio": safe_get(calmar_analysis, 'calmar'),      # Added
            "sqn": safe_get(sqn_analysis, 'sqn'),                    # Added

            # Drawdown
            "max_drawdown_pct": safe_get(drawdown_analysis, ['max', 'drawdown']),
            "max_drawdown_money": safe_get(drawdown_analysis, ['max', 'moneydown']),
            "max_drawdown_duration_bars": safe_get(drawdown_analysis, ['max', 'len']), # Added duration

            # Trade Stats
            "total_trades": safe_get(trade_analysis, ['total', 'total'], 0),
            "trades_open": safe_get(trade_analysis, ['total', 'open'], 0),
            "trades_closed": safe_get(trade_analysis, ['total', 'closed'], 0),
            "win_trades": safe_get(trade_analysis, ['won', 'total'], 0),
            "loss_trades": safe_get(trade_analysis, ['lost', 'total'], 0),
            "win_rate_pct": (safe_get(trade_analysis, ['won', 'total'], 0) / safe_get(trade_analysis, ['total', 'closed'], 1) * 100) \
                            if safe_get(trade_analysis, ['total', 'closed']) > 0 else 0, # Avoid division by zero
            "total_net_pnl": safe_get(trade_analysis, ['pnl', 'net', 'total'], 0),
            "average_win_pnl": safe_get(trade_analysis, ['won', 'pnl', 'average'], 0),
            "average_loss_pnl": safe_get(trade_analysis, ['lost', 'pnl', 'average'], 0),
            "profit_factor": abs(safe_get(trade_analysis, ['won', 'pnl', 'total'], 0) / safe_get(trade_analysis, ['lost', 'pnl', 'total'], 1)) \
                             if safe_get(trade_analysis, ['lost', 'pnl', 'total']) != 0 else None, # Avoid division by zero
            "max_consecutive_wins": safe_get(trade_analysis, ['streak', 'won', 'longest'], 0), # Added
            "max_consecutive_losses": safe_get(trade_analysis, ['streak', 'lost', 'longest'], 0), # Added
            "average_trade_duration_bars": safe_get(trade_analysis, ['len', 'average']), # Added duration

            # Annual Returns (dictionary)
            "annual_returns": annual_return_analysis, # Added

        }

        # --- Print Summary --- (Optional - can remove if not needed)
        print("\n--- Backtest Summary ---")
        print(f"Initial Portfolio Value: ${initial_value:.2f}")
        print(f"Final Portfolio Value: ${final_value:.2f}")
        # ... (keep or remove other summary prints as desired) ...
        print(f"Total Trades Closed: {results_data['results']['trades_closed']}")
        print(f"Win Rate: {results_data['results']['win_rate_pct']:.2f}%")
        print(f"Total Net PnL: ${results_data['results']['total_net_pnl']:.2f}")
        print("-" * 24)

    except Exception as e:
        print(f"ERROR during backtest: {e}", file=sys.stderr)
        results_data["error"] = str(e)
        # Re-raise the exception so the script exits with an error
        raise
    
    return results_data

def save_results_to_json(filepath, data):
    """Saves the results dictionary to a JSON file."""
    print(f"Attempting to save results to {filepath}...")
    try:
        # Ensure the directory exists (though /workspace should always exist in Cloud Build)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4) # Use indent for readability
        print(f"Successfully saved results to {filepath}")
    except Exception as e:
        print(f"ERROR saving results to {filepath}: {e}", file=sys.stderr)
        # Re-raise the exception to indicate failure
        raise


if __name__ == "__main__":
    # symbols = ["AAPL", "MSFT", "X", "SUN", "T", "COF", "F", "FORD"]
    with open("symbols.txt", "r") as file:
        lines = file.readlines()  # Read all lines into a list
        symbols = [line for line in lines]

    start_date = "2020-01-01"
    end_date = "2025-03-25"
    # end_date = datetime.datetime.now().strftime('%Y-%m-%d') # Use current date for end
    fast_period = 10
    slow_period = 30
    # Define risk-free rate for Sharpe Ratio (e.g., 0% or approximate T-bill rate)
    risk_free_rate = 0.01 # Example: 1% annual rate

    final_results = {}
    exit_code = 0

    try:
        # Run the backtest
        final_results = run_backtest(
            symbols, start_date, end_date,
            fast_period, slow_period,
            risk_free_rate=risk_free_rate
        )
        # Save results to JSON
        save_results_to_json(OUTPUT_FILE, final_results)

    except Exception as e:
        # If any part fails, try to save an error state (optional)
        if not final_results: # If run_backtest failed before returning
             final_results = { "parameters": { "symbols": symbols, "start_date": start_date, "end_date": end_date}, "error": f"Script failed early: {e}" }
        elif not final_results.get("error"): # If run_backtest succeeded but saving failed
             final_results["error"] = f"Failed to save results: {e}"
        # Try saving error state (best effort)
        try:
            save_results_to_json(OUTPUT_FILE, final_results)
        except:
             print("Failed even to save error state to JSON.", file=sys.stderr)
        exit_code = 1 # Signal failure to Cloud Build

    print(f"Exiting with code {exit_code}")
    sys.exit(exit_code) # Ensure Cloud Build knows if the step succeeded or failed