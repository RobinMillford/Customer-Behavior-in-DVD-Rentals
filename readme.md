# DVD Rental Analytics — Streamlit Dashboard

A polished, local-first Streamlit dashboard for exploring the **DVD Rental** CSV dataset.
Load your CSVs from a folder (e.g. `./data`) and the app will register them into an in-memory DuckDB and provide 25 built-in analytics queries, interactive Plotly visualizations, a saved-queries panel, and an Advanced SQL explorer.

---

## 🚀 Live Demo (Streamlit Cloud)

You can try the **live deployed version** here:

👉 **[https://customer-behavior.streamlit.app/](https://customer-behavior-in-dvd-rentals.streamlit.app/)**

This deployment contains the full dashboard, all features, and supports uploading a dataset folder directly inside the app.

---

## Key features

* Auto-load **all CSVs** from a folder and register them in DuckDB.
* 7 interactive tabs: Overview, Customers, Rentals & Stores, Categories & Films, Revenue, Actors, Advanced SQL.
* 25 converted DuckDB saved queries (one-click buttons).
* Interactive Plotly charts: area, stacked bar, heatmap, treemap, sunburst, violin, scatter, Pareto, rolling averages.
* Compact dashboard header with metric cards and quick actions.
* Advanced SQL Explorer: run custom DuckDB SQL + visualize the results.
* CSV export of all registered tables.
* Single-file Streamlit app — **fast, local, no external compute**.

---

## Quick start

1. Clone your repo:

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

3. Place all CSV files in a folder such as `./data`.

4. Run the dashboard:

   ```bash
   streamlit run dashboard.py
   ```

5. In the app sidebar:

   * Enter dataset folder path
   * Load CSVs
   * Explore visualizations
   * Run saved queries
   * Run your own SQL

---

## Saved Queries

All 25 queries from the original analysis are included in the **Saved Queries** area.

Examples include:

* Top 3 Spenders
* Monthly Rentals per Store
* Revenue, Cost & ROI by Category
* Family Movie Rental Counts
* Customer Lifetime Value
* Loyalty Tiers
* Late Returns Impact
* Most Profitable Actors
* Film Availability & Demand
* …and much more

Click a button → query runs instantly → results appear below → optional visualization.

---

## Visualizations & Interaction

* Interactive Plotly charts (zoom, hover, export).
* Auto-generated charts for saved queries and custom SQL.
* Multiple visualization types: scatter, bar, box, treemap, pie, histogram.
* Export all DuckDB tables back to CSV.

---

## Troubleshooting & Tips

* **No CSVs found?** Check the folder path.
* **Table mismatch?** Ensure file names loosely match (`customer.csv`, `film_category.csv`, etc.).
* **Datetime issues?** Disable Auto-Coerce Dates in the sidebar.
* **DuckDB casting errors?** Use:

  ```sql
  CAST(payment_date AS TIMESTAMP)
  ```

---

## Development Notes

* Uses **in-memory DuckDB** for fast SQL execution.
* All queries stored in `SAVED_QUERIES`.
* Clean CSS-based dark theme (full dark mode).
* Lightweight and easy to extend.

---

## Contributing

1. Fork the repo
2. Create a feature branch
3. Run locally and test
4. Submit PR 🚀

---

## Acknowledgements

Built with ❤️ using:

* **Streamlit**
* **Pandas**
* **DuckDB**
* **Plotly**

---
