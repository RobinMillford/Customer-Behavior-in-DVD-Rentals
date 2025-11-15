# streamlit_dvd_dashboard.py
# Modern interactive Streamlit dashboard for the DVD rental dataset folder
# Uses: pandas, duckdb, plotly, plotly.express, streamlit

import os
import glob
import pandas as pd
import duckdb
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="DVD Rental Analytics", layout="wide", initial_sidebar_state="expanded")

# ------------------------- Helpers -------------------------
@st.cache_data(show_spinner=False)
def load_csvs_from_folder(folder_path: str) -> dict:
    """Load all CSV files in a folder and return a dict of DataFrames keyed by filename (without extension)."""
    files = glob.glob(os.path.join(folder_path, "*.csv"))
    dfs = {}
    for f in files:
        key = os.path.splitext(os.path.basename(f))[0]
        try:
            df = pd.read_csv(f, low_memory=False)
        except Exception:
            df = pd.read_csv(f, engine="python")
        dfs[key] = df
    return dfs


def coerce_date_columns(dfs: dict, sample_size: int = 2000, threshold: float = 0.6) -> dict:
    """Auto-detect and coerce likely date columns to pandas datetime for each DataFrame.
    - Columns that contain 'date' in the name or object dtype are sampled.
    - If >= threshold of samples parse as datetimes, the whole column is coerced.
    """
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


def create_duckdb_connection(dfs: dict):
    """Create a fresh in-memory DuckDB connection and register DataFrames as tables.
    We intentionally do not cache the connection object (not serializable by Streamlit).
    """
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


# ------------------------- UI: Sidebar -------------------------
st.sidebar.title("Settings & Controls")
folder = st.sidebar.text_input("CSV folder path (local)", value="./data")
load_button = st.sidebar.button("Load CSVs from folder")
st.sidebar.markdown("---")
show_raw = st.sidebar.checkbox("Show raw tables after load", value=False)
auto_coerce_dates = st.sidebar.checkbox("Auto-coerce likely date columns", value=True)
max_rows_preview = st.sidebar.number_input("Max rows to preview", value=200, min_value=10, max_value=5000)

# ------------------------- Auto-load logic -------------------------
def folder_has_csvs(folder_path: str) -> bool:
    return os.path.isdir(folder_path) and len(glob.glob(os.path.join(folder_path, "*.csv"))) > 0

