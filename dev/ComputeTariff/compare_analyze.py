"""Compare new and old calculate_energy_cost implementations for identical output."""

import sys
import numpy as np
import pandas as pd
from pathlib import Path

# Project root (two levels up from dev/ComputeTariff/)
ROOT = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, ROOT)
# Local dev folder for the archived old implementation
sys.path.insert(0, str(Path(__file__).parent))

from doper.data.analyze import calculate_energy_cost as calculate_new
from analyze_old import calculate_energy_cost as calculate_old
from doper.data.tariff import get_e19_2020_tariff, get_e19_2018_tariff, get_b10_2026_tariff

# ── Synthetic data ────────────────────────────────────────────────────────────
np.random.seed(42)
ts = 15 # minutes
periods_per_day = int(60 / ts * 24)

# Two full months: Jan + Feb 2023 (non-leap)
idx = pd.date_range('2023-01-01', '2023-03-01', freq=f'{ts}min', inclusive='left')
n = len(idx)

rng = np.random.default_rng(42)
data = pd.DataFrame(index=idx)
for t in ['MPC', 'Base', 'BasePV']:
    data[t + '_Net Load [kW]'] = rng.uniform(50, 500, size=n)

# Data with negative loads to test export revenue
data_export = data.copy()
data_export['MPC_Net Load [kW]'] = rng.uniform(-200, 300, size=n) # mix of import/export

# Data with RTP column (can be positive or negative $/kWh)
data_rtp = data.copy()
data_rtp['RTP'] = rng.uniform(-0.05, 0.30, size=n) # real-time price [$/kWh]

# ── Tariffs ───────────────────────────────────────────────────────────────────
tariff_daytype = get_e19_2020_tariff() # has weekday/weekend
tariff_simple = get_e19_2018_tariff() # no weekday key
tariff_b10 = get_b10_2026_tariff() # PG&E B-10 2026

KWARGS_CASES = [
    {'label': 'daytype tariff, daily=False', 'kwargs': dict(
        tariff=tariff_daytype, types=['MPC', 'Base', 'BasePV'], ts=ts,
        tz='Etc/GMT+8', tz_local='America/Los_Angeles', daily=False,
    )},
    {'label': 'daytype tariff, daily=True', 'kwargs': dict(
        tariff=tariff_daytype, types=['MPC', 'Base', 'BasePV'], ts=ts,
        tz='Etc/GMT+8', tz_local='America/Los_Angeles', daily=True,
    )},
    {'label': 'simple tariff (no daytype)', 'kwargs': dict(
        tariff=tariff_simple, types=['MPC', 'Base'], ts=ts,
        tz='Etc/GMT+8', tz_local='America/Los_Angeles', daily=False,
    )},
    {'label': 'fullmonth=True', 'kwargs': dict(
        tariff=tariff_daytype, types=['MPC'], ts=ts,
        tz='Etc/GMT+8', tz_local='America/Los_Angeles', daily=False,
        fullmonth=True,
    )},
    {'label': 'b10-2026 tariff, daily=True', 'kwargs': dict(
        tariff=tariff_b10, types=['MPC', 'Base', 'BasePV'], ts=ts,
        tz='Etc/GMT+8', tz_local='America/Los_Angeles', daily=True,
    )},
    {'label': 'b10-2026 with export (negative loads), daily=True', 'data': data_export,
     'new_kwargs': dict(
        tariff=tariff_b10, types=['MPC'], ts=ts,
        tz='Etc/GMT+8', tz_local='America/Los_Angeles', daily=True,
    )},
    {'label': 'RTP column, daily=True', 'data': data_rtp,
     'new_kwargs': dict(
        tariff=tariff_daytype, types=['MPC', 'Base'], ts=ts,
        tz='Etc/GMT+8', tz_local='America/Los_Angeles', daily=True,
        rtp_col='RTP',
    )},
    # New-only cases (old function doesn't support these parameters)
    {'label': 'auto-detect types (types=None)', 'new_kwargs': dict(
        tariff=tariff_daytype, types=None, ts=ts,
        tz='Etc/GMT+8', tz_local='America/Los_Angeles', daily=False,
    ), 'old_kwargs': dict(
        tariff=tariff_daytype, types=['MPC', 'Base', 'BasePV'], ts=ts,
        tz='Etc/GMT+8', tz_local='America/Los_Angeles', daily=False,
    )},
    {'label': 'custom col_suffix', 'new_kwargs': dict(
        tariff=tariff_daytype, types=['MPC', 'Base', 'BasePV'],
        col_suffix='_Net Load [kW]', ts=ts,
        tz='Etc/GMT+8', tz_local='America/Los_Angeles', daily=False,
    ), 'old_kwargs': dict(
        tariff=tariff_daytype, types=['MPC', 'Base', 'BasePV'], ts=ts,
        tz='Etc/GMT+8', tz_local='America/Los_Angeles', daily=False,
    )},
]

