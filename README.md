# International Cost of Capital App

A Streamlit app that compares project cost of equity, cost of debt, and WACC in USD and a selected country's currency.

## Method

1. Relever beta: `βL = βU × [1 + (1 − T) × D/E]`
2. USD cost of equity: `Ke,USD = U.S. 10Y yield + βL × ERP`
3. USD debt cost: `Kd,USD = U.S. 10Y yield + BBB spread`
4. Currency translation factor: `F = (1 + foreign 10Y yield) / (1 + U.S. 10Y yield)`
5. Foreign equity cost: `Ke,FX = (1 + Ke,USD) × F − 1`
6. Auto foreign BBB spread: `s,FX = s,USD × F`; foreign debt cost: `Kd,FX = foreign 10Y yield + s,FX`
7. WACC: `(E/V × Ke) + (D/V × Kd × (1 − T))`

This translation makes the two currency results identical when government yields are equal and shared inputs are unchanged. These formulas match the supplied class packet. The included Colombia test reproduces approximately 8.5265% USD WACC and 16.0670% COP WACC.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Data sources

- Damodaran industry betas: https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls
- OECD corporate tax rates: https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/full-report/statutory-corporate-income-tax-rates_440f9286.html#chapter-d1e2342-08e74a33fb
- Damodaran BBB spread: https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html
- Trading Economics government bond yields: https://tradingeconomics.com/bonds

## Deployment

Create a public GitHub repository, upload `app.py`, `requirements.txt`, and `README.md`, then connect the repository at https://share.streamlit.io.

## Important limitation

OECD and Trading Economics may change their page structure or block automated requests. The app shows whether each source was retrieved live or from fallback values and supports manual overrides. Verify every displayed input before submitting the assignment.