should_auto_load = folder_has_csvs(folder) and not load_button

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

    # ------------------------- helper: table name discovery -------------------------
    table_names = list(dfs.keys())
    lower_names = [n.lower() for n in table_names]

    def get_table(candidates: list[str]) -> str | None:
        for cand in candidates:
            for i, n in enumerate(lower_names):
                if cand in n:
                    return table_names[i]
        return None

    # ------------------------- Main UI -------------------------
    st.title("📊 DVD Rental — Interactive Analytics Dashboard")
    st.markdown("Explore datasets, interactive charts, and run custom SQL. Tables are auto-registered in DuckDB.")

    tabs = st.tabs(["Overview", "Customers", "Rentals & Stores", "Categories & Films", "Revenue", "Actors", "Advanced SQL"])

    # ------------------------- Overview -------------------------
    with tabs[0]:
        st.header("Overview & Dataset Health")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Tables Loaded", len(dfs))
        with col2:
            row_counts = {k: v.shape[0] for k, v in dfs.items()}
            st.metric("Total rows", sum(row_counts.values()))
        with col3:
            st.metric("Total columns", sum(v.shape[1] for v in dfs.values()))

        st.subheader("Table row counts")
        counts_df = pd.DataFrame(row_counts.items(), columns=["table", "rows"]).sort_values('rows', ascending=False)
        st.dataframe(counts_df)

        # small correlation heatmap for the largest numeric table
        numeric_tables = {n: df.select_dtypes(include=['number']) for n, df in dfs.items()}
        best_table = None
        best_cols = 0
        for name, num_df in numeric_tables.items():
            if num_df.shape[1] > best_cols and num_df.shape[1] >= 2:
                best_table = name
                best_cols = num_df.shape[1]
        if best_table:
            st.subheader(f"Correlation heatmap — numeric columns from: {best_table}")
            corr = numeric_tables[best_table].corr()
            fig_corr = px.imshow(corr, text_auto=True, title=f"Correlation — {best_table}")
            safe_plotly(fig_corr)

    # ------------------------- Customers -------------------------
    with tabs[1]:
        st.header("Customers & Top Spenders")
        customer_tbl = get_table(['customer'])
        payment_tbl = get_table(['payment'])

        if customer_tbl and payment_tbl:
            q = f"SELECT (c.first_name || ' ' || c.last_name) AS fullname, p.customer_id, SUM(p.amount) AS total_spent FROM \"{payment_tbl}\" p JOIN \"{customer_tbl}\" c USING (customer_id) GROUP BY p.customer_id, fullname ORDER BY total_spent DESC LIMIT 250"
            df_top = run_sql(con, q)
            st.subheader("Top customers — table")
            st.dataframe(df_top.head(max_rows_preview))

            if not df_top.empty:
                # Horizontal bar
                fig = px.bar(df_top.head(25), x='total_spent', y='fullname', orientation='h', title='Top 25 customers by spend')
                safe_plotly(fig)

                # Scatter matrix (for numeric fields) if available
                if 'total_spent' in df_top.columns:
                    st.subheader('Scatter matrix — top customers')
                    fig_smatrix = px.scatter_matrix(df_top.head(50), dimensions=['total_spent'], title='Scatter matrix (total_spent)')
                    safe_plotly(fig_smatrix)

                # Pareto chart
                df_p = df_top.sort_values('total_spent', ascending=False).reset_index(drop=True)
                df_p['cum_pct'] = df_p['total_spent'].cumsum() / df_p['total_spent'].sum()
                fig_p = make_subplots(specs=[[{"secondary_y": True}]])
                fig_p.add_trace(go.Bar(x=df_p['fullname'].head(30), y=df_p['total_spent'].head(30), name='spend'))
                fig_p.add_trace(go.Scatter(x=df_p['fullname'].head(30), y=df_p['cum_pct'].head(30), name='cumulative', yaxis='y2'))
                fig_p.update_yaxes(title_text='Spend', secondary_y=False)
                fig_p.update_yaxes(title_text='Cumulative %', secondary_y=True, tickformat='.0%')
                fig_p.update_layout(title='Pareto — top customers (top 30)')
                safe_plotly(fig_p)

        else:
            st.warning('customer or payment table not found — rename or place your csv files with those names in the folder.')

    # ------------------------- Rentals & Stores -------------------------
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
                st.subheader('Area chart — rentals over time (per store)')
                fig_area = px.area(df_month, x='ym_dt', y='rentals', color='store_id', title='Monthly rentals by store')
                safe_plotly(fig_area)

                st.subheader('Stacked bar — rentals by store each month')
                fig_bar = px.bar(df_month, x='ym_dt', y='rentals', color='store_id', title='Stacked monthly rentals')
                safe_plotly(fig_bar)

                st.subheader('Heatmap — year vs month')
                df_month['year'] = df_month['ym_dt'].dt.year.astype(str)
                df_month['month'] = df_month['ym_dt'].dt.month
                pivot = df_month.pivot_table(index='year', columns='month', values='rentals', aggfunc='sum', fill_value=0)
                heat = go.Figure(data=go.Heatmap(z=pivot.values, x=pivot.columns, y=pivot.index))
                heat.update_layout(title='Rentals heatmap (year vs month)')
                safe_plotly(heat)

        else:
            st.warning('rental/staff/store tables missing — rentals visuals unavailable.')

    # ------------------------- Categories & Films -------------------------
    with tabs[3]:
        st.header('Film Categories, Quartiles & Family Rentals')
        film_tbl = get_table(['film'])
        film_cat_tbl = get_table(['film_category', 'filmcategory', 'film-category'])
        cat_tbl = get_table(['category'])

        if film_tbl and film_cat_tbl and cat_tbl:
            q_quart = f"WITH t1 AS (SELECT f.title AS film_title, c.name AS category_name, ntile(4) OVER (ORDER BY COALESCE(f.rental_duration,0)) AS quart FROM \"{film_tbl}\" f JOIN \"{film_cat_tbl}\" fc ON f.film_id = fc.film_id JOIN \"{cat_tbl}\" c ON fc.category_id = c.category_id) SELECT category_name, quart AS standard_quartile, COUNT(film_title) AS film_count FROM t1 WHERE category_name IN ('Animation','Children','Classics','Comedy','Family','Music') GROUP BY category_name, standard_quartile ORDER BY category_name, standard_quartile"
            df_quart = run_sql(con, q_quart)
            st.subheader('Film quartiles by rental_duration')
            st.dataframe(df_quart)
            if not df_quart.empty:
                fig = px.bar(df_quart, x='standard_quartile', y='film_count', color='category_name', barmode='group', title='Film counts by quartile & category')
                safe_plotly(fig)

            # family category treemap (sample)
            inv_tbl = get_table(['inventory'])
            if inv_tbl:
                q_family = f"WITH t1 AS (SELECT f.title AS film_title, c.name AS category_name, r.rental_id FROM \"{film_tbl}\" f JOIN \"{film_cat_tbl}\" fc ON f.film_id = fc.film_id JOIN \"{cat_tbl}\" c ON fc.category_id = c.category_id JOIN \"{inv_tbl}\" i ON f.film_id = i.film_id JOIN \"{rental_tbl}\" r ON i.inventory_id = r.inventory_id) SELECT category_name, film_title, COUNT(rental_id) AS rentals FROM t1 WHERE category_name IN ('Animation','Children','Classics','Comedy','Family','Music') GROUP BY category_name, film_title ORDER BY rentals DESC LIMIT 500"
                df_family = run_sql(con, q_family)
                st.subheader('Family categories — treemap')
                if not df_family.empty:
                    fig_t = px.treemap(df_family, path=['category_name','film_title'], values='rentals', title='Family categories treemap')
                    safe_plotly(fig_t)

        else:
            st.warning('film or film_category or category tables missing — category visuals limited.')

    # ------------------------- Revenue -------------------------
    with tabs[4]:
        st.header('Revenue: Trends, Categories & Late Returns')
        pay_tbl = get_table(['payment'])
        if pay_tbl:
            q_rev = f"SELECT strftime(CAST(payment.payment_date AS TIMESTAMP), '%Y-%m') AS ym, SUM(payment.amount) AS revenue FROM \"{pay_tbl}\" payment GROUP BY ym ORDER BY ym"
            df_rev = run_sql(con, q_rev)
            if not df_rev.empty:
                df_rev['ym_dt'] = pd.to_datetime(df_rev['ym'] + '-01', errors='coerce')
                st.subheader('Monthly revenue — line + markers')
                fig = px.line(df_rev, x='ym_dt', y='revenue', markers=True, title='Monthly revenue')
                safe_plotly(fig)

                st.subheader('Revenue rolling averages')
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
            st.dataframe(df_cat_rev)
            if not df_cat_rev.empty:
                fig = px.bar(df_cat_rev.head(12), x='category_name', y='total_revenue', title='Top categories by revenue')
                safe_plotly(fig)
                fig_v = px.violin(df_cat_rev, y='total_revenue', box=True, points='all', title='Revenue distribution by category')
                safe_plotly(fig_v)

        # late returns impact
        rent = get_table(['rental'])
        if all([rent, pay_tbl, film_tbl, get_table(['inventory'])]):
            inv = get_table(['inventory'])
            q_late = f"SELECT CASE WHEN date_diff('day', CAST(r.rental_date AS DATE), CAST(r.return_date AS DATE)) > f.rental_duration THEN 'Late' ELSE 'On Time' END AS return_status, p.amount AS amount FROM \"{rent}\" r JOIN \"{pay_tbl}\" p ON r.rental_id = p.rental_id JOIN \"{inv}\" i ON r.inventory_id = i.inventory_id JOIN \"{film_tbl}\" f ON i.film_id = f.film_id"
            df_late = run_sql(con, q_late)
            if not df_late.empty:
                st.subheader('Payment distribution by return status')
                fig = px.box(df_late, x='return_status', y='amount', title='Payment amount by return status')
                safe_plotly(fig)

    # ------------------------- Actors -------------------------
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
                fig = px.bar(df_actor.head(40), x='last_name', y='total_revenue', hover_data=['first_name'], title='Top actors by revenue')
                safe_plotly(fig)

                # Sankey: actor -> category (aggregate)
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

        st.subheader('Availability vs Demand — films')
        if film_tbl and inv_tbl and rent_tbl:
            q_avail = f"SELECT f.title AS film_title, COUNT(i.inventory_id) AS available_copies, COUNT(r.rental_id) AS rental_count FROM \"{film_tbl}\" f LEFT JOIN \"{inv_tbl}\" i ON f.film_id = i.film_id LEFT JOIN \"{rent_tbl}\" r ON i.inventory_id = r.inventory_id GROUP BY film_title ORDER BY rental_count DESC, available_copies DESC LIMIT 500"
            df_avail = run_sql(con, q_avail)
            if not df_avail.empty:
                st.dataframe(df_avail.head(200))
                fig = px.scatter(df_avail, x='available_copies', y='rental_count', size='rental_count', hover_data=['film_title'], title='Availability vs Demand')
                safe_plotly(fig)

    # ------------------------- Advanced SQL -------------------------
    with tabs[6]:
        st.header('Advanced — SQL Explorer & Saved Queries')
        st.markdown('Run ad-hoc SQL against DuckDB. Converted MySQL queries are available in Saved Queries.')

        saved_queries = {
            'Top 3 spenders': """
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
) AS derived_table;""",
        }

        cols = st.columns(3)
        for i, (name, q) in enumerate(saved_queries.items()):
            with cols[i % 3]:
                if st.button(name):
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

    # ------------------------- Export -------------------------
    st.sidebar.markdown('---')
    if st.sidebar.button('Export tables to CSV'):
        export_dir = os.path.join(folder, 'exported_tables')
        os.makedirs(export_dir, exist_ok=True)
        for name, df in dfs.items():
            df.to_csv(os.path.join(export_dir, f"{name}.csv"), index=False)
        st.sidebar.success(f'Exported {len(dfs)} tables to {export_dir}')

    st.success('Dashboard ready — explore the tabs above.')

else:
    st.title('DVD Rental Streamlit Dashboard — Starter')
    st.write('This app will load all CSVs from a folder, register them in DuckDB, and offer interactive plots.')
    st.info("Put your CSVs into the folder './data' (or enter another path), then click 'Load CSVs from folder'.")
    st.markdown('---')
    st.write('Supported visuals: time-series, area, stacked bars, heatmaps, treemaps, sankey, violin/box, scatter, correlation heatmap.')
    st.code('pip install streamlit pandas duckdb plotly streamlit run streamlit_dvd_dashboard.py')

# End of file
