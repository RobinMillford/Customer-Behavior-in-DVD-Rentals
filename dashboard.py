# streamlit_dvd_dashboard.py
# Modern interactive Streamlit dashboard for the DVD rental dataset folder
# Uses: pandas, duckdb, plotly, plotly.express, streamlit

import os
import glob
import textwrap
from typing import Dict

import pandas as pd
import duckdb
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ------------------------- Page config & theming -------------------------
st.set_page_config(page_title="DVD Rental Analytics", layout="wide", initial_sidebar_state="expanded")

# Dark-only theme CSS (do NOT set fonts here — let Streamlit handle fonts)
DARK_CSS = """
<style>
/* keep styling minimal and avoid forcing fonts */
.stApp { background-color: #071226; color: #e6eef8; }
.card { background: linear-gradient(180deg,#08101a,#0d1b2a); padding:10px; border-radius:10px; box-shadow: 0 2px 8px rgba(0,0,0,0.6); }
.compact-metric { font-size:18px; font-weight:700; color:#e6eef8; }
.small-muted { color:#aebdcc; font-size:13px; }
</style>
"""
st.markdown(DARK_CSS, unsafe_allow_html=True)

# ------------------------- Helpers -------------------------
@st.cache_data(show_spinner=False)
def load_csvs_from_folder(folder_path: str) -> Dict[str, pd.DataFrame]:
    files = glob.glob(os.path.join(folder_path, "*.csv"))
    dfs: Dict[str, pd.DataFrame] = {}
    for f in files:
        key = os.path.splitext(os.path.basename(f))[0]
        try:
            df = pd.read_csv(f, low_memory=False)
        except Exception:
            df = pd.read_csv(f, engine="python")
        dfs[key] = df
    return dfs


def coerce_date_columns(dfs: Dict[str, pd.DataFrame], sample_size: int = 2000, threshold: float = 0.6) -> Dict[str, pd.DataFrame]:
    coerced = {}
    for name, df in dfs.items():
        df = df.copy()
        for col in df.columns:
            col_low = col.lower()
            if 'date' in col_low or df[col].dtype == object:
                sample = df[col].dropna().astype(str).head(sample_size)
                if sample.empty:
                    continue
                parsed = pd.to_datetime(sample, errors='coerce', infer_datetime_format=True)
                success_rate = parsed.notna().sum() / len(parsed)
                if success_rate >= threshold:
                    df[col] = pd.to_datetime(df[col], errors='coerce', infer_datetime_format=True)
        coerced[name] = df
    return coerced


def create_duckdb_connection(dfs: Dict[str, pd.DataFrame]):
    con = duckdb.connect(database=':memory:')
    for name, df in dfs.items():
        table_name = name.lower().replace(' ', '_')
        con.register(table_name, df)
    return con


def run_sql(con, sql: str) -> pd.DataFrame:
    try:
        return con.execute(sql).df()
    except Exception as e:
        st.error(f"SQL execution error: {e}")
        return pd.DataFrame()


def safe_plotly(fig):
    try:
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Plot error: {e}")


# ------------------------- Sidebar controls -------------------------
st.sidebar.title("Settings & Controls")
folder = st.sidebar.text_input("CSV folder path (local)", value="./data")
load_button = st.sidebar.button("Load CSVs from folder")
st.sidebar.markdown("---")
show_raw = st.sidebar.checkbox("Show raw tables after load", value=False)
auto_coerce_dates = st.sidebar.checkbox("Auto-coerce likely date columns", value=True)
compact_mode = st.sidebar.checkbox("Compact dashboard (cards + small charts)", value=True)
max_rows_preview = st.sidebar.number_input("Max rows to preview", value=200, min_value=10, max_value=5000)

# ------------------------- Utility: discover tables -------------------------
def folder_has_csvs(folder_path: str) -> bool:
    return os.path.isdir(folder_path) and len(glob.glob(os.path.join(folder_path, "*.csv"))) > 0

should_auto_load = folder_has_csvs(folder) and not load_button

