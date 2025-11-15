# DVD Rental Analytics — Streamlit Dashboard

A polished, local-first Streamlit dashboard for exploring the **DVD Rental** CSV dataset.
Load your CSVs from a folder (e.g. `./data`) and the app will register them into an in-memory DuckDB and provide 25 built-in analytics queries, interactive Plotly visualizations, a saved-queries panel, and an Advanced SQL explorer.

---

## Key features

- Auto-load **all CSVs** from a folder and register them in DuckDB.
- 7 interactive tabs: Overview, Customers, Rentals & Stores, Categories & Films, Revenue, Actors, Advanced SQL.
- 25 converted DuckDB saved queries (one-click buttons) covering the analyses you provided (top spenders, monthly rentals, category revenue, ROI, loyalty tiers, etc.).
- Interactive Plotly visualizations: area charts, stacked bars, heatmaps, treemaps, sunbursts, violin/box, scatter, sankey, Pareto charts, rolling-average lines.
- Compact dashboard header with metric cards and quick actions.
- Advanced SQL explorer: run custom DuckDB SQL and plot results on the fly.
- Export CSVs of the registered tables.
- Single-file Streamlit app — runs locally (no cloud/remote compute required).

---

## Quick start

1. Clone your repo (or place `streamlit_dvd_dashboard.py` in a folder):

   ```bash
   git clone https://github.com/RobinMillford/Customer-Behavior-in-DVD-Rentals.git
   cd Customer-Behavior-in-DVD-Rentals
   ```

2. Create a virtual environment and install dependencies:

   ```bash
   python -m venv venv
   source venv/bin/activate        # macOS / Linux
   venv\Scripts\activate           # Windows PowerShell

   pip install -r requirements.txt
   ```

   Example `requirements.txt` (provided in repo):

   ```
   streamlit
   pandas
   duckdb
   plotly
   ```

   Optionally pin versions (see repo notes).

3. Put all CSV files in `./data` (or any folder) — file names preserved.

4. Run the dashboard:

   ```bash
   streamlit run dashboard.py
   ```

5. In the app sidebar:

   - Enter the CSV folder path (e.g. `./data`) and click **Load CSVs from folder**.
   - Toggle **Compact dashboard** if you want the small-cards layout.
   - Choose theme (the app ships with a full dark mode by default if configured).

6. Explore the tabs. Use **Advanced → Saved Queries** to run any of the 25 pre-converted DuckDB queries with a single click. Use the SQL editor for ad-hoc queries and plotting.

---

## Saved Queries

All 25 queries from the original analysis are wired into the **Saved Queries** panel. Examples:

- Top 3 Spenders
- Monthly Rentals per Store
- Film Categories & Rental Durations (quartiles)
- Top 10 Paying Customers — Payment Patterns
- Family Movie Rental Counts
- Peak Activity by Store
- Total Revenue by Category
- Monthly Revenue Trends
- Most Active Stores
- Customer Lifetime Value and Loyalty Tiers
- Revenue, Cost & ROI by Category
- Most Profitable Actors
- Film Availability & Demand
- ...and more (full list is included in the app source under `SAVED_QUERIES`)

(Click a saved-query button to run it. Results appear below the buttons and can be plotted.)

---

## Visualizations & Interaction

- Figures are rendered with Plotly (interactive zoom, hover, export).
- Advanced SQL results can be plotted directly: choose X/Y columns and chart type (scatter, line, bar, box, histogram, treemap, pie).
- Export registered DataFrames to CSV via the sidebar export button.

---

## Troubleshooting & tips

- **No CSVs found:** double-check the folder path and that files end with `.csv`.
- **Table discovery fails:** filenames should include the table name (e.g., `customer.csv`, `payment.csv`). The app uses substring matching.
- **Datetime parsing wrong:** disable Auto-coerce or ensure date columns are in ISO-like format. You can re-run with `Auto-coerce` unchecked.
- **DuckDB SQL errors:** DuckDB is picky about types in `strftime` and date functions — the included queries cast date/time fields where needed. For custom SQL, wrap/cast fields like `CAST(payment_date AS TIMESTAMP)`.
- **Large CSVs:** For very large datasets consider downsampling before loading into the dashboard to keep the UI responsive.

---

## Development notes

- Single-file Streamlit app (`streamlit_dvd_dashboard.py`) — easy to edit.
- The app registers pandas DataFrames into an in-memory DuckDB connection (no on-disk DB).
- Saved queries live in `SAVED_QUERIES` (a Python dict). Add or modify queries there.
- The styling uses a CSS fallback; to avoid platform font issues the app sets a system font stack.

---

## Contributing

1. Fork the repo.
2. Create a branch (`feature/xxx`).
3. Make changes and run the app locally.
4. Open a PR with a short description.

---

## Acknowledgements

Built with: Streamlit, Pandas, DuckDB, Plotly.

---