# ── Comparison helper ─────────────────────────────────────────────────────────
def compare_frames(label, old, new):
    """Assert two DataFrames are numerically identical; print result."""
    # Align columns and index
    cols = sorted(old.columns.tolist())
    old = old[cols].sort_index()
    new = new[cols].sort_index()
    try:
        pd.testing.assert_frame_equal(old, new, check_like=False, rtol=1e-10)
        print(f'  PASS: {label}')
    except AssertionError as e:
        print(f'  FAIL: {label}')
        print(f'    {e}')

# ── Run cases ─────────────────────────────────────────────────────────────────
for case in KWARGS_CASES:
    label = case['label']
    print(f'Case: {label}')

    # Support separate old/new kwargs for cases with new-only parameters
    old_kwargs = case.get('old_kwargs', case.get('kwargs'))
    new_kwargs = case.get('new_kwargs', case.get('kwargs'))

    input_data = case.get('data', data).copy()
    result_old = calculate_old(input_data.copy(), **old_kwargs) if old_kwargs else None
    result_new = calculate_new(input_data, **new_kwargs)

    if result_old is None:
        # New-only case: verify run and spot-check key columns
        result = result_new if not isinstance(result_new, tuple) else result_new[0]
        export_cols = [c for c in result.columns if 'Export Revenue [$]' in c and 'Cum' not in c]
        rtp_cols = [c for c in result.columns if 'RTP Cost [$]' in c and 'Cum' not in c]
        net_cols = [c for c in result.columns if 'Net Energy Cost [$]' in c]
        if export_cols and net_cols:
            rev = result[export_cols]
            print(f'  PASS: Export Revenue [{rev.values.min():.2f}, {rev.values.max():.2f}] $')
        else:
            print(f'  FAIL: export or net-cost columns missing')
        if rtp_cols:
            rtp = result[rtp_cols]
            print(f'  PASS: RTP Cost [{rtp.values.min():.2f}, {rtp.values.max():.2f}] $')
    elif isinstance(result_old, tuple):
        cost_old, daily_old = result_old
        cost_new, daily_new = result_new
        compare_frames('cost', cost_old, cost_new)
        compare_frames('cost_daily', daily_old, daily_new)
    else:
        compare_frames('cost', result_old, result_new)

# ── Benchmark: one month of data ─────────────────────────────────────────────
import timeit

idx_1m = pd.date_range('2023-06-01', '2023-07-01', freq=f'{ts}min', inclusive='left')
data_1m = pd.DataFrame(index=idx_1m)
for t in ['MPC', 'Base', 'BasePV']:
    data_1m[t + '_Net Load [kW]'] = rng.uniform(50, 500, size=len(idx_1m))

bench_kwargs = dict(
    tariff=tariff_daytype, types=['MPC', 'Base', 'BasePV'], ts=ts,
    tz='Etc/GMT+8', tz_local='America/Los_Angeles', daily=True,
)
n_runs = 20
t_old = timeit.timeit(lambda: calculate_old(data_1m.copy(), **bench_kwargs), number=n_runs)
t_new = timeit.timeit(lambda: calculate_new(data_1m.copy(), **bench_kwargs), number=n_runs)

print(f'\nBenchmark ({n_runs} runs, 1 month of {ts}-min data, {len(idx_1m)} rows):')
print(f'  Old: {t_old/n_runs*1000:.1f} ms/call')
print(f'  New: {t_new/n_runs*1000:.1f} ms/call')
print(f'  Speedup: {t_old/t_new:.2f}x')