# ------------------------- Saved SQL queries (all 25) -------------------------
SAVED_QUERIES = {
    '1. Top 3 Spenders': textwrap.dedent("""
        SELECT fullname, customer_id, total_spent
        FROM (
          SELECT (c.first_name || ' ' || c.last_name) AS fullname,
                 p.customer_id,
                 SUM(p.amount) AS total_spent
          FROM customer c
          JOIN payment p ON c.customer_id = p.customer_id
          GROUP BY p.customer_id, fullname
          ORDER BY total_spent DESC
          LIMIT 3
        ) AS derived_table;"""),
    '2. Monthly Rentals per Store': textwrap.dedent("""
        SELECT s.store_id, strftime(CAST(r.rental_date AS TIMESTAMP), '%Y') AS rental_year, strftime(CAST(r.rental_date AS TIMESTAMP), '%m') AS rental_month, COUNT(r.rental_id) AS rental_count
        FROM rental r
        JOIN staff st ON r.staff_id = st.staff_id
        JOIN store s ON st.store_id = s.store_id
        GROUP BY s.store_id, rental_year, rental_month
        ORDER BY s.store_id, rental_year, rental_month;"""),
    '3. Film Categories & Rental Durations (quartiles)': textwrap.dedent("""
        WITH t1 AS (
            SELECT f.title AS film_title, c.name AS category_name, ntile(4) OVER (ORDER BY COALESCE(f.rental_duration,0)) AS standard_quartile
            FROM film f
            JOIN film_category fc ON f.film_id = fc.film_id
            JOIN category c ON fc.category_id = c.category_id
        )
        SELECT category_name, standard_quartile, COUNT(film_title) AS film_count
        FROM t1
        WHERE category_name IN ('Animation', 'Children', 'Classics', 'Comedy', 'Family', 'Music')
        GROUP BY category_name, standard_quartile
        ORDER BY category_name, standard_quartile;"""),
    '4. Top 10 Paying Customers Payment Patterns': textwrap.dedent("""
        WITH top_paying_customers AS (
            SELECT c.customer_id, (c.first_name || ' ' || c.last_name) AS customer_name, SUM(p.amount) AS total_payment
            FROM customer c
            JOIN payment p ON c.customer_id = p.customer_id
            GROUP BY c.customer_id, customer_name
            ORDER BY total_payment DESC
            LIMIT 10
        )
        SELECT tpc.customer_name, strftime(CAST(p.payment_date AS TIMESTAMP), '%Y-%m') AS payment_month, COUNT(p.payment_id) AS payment_count, SUM(p.amount) AS total_amount
        FROM payment p
        JOIN top_paying_customers tpc ON p.customer_id = tpc.customer_id
        GROUP BY tpc.customer_name, payment_month
        ORDER BY tpc.customer_name, payment_month;"""),
    '5. Family Movie Rental Counts': textwrap.dedent("""
        WITH t1 AS (
            SELECT f.title AS film_title, c.name AS category_name, r.rental_id
            FROM film f
            JOIN film_category fc ON f.film_id = fc.film_id
            JOIN category c ON fc.category_id = c.category_id
            JOIN inventory i ON f.film_id = i.film_id
            JOIN rental r ON i.inventory_id = r.inventory_id
        )
        SELECT film_title, category_name, COUNT(rental_id) AS rental_count
        FROM t1
        WHERE category_name IN ('Animation', 'Children', 'Classics', 'Comedy', 'Family', 'Music')
        GROUP BY film_title, category_name
        ORDER BY category_name, film_title;"""),
    '6. Peak Activity by Store (monthly)': textwrap.dedent("""
        WITH result_table AS (
            SELECT strftime(CAST(r.rental_date AS TIMESTAMP), '%Y') AS year, strftime(CAST(r.rental_date AS TIMESTAMP), '%m') AS rental_month, st.store_id, COUNT(r.rental_id) AS rental_count
            FROM rental r
            JOIN staff st ON r.staff_id = st.staff_id
            GROUP BY year, rental_month, st.store_id
        )
        SELECT year, rental_month,
               SUM(CASE WHEN store_id = 1 THEN rental_count ELSE 0 END) AS store_1_count,
               SUM(CASE WHEN store_id = 2 THEN rental_count ELSE 0 END) AS store_2_count
        FROM result_table
        GROUP BY year, rental_month
        ORDER BY year, rental_month;"""),
    '7. Family-friendly film orders (counts)': textwrap.dedent("""
        WITH result_table AS (
            SELECT f.title AS film_title, cat.name AS category_name, COUNT(re.rental_id) AS num_rentals
            FROM film f
            JOIN film_category fc ON f.film_id = fc.film_id
            JOIN category cat ON fc.category_id = cat.category_id
            JOIN inventory inv ON f.film_id = inv.film_id
            JOIN rental re ON inv.inventory_id = re.inventory_id
            WHERE cat.name IN ('Animation', 'Children', 'Classics', 'Comedy', 'Family', 'Music')
            GROUP BY film_title, category_name
        )
        SELECT * FROM result_table;"""),
    '8. Total Revenue by Category': textwrap.dedent("""
        SELECT category.name AS category_name, SUM(payment.amount) AS total_revenue
        FROM category
        JOIN film_category ON category.category_id = film_category.category_id
        JOIN film ON film_category.film_id = film.film_id
        JOIN inventory ON film.film_id = inventory.film_id
        JOIN rental ON inventory.inventory_id = rental.inventory_id
        JOIN payment ON rental.rental_id = payment.rental_id
        GROUP BY category.name
        ORDER BY total_revenue DESC;"""),
    '9. Total Rentals & Avg Rental Rate per Customer': textwrap.dedent("""
        SELECT customer.first_name, customer.last_name, customer.email, COUNT(rental.rental_id) AS total_rentals, AVG(payment.amount) AS average_rental_rate
        FROM customer
        LEFT JOIN rental ON customer.customer_id = rental.customer_id
        LEFT JOIN payment ON rental.rental_id = payment.rental_id
        GROUP BY customer.first_name, customer.last_name, customer.email;"""),
    '10. Highly Rented Films (>30)': textwrap.dedent("""
        SELECT film.title, COUNT(DISTINCT rental.rental_id) AS rental_count
        FROM film
        JOIN inventory ON film.film_id = inventory.film_id
        JOIN rental ON inventory.inventory_id = rental.inventory_id
        GROUP BY film.title
        HAVING rental_count > 30
        ORDER BY rental_count DESC;"""),
    '11. City Rental Rates (avg)': textwrap.dedent("""
        WITH CityRentalRates AS (
            SELECT city.city_id, city.city, AVG(payment.amount) AS avg_rental_rate
            FROM city
            JOIN address ON city.city_id = address.city_id
            JOIN customer ON address.address_id = customer.address_id
            JOIN rental ON customer.customer_id = rental.customer_id
            JOIN payment ON rental.rental_id = payment.rental_id
            GROUP BY city.city_id, city.city
        ), MaxMinRates AS (
            SELECT MAX(avg_rental_rate) AS max_rate, MIN(avg_rental_rate) AS min_rate FROM CityRentalRates
        )
        SELECT cr.city, cr.avg_rental_rate,
               CASE WHEN cr.avg_rental_rate = mmr.max_rate THEN 'Highest Rate'
                    WHEN cr.avg_rental_rate = mmr.min_rate THEN 'Lowest Rate'
                    ELSE 'Standard Rate' END AS rate_status
        FROM CityRentalRates cr CROSS JOIN MaxMinRates mmr;"""),
    '12. Top customers by unique films rented (top 3)': textwrap.dedent("""
        SELECT customer.customer_id, customer.first_name, customer.last_name, customer.email, COUNT(DISTINCT rental.inventory_id) AS unique_films_rented
        FROM customer
        JOIN rental ON customer.customer_id = rental.customer_id
        GROUP BY customer.customer_id, customer.first_name, customer.last_name, customer.email
        ORDER BY unique_films_rented DESC
        LIMIT 3;"""),
    '13. Monthly Revenue Trends': textwrap.dedent("""
        SELECT strftime(CAST(payment.payment_date AS TIMESTAMP), '%Y-%m') AS payment_month, SUM(payment.amount) AS monthly_revenue
        FROM payment
        GROUP BY payment_month
        ORDER BY payment_month;"""),
    '14. Most Active Stores (top 5)': textwrap.dedent("""
        SELECT store.store_id, COUNT(rental.rental_id) AS total_rentals
        FROM store
        LEFT JOIN staff ON store.store_id = staff.store_id
        LEFT JOIN rental ON staff.staff_id = rental.staff_id
        GROUP BY store.store_id
        ORDER BY total_rentals DESC
        LIMIT 5;"""),
    '15. Customer Lifetime Value (top 5)': textwrap.dedent("""
        SELECT customer.customer_id, customer.first_name, customer.last_name, COUNT(rental.rental_id) AS total_rentals, SUM(payment.amount) AS total_spent
        FROM customer
        LEFT JOIN rental ON customer.customer_id = rental.customer_id
        LEFT JOIN payment ON rental.rental_id = payment.rental_id
        GROUP BY customer.customer_id, customer.first_name, customer.last_name
        ORDER BY total_spent DESC
        LIMIT 5;"""),
    '16. Loyalty Tiers by Rental Frequency': textwrap.dedent("""
        SELECT customer.customer_id, customer.first_name, customer.last_name, COUNT(rental.rental_id) AS total_rentals,
               CASE WHEN COUNT(rental.rental_id) >= 50 THEN 'Platinum'
                    WHEN COUNT(rental.rental_id) >= 30 THEN 'Gold'
                    WHEN COUNT(rental.rental_id) >= 10 THEN 'Silver' ELSE 'Bronze' END AS loyalty_tier
        FROM customer
        LEFT JOIN rental ON customer.customer_id = rental.customer_id
        GROUP BY customer.customer_id, customer.first_name, customer.last_name
        ORDER BY total_rentals DESC;"""),
    '17. Monthly Revenue Growth Rate': textwrap.dedent("""
        WITH MonthlyRevenue AS (
            SELECT strftime(CAST(payment_date AS TIMESTAMP), '%Y-%m') AS payment_month, SUM(amount) AS monthly_revenue
            FROM payment
            GROUP BY payment_month
        ), RevenueGrowth AS (
            SELECT payment_month, monthly_revenue,
                   LAG(monthly_revenue) OVER (ORDER BY payment_month) AS prev_monthly_revenue,
                   (monthly_revenue - LAG(monthly_revenue) OVER (ORDER BY payment_month)) / NULLIF(LAG(monthly_revenue) OVER (ORDER BY payment_month),0) AS growth_rate
            FROM MonthlyRevenue
        )
        SELECT payment_month, monthly_revenue, IFNULL(growth_rate, 0) AS growth_rate FROM RevenueGrowth;"""),
    '18. Revenue, Cost & ROI by Category': textwrap.dedent("""
        SELECT fc.category_id, c.name AS category_name, SUM(payment.amount) AS total_revenue,
               SUM(f.rental_duration * payment.amount) AS total_cost,
               SUM(payment.amount) - SUM(f.rental_duration * payment.amount) AS profit,
               (SUM(payment.amount) - SUM(f.rental_duration * payment.amount)) / NULLIF(SUM(f.rental_duration * payment.amount),0) * 100 AS ROI_percentage
        FROM payment
        JOIN rental ON payment.rental_id = rental.rental_id
        JOIN inventory i ON rental.inventory_id = i.inventory_id
        JOIN film f ON i.film_id = f.film_id
        JOIN film_category fc ON f.film_id = fc.film_id
        JOIN category c ON fc.category_id = c.category_id
        GROUP BY fc.category_id, c.name
        ORDER BY profit DESC;"""),
    '19. Rental Patterns Over Time': textwrap.dedent("""
        WITH RentalPatterns AS (
            SELECT strftime(CAST(rental_date AS TIMESTAMP), '%Y-%m') AS rental_month, COUNT(rental_id) AS rental_count
            FROM rental
            GROUP BY rental_month
        )
        SELECT rental_month, rental_count, LAG(rental_count) OVER (ORDER BY rental_month) AS prev_rental_count,
               (rental_count - LAG(rental_count) OVER (ORDER BY rental_month)) AS rental_growth
        FROM RentalPatterns;"""),
    '20. Late Returns Impact on Revenue': textwrap.dedent("""
        SELECT CASE WHEN date_diff('day', CAST(r.rental_date AS DATE), CAST(r.return_date AS DATE)) > f.rental_duration THEN 'Late' ELSE 'On Time' END AS return_status,
               COUNT(r.rental_id) AS rental_count, SUM(p.amount) AS total_revenue
        FROM rental r
        JOIN payment p ON r.rental_id = p.rental_id
        JOIN inventory i ON r.inventory_id = i.inventory_id
        JOIN film f ON i.film_id = f.film_id
        GROUP BY return_status;"""),
    '21. Most Popular Genres by Rentals': textwrap.dedent("""
        SELECT category.name AS genre, COUNT(rental.rental_id) AS rental_count
        FROM rental
        JOIN inventory ON rental.inventory_id = inventory.inventory_id
        JOIN film ON inventory.film_id = film.film_id
        JOIN film_category ON film.film_id = film_category.film_id
        JOIN category ON film_category.category_id = category.category_id
        GROUP BY genre ORDER BY rental_count DESC;"""),
    '22. Return Patterns by Day of Week': textwrap.dedent("""
        SELECT DAYNAME(return_date) AS day_of_week, COUNT(rental_id) AS rental_count
        FROM rental
        WHERE return_date IS NOT NULL
        GROUP BY day_of_week
        ORDER BY FIELD(day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday');"""),
    '23. Revenue by City': textwrap.dedent("""
        SELECT city.city, SUM(payment.amount) AS total_revenue
        FROM payment
        JOIN rental ON payment.rental_id = rental.rental_id
        JOIN inventory ON rental.inventory_id = inventory.inventory_id
        JOIN store ON inventory.store_id = store.store_id
        JOIN address ON store.address_id = address.address_id
        JOIN city ON address.city_id = city.city_id
        GROUP BY city.city
        ORDER BY total_revenue DESC;"""),
    '24. Most Profitable Actors': textwrap.dedent("""
        SELECT a.actor_id, a.first_name, a.last_name, SUM(payment.amount) AS total_revenue
        FROM actor a
        JOIN film_actor fa ON a.actor_id = fa.actor_id
        JOIN film f ON fa.film_id = f.film_id
        JOIN inventory ON f.film_id = inventory.film_id
        JOIN rental ON inventory.inventory_id = rental.inventory_id
        JOIN payment ON rental.rental_id = payment.rental_id
        GROUP BY a.actor_id, a.first_name, a.last_name
        ORDER BY total_revenue DESC;"""),
    '25. Film Availability & Demand (top 500)': textwrap.dedent("""
        SELECT f.title AS film_title, COUNT(i.inventory_id) AS available_copies, COUNT(r.rental_id) AS rental_count
        FROM film f
        LEFT JOIN inventory i ON f.film_id = i.film_id
        LEFT JOIN rental r ON i.inventory_id = r.inventory_id
        GROUP BY film_title
        ORDER BY rental_count DESC, available_copies DESC
        LIMIT 500;"""),
}

# ------------------------- Main app logic -------------------------
if load_button or should_auto_load:
    if not os.path.isdir(folder):
        st.sidebar.error("Folder not found. Please enter a valid path.")
        st.stop()

    with st.spinner("Loading CSVs..."):
        dfs = load_csvs_from_folder(folder)
        if len(dfs) == 0:
            st.sidebar.warning("No CSV files found in folder.")
            st.stop()
        if auto_coerce_dates:
            dfs = coerce_date_columns(dfs)
        con = create_duckdb_connection(dfs)

    st.sidebar.success(f"Loaded {len(dfs)} CSV files: {', '.join(list(dfs.keys())[:10])}")

    # discover tables (helpers)
    table_names = list(dfs.keys())
    lower_names = [n.lower() for n in table_names]

    def get_table(candidates: list[str]) -> str | None:
        for cand in candidates:
            for i, n in enumerate(lower_names):
                if cand in n:
                    return table_names[i]
        return None

    # main UI
    st.title("📊 DVD Rental — Interactive Analytics Dashboard (Dark Mode)")

    # Header/cards
    col1, col2, col3, col4 = st.columns(4)
    row_counts = {k: v.shape[0] for k, v in dfs.items()}
    total_rows = sum(row_counts.values())
    total_tables = len(dfs)

    with col1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"<div class=\"compact-metric\">Tables</div><div>{total_tables}</div>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"<div class=\"compact-metric\">Total rows</div><div>{total_rows}</div>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        max_rows_table = max((v.shape[0] for v in dfs.values()), default=0)
        st.markdown(f"<div class=\"compact-metric\">Largest table rows</div><div>{max_rows_table}</div>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with col4:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="compact-metric">Quick actions</div><div class="small-muted">Saved Queries • Export tables</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    tabs = st.tabs(["Overview", "Customers", "Rentals & Stores", "Categories & Films", "Revenue", "Actors", "Advanced SQL"])

    # Overview
    with tabs[0]:
        st.header("Overview & Dataset Health")
        counts_df = pd.DataFrame(row_counts.items(), columns=["table", "rows"]).sort_values('rows', ascending=False)
        st.dataframe(counts_df)
        top8 = counts_df.head(8)
        if not top8.empty:
            fig = px.bar(top8, x='table', y='rows', title='Top tables by row count')
            safe_plotly(fig)

        # quick payment metrics
        pay_tbl = get_table(['payment'])
        if pay_tbl:
            q_metrics = f"SELECT COUNT(*) AS payments_count, SUM(amount) AS total_revenue, AVG(amount) AS avg_payment FROM \"{pay_tbl}\""
            df_metrics = run_sql(con, q_metrics)
            if not df_metrics.empty:
                mc = df_metrics.iloc[0].to_dict()
                c1, c2, c3 = st.columns(3)
                c1.metric("Payments", int(mc.get('payments_count', 0)))
                c2.metric("Total revenue", f"{mc.get('total_revenue', 0):,.2f}")
                c3.metric("Avg payment", f"{mc.get('avg_payment', 0):,.2f}")

    # Customers
    with tabs[1]:
        st.header("Customers & Top Spenders")
        customer_tbl = get_table(['customer'])
        payment_tbl = get_table(['payment'])
        if customer_tbl and payment_tbl:
            q = f"SELECT (c.first_name || ' ' || c.last_name) AS fullname, p.customer_id, SUM(p.amount) AS total_spent FROM \"{payment_tbl}\" p JOIN \"{customer_tbl}\" c USING (customer_id) GROUP BY p.customer_id, fullname ORDER BY total_spent DESC LIMIT 500"
            df_top = run_sql(con, q)
            st.subheader("Top customers — table")
            st.dataframe(df_top.head(max_rows_preview))
            if not df_top.empty:
                safe_plotly(px.bar(df_top.head(25), x='total_spent', y='fullname', orientation='h', title='Top 25 customers by spend'))
                safe_plotly(px.histogram(df_top, x='total_spent', nbins=30, title='Distribution of total spent (top customers)'))
                df_pareto = df_top.sort_values('total_spent', ascending=False).reset_index(drop=True)
                df_pareto['cum_pct'] = df_pareto['total_spent'].cumsum() / df_pareto['total_spent'].sum()
                fig_p = make_subplots(specs=[[{"secondary_y": True}]])
                fig_p.add_trace(go.Bar(x=df_pareto['fullname'].head(30), y=df_pareto['total_spent'].head(30), name='spend'))
                fig_p.add_trace(go.Scatter(x=df_pareto['fullname'].head(30), y=df_pareto['cum_pct'].head(30), name='cumulative %', yaxis='y2'))
                fig_p.update_yaxes(title_text='Spend', secondary_y=False)
                fig_p.update_yaxes(title_text='Cumulative %', secondary_y=True, tickformat='.0%')
                fig_p.update_layout(title='Pareto — top customers (top 30)')
                safe_plotly(fig_p)
        else:
            st.warning('customer or payment table not found — rename or place your csv files with those names in the folder.')

    # Rentals & Stores
    with tabs[2]:
        st.header('Rentals — Monthly, By Store & Peak Activity')
        rental_tbl = get_table(['rental'])
        staff_tbl = get_table(['staff'])
        store_tbl = get_table(['store'])
        if rental_tbl and staff_tbl and store_tbl:
            q = f"SELECT s.store_id, strftime(CAST(r.rental_date AS TIMESTAMP), '%Y-%m') AS ym, COUNT(r.rental_id) AS rentals FROM \"{rental_tbl}\" r JOIN \"{staff_tbl}\" st ON r.staff_id = st.staff_id JOIN \"{store_tbl}\" s ON st.store_id = s.store_id GROUP BY s.store_id, ym ORDER BY ym"
            df_month = run_sql(con, q)
            if not df_month.empty:
                df_month['ym_dt'] = pd.to_datetime(df_month['ym'] + '-01', errors='coerce')
                safe_plotly(px.area(df_month, x='ym_dt', y='rentals', color='store_id', title='Monthly rentals by store'))
                safe_plotly(px.bar(df_month, x='ym_dt', y='rentals', color='store_id', title='Stacked monthly rentals'))
                df_month['year'] = df_month['ym_dt'].dt.year.astype(str)
                df_month['month'] = df_month['ym_dt'].dt.month
                pivot = df_month.pivot_table(index='year', columns='month', values='rentals', aggfunc='sum', fill_value=0)
                heat = go.Figure(data=go.Heatmap(z=pivot.values, x=pivot.columns, y=pivot.index, colorbar=dict(title='rentals')))
                heat.update_layout(title='Rentals heatmap (year vs month)')
                safe_plotly(heat)
        else:
            st.warning('rental/staff/store tables missing — rentals visuals unavailable.')

    # Categories & Films
    with tabs[3]:
        st.header('Film Categories, Quartiles & Family Rentals')
        film_tbl = get_table(['film'])
        film_cat_tbl = get_table(['film_category', 'filmcategory', 'film-category'])
        cat_tbl = get_table(['category'])
        if film_tbl and film_cat_tbl and cat_tbl:
            q_quart = f"WITH t1 AS (SELECT f.title AS film_title, c.name AS category_name, ntile(4) OVER (ORDER BY COALESCE(f.rental_duration,0)) AS quart FROM \"{film_tbl}\" f JOIN \"{film_cat_tbl}\" fc ON f.film_id = fc.film_id JOIN \"{cat_tbl}\" c ON fc.category_id = c.category_id) SELECT category_name, quart AS standard_quartile, COUNT(film_title) AS film_count FROM t1 WHERE category_name IN ('Animation','Children','Classics','Comedy','Family','Music') GROUP BY category_name, standard_quartile ORDER BY category_name, standard_quartile"
            df_quart = run_sql(con, q_quart)
            st.subheader('Film quartiles by rental_duration')
            st.dataframe(df_quart.head(500))
            if not df_quart.empty:
                safe_plotly(px.bar(df_quart, x='standard_quartile', y='film_count', color='category_name', barmode='group', title='Film counts by quartile & category'))
            inv_tbl = get_table(['inventory'])
            rental_tbl_local = get_table(['rental'])
            if inv_tbl and rental_tbl_local:
                q_family = f"WITH t1 AS (SELECT f.title AS film_title, c.name AS category_name, r.rental_id FROM \"{film_tbl}\" f JOIN \"{film_cat_tbl}\" fc ON f.film_id = fc.film_id JOIN \"{cat_tbl}\" c ON fc.category_id = c.category_id JOIN \"{inv_tbl}\" i ON f.film_id = i.film_id JOIN \"{rental_tbl_local}\" r ON i.inventory_id = r.inventory_id) SELECT category_name, film_title, COUNT(rental_id) AS rentals FROM t1 WHERE category_name IN ('Animation','Children','Classics','Comedy','Family','Music') GROUP BY category_name, film_title ORDER BY rentals DESC LIMIT 500"
                df_family = run_sql(con, q_family)
                if not df_family.empty:
                    safe_plotly(px.treemap(df_family, path=['category_name','film_title'], values='rentals', title='Family categories treemap'))
                    safe_plotly(px.sunburst(df_family, path=['category_name','film_title'], values='rentals', title='Family categories sunburst'))
        else:
            st.warning('film or film_category or category tables missing — category visuals limited.')

    # Revenue
    with tabs[4]:
        st.header('Revenue: Trends, Categories & Late Returns')
        pay_tbl = get_table(['payment'])
        if pay_tbl:
            q_rev = f"SELECT strftime(CAST(payment.payment_date AS TIMESTAMP), '%Y-%m') AS ym, SUM(payment.amount) AS revenue FROM \"{pay_tbl}\" payment GROUP BY ym ORDER BY ym"
            df_rev = run_sql(con, q_rev)
            if not df_rev.empty:
                df_rev['ym_dt'] = pd.to_datetime(df_rev['ym'] + '-01', errors='coerce')
                safe_plotly(px.line(df_rev, x='ym_dt', y='revenue', markers=True, title='Monthly revenue'))
                df_rev = df_rev.sort_values('ym_dt')
                df_rev['ma_3'] = df_rev['revenue'].rolling(3, min_periods=1).mean()
                df_rev['ma_6'] = df_rev['revenue'].rolling(6, min_periods=1).mean()
                fig_ma = go.Figure()
                fig_ma.add_trace(go.Scatter(x=df_rev['ym_dt'], y=df_rev['revenue'], name='monthly'))
                fig_ma.add_trace(go.Scatter(x=df_rev['ym_dt'], y=df_rev['ma_3'], name='3-mo MA', line=dict(dash='dash')))
                fig_ma.add_trace(go.Scatter(x=df_rev['ym_dt'], y=df_rev['ma_6'], name='6-mo MA', line=dict(dash='dot')))
                fig_ma.update_layout(title='Revenue with moving averages')
                safe_plotly(fig_ma)
        # revenue by category
        if all([pay_tbl, film_tbl, film_cat_tbl, cat_tbl, get_table(['inventory']), get_table(['rental'])]):
            inv = get_table(['inventory'])
            rent = get_table(['rental'])
            q_cat = f"SELECT c.name AS category_name, SUM(p.amount) AS total_revenue FROM \"{cat_tbl}\" c JOIN \"{film_cat_tbl}\" fc ON c.category_id = fc.category_id JOIN \"{film_tbl}\" f ON fc.film_id = f.film_id JOIN \"{inv}\" i ON f.film_id = i.film_id JOIN \"{rent}\" r ON i.inventory_id = r.inventory_id JOIN \"{pay_tbl}\" p ON r.rental_id = p.rental_id GROUP BY c.name ORDER BY total_revenue DESC"
            df_cat_rev = run_sql(con, q_cat)
            st.subheader('Revenue by category')
            st.dataframe(df_cat_rev.head(200))
            if not df_cat_rev.empty:
                safe_plotly(px.bar(df_cat_rev.head(12), x='category_name', y='total_revenue', title='Top categories by revenue'))
                safe_plotly(px.violin(df_cat_rev, y='total_revenue', box=True, points='all', title='Revenue distribution by category'))
        # late returns impact
        rent = get_table(['rental'])
        if all([rent, pay_tbl, film_tbl, get_table(['inventory'])]):
            inv = get_table(['inventory'])
            q_late = f"SELECT CASE WHEN date_diff('day', CAST(r.rental_date AS DATE), CAST(r.return_date AS DATE)) > f.rental_duration THEN 'Late' ELSE 'On Time' END AS return_status, p.amount AS amount FROM \"{rent}\" r JOIN \"{pay_tbl}\" p ON r.rental_id = p.rental_id JOIN \"{inv}\" i ON r.inventory_id = i.inventory_id JOIN \"{film_tbl}\" f ON i.film_id = f.film_id"
            df_late = run_sql(con, q_late)
            if not df_late.empty:
                safe_plotly(px.box(df_late, x='return_status', y='amount', title='Payment amount distribution by return status'))

    # Actors
    with tabs[5]:
        st.header('Actors — revenue & flows')
        actor_tbl = get_table(['actor'])
        film_actor_tbl = get_table(['film_actor', 'filmactor'])
        inv_tbl = get_table(['inventory'])
        rent_tbl = get_table(['rental'])
        pay_tbl = get_table(['payment'])
        if all([actor_tbl, film_actor_tbl, inv_tbl, rent_tbl, pay_tbl, film_tbl, film_cat_tbl, cat_tbl]):
            q_actor = f"SELECT a.actor_id, a.first_name, a.last_name, SUM(p.amount) AS total_revenue FROM \"{actor_tbl}\" a JOIN \"{film_actor_tbl}\" fa ON a.actor_id = fa.actor_id JOIN \"{film_tbl}\" f ON fa.film_id = f.film_id JOIN \"{inv_tbl}\" i ON f.film_id = i.film_id JOIN \"{rent_tbl}\" r ON i.inventory_id = r.inventory_id JOIN \"{pay_tbl}\" p ON r.rental_id = p.rental_id GROUP BY a.actor_id, a.first_name, a.last_name ORDER BY total_revenue DESC LIMIT 200"
            df_actor = run_sql(con, q_actor)
            st.subheader('Top actors by revenue')
            if not df_actor.empty:
                st.dataframe(df_actor.head(max_rows_preview))
                safe_plotly(px.bar(df_actor.head(40), x='last_name', y='total_revenue', hover_data=['first_name'], title='Top actors by revenue'))
                q_sankey = f"SELECT (a.first_name || ' ' || a.last_name) AS actor_name, c.name AS category_name, SUM(p.amount) AS revenue FROM \"{actor_tbl}\" a JOIN \"{film_actor_tbl}\" fa ON a.actor_id = fa.actor_id JOIN \"{film_tbl}\" f ON fa.film_id = f.film_id JOIN \"{film_cat_tbl}\" fc ON f.film_id = fc.film_id JOIN \"{cat_tbl}\" c ON fc.category_id = c.category_id JOIN \"{inv_tbl}\" i ON f.film_id = i.film_id JOIN \"{rent_tbl}\" r ON i.inventory_id = r.inventory_id JOIN \"{pay_tbl}\" p ON r.rental_id = p.rental_id GROUP BY actor_name, category_name ORDER BY revenue DESC LIMIT 500"
                df_sankey = run_sql(con, q_sankey)
                if not df_sankey.empty:
                    actors = df_sankey['actor_name'].unique().tolist()
                    cats = df_sankey['category_name'].unique().tolist()
                    nodes = actors + cats
                    idx = {n: i for i, n in enumerate(nodes)}
                    sources = [idx[a] for a in df_sankey['actor_name']]
                    targets = [idx[c] for c in df_sankey['category_name']]
                    values = df_sankey['revenue'].tolist()
                    sankey = go.Figure(data=[go.Sankey(node=dict(label=nodes, pad=15, thickness=18), link=dict(source=sources, target=targets, value=values))])
                    sankey.update_layout(title='Actor -> Category revenue flow (sample)', font_size=10)
                    safe_plotly(sankey)
        else:
            st.info('Actor analysis unavailable — some actor/film_actor/inventory/rental/payment tables are missing.')
        # availability vs demand
        if film_tbl and inv_tbl and rent_tbl:
            q_avail = f"SELECT f.title AS film_title, COUNT(i.inventory_id) AS available_copies, COUNT(r.rental_id) AS rental_count FROM \"{film_tbl}\" f LEFT JOIN \"{inv_tbl}\" i ON f.film_id = i.film_id LEFT JOIN \"{rent_tbl}\" r ON i.inventory_id = r.inventory_id GROUP BY film_title ORDER BY rental_count DESC, available_copies DESC LIMIT 500"
            df_avail = run_sql(con, q_avail)
            if not df_avail.empty:
                st.subheader('Availability vs Demand — films')
                st.dataframe(df_avail.head(200))
                safe_plotly(px.scatter(df_avail, x='available_copies', y='rental_count', size='rental_count', hover_data=['film_title'], title='Availability vs Demand'))

    # Advanced SQL & Saved Queries (wired all 25 above)
    with tabs[6]:
        st.header('Advanced — SQL Explorer & Saved Queries')
        st.markdown('Run ad-hoc SQL against DuckDB. Click any saved query button to run it.')

        names = list(SAVED_QUERIES.keys())
        ncols = 3
        rows = (len(names) + ncols - 1) // ncols
        for r in range(rows):
            cols = st.columns(ncols)
            for cidx in range(ncols):
                idx = r * ncols + cidx
                if idx >= len(names):
                    break
                name = names[idx]
                q = SAVED_QUERIES[name]
                if cols[cidx].button(name):
                    df_q = run_sql(con, q)
                    st.dataframe(df_q)

        st.markdown('---')
        custom_sql = st.text_area('Enter SQL (use double quotes for table names if needed)', height=200)
        if st.button('Run SQL'):
            if not custom_sql.strip():
                st.warning('Please enter SQL.')
            else:
                df_custom = run_sql(con, custom_sql)
                st.dataframe(df_custom.head(500))
                if not df_custom.empty:
                    cols = df_custom.columns.tolist()
                    x_col = st.selectbox('X axis', options=cols, key='adv_x')
                    y_col = st.selectbox('Y axis', options=cols, key='adv_y')
                    chart_type = st.selectbox('Chart type', options=['scatter','line','bar','box','histogram','treemap','pie'])
                    if st.button('Plot result'):
                        try:
                            if chart_type == 'scatter':
                                fig = px.scatter(df_custom, x=x_col, y=y_col, title='Custom scatter')
                            elif chart_type == 'line':
                                fig = px.line(df_custom, x=x_col, y=y_col, title='Custom line')
                            elif chart_type == 'bar':
                                fig = px.bar(df_custom, x=x_col, y=y_col, title='Custom bar')
                            elif chart_type == 'box':
                                fig = px.box(df_custom, x=x_col, y=y_col, title='Custom box')
                            elif chart_type == 'histogram':
                                fig = px.histogram(df_custom, x=x_col, title='Custom histogram')
                            elif chart_type == 'treemap':
                                path = [cols[0]] + ([cols[1]] if len(cols) > 1 else [])
                                fig = px.treemap(df_custom, path=path, values=y_col, title='Custom treemap')
                            else:
                                fig = px.pie(df_custom, names=x_col, values=y_col, title='Custom pie')
                            safe_plotly(fig)
                        except Exception as e:
                            st.error(f'Plot error: {e}')

    # Export
    st.sidebar.markdown('---')
    if st.sidebar.button('Export tables to CSV'):
        export_dir = os.path.join(folder, 'exported_tables')
        os.makedirs(export_dir, exist_ok=True)
        for name, df in dfs.items():
            df.to_csv(os.path.join(export_dir, f"{name}.csv"), index=False)
        st.sidebar.success(f'Exported {len(dfs)} tables to {export_dir}')

    st.success('Dashboard ready — explore the tabs above.')

else:
    st.title('DVD Rental Streamlit Dashboard — Starter (Dark Mode)')
    st.write('This app will load all CSVs from a folder, register them in DuckDB, and offer interactive plots.')
    st.info("Put your CSVs into the folder './data' (or enter another path), then click 'Load CSVs from folder'.")
    st.markdown('---')
    st.write('Supported visuals: time-series, area, stacked bars, heatmaps, treemaps, sankey, violin/box, scatter, correlation heatmap.')
    st.code('pip install streamlit pandas duckdb plotly')
