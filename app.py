"""EV Market Performance & Insights - Flask app.

Reads the compressed dataset files (compressed_data*.csv.gz) or any CSV
placed in the project folder (or a data/ folder), cleans it in memory and
serves KPI + chart data to the dashboard. Source files are never modified.
"""
import glob
import os

import pandas as pd
from flask import Flask, jsonify, render_template, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)

# role -> keywords searched (in order) inside the column names
ROLES = {
    "year": ["model_year", "year"],
    "manufacturer": ["manufacturer", "brand", "make"],
    "battery_type": ["battery_type", "batterytype"],
    "battery_capacity": ["battery_capacity", "capacity"],
    "region": ["region"],
    "category": ["category", "vehicle_type", "segment"],
    "country": ["manufacturing_country", "country"],
    "sales": ["annual_sales", "sales"],
    "rating": ["customer_rating", "rating"],
    "range": ["range"],
    "energy": ["energy"],
    "co2": ["co2"],
    "model": ["model_name", "model"],
}
FILTERS = ["manufacturer", "battery_type", "region", "category"]

_cache = {}


def find_files():
    patterns = ["compressed_data*.csv.gz", "*.csv", "data/*.csv", "data/*.csv.gz"]
    files = []
    custom = os.environ.get("EV_DATA_FILE")
    if custom:
        return [custom]
    for p in patterns:
        files += glob.glob(os.path.join(BASE_DIR, p))
    return sorted(set(files))


def load_data():
    if "df" in _cache:
        return _cache["df"], _cache["cols"]
    files = find_files()
    if not files:
        return None, {}
    frames = [pd.read_csv(f) for f in files]
    df = pd.concat(frames, ignore_index=True).drop_duplicates()
    cols, used = {}, set()
    lower = {c: c.lower().replace(" ", "_") for c in df.columns}
    for role, words in ROLES.items():
        for w in words:
            hit = next((c for c in df.columns if w in lower[c] and c not in used), None)
            if hit:
                cols[role] = hit
                used.add(hit)
                break
    for role in ["year", "sales", "rating", "range", "energy", "co2", "battery_capacity"]:
        if role in cols:
            df[cols[role]] = pd.to_numeric(df[cols[role]], errors="coerce")
    _cache["df"], _cache["cols"] = df, cols
    return df, cols


def apply_filters(df, cols):
    for key in FILTERS:
        val = request.args.get(key)
        if val and key in cols:
            df = df[df[cols[key]].astype(str) == val]
    if "year" in cols:
        lo, hi = request.args.get("year_min"), request.args.get("year_max")
        if lo:
            df = df[df[cols["year"]] >= float(lo)]
        if hi:
            df = df[df[cols["year"]] <= float(hi)]
    return df


def group(df, cols, dim, measure, how="sum", top=10):
    if dim not in cols or measure not in cols or df.empty:
        return {"labels": [], "values": []}
    s = df.groupby(cols[dim])[cols[measure]].agg(how).dropna()
    s = s.sort_values(ascending=False).head(top)
    return {"labels": [str(i) for i in s.index], "values": [round(float(v), 2) for v in s.values]}


def num(df, cols, role, how):
    if role not in cols or df.empty:
        return None
    v = getattr(df[cols[role]], how)()
    return None if pd.isna(v) else round(float(v), 2)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/options")
def options():
    df, cols = load_data()
    if df is None:
        return jsonify({"error": "No dataset found. Put compressed_data*.csv.gz in the project folder."}), 404
    out = {k: sorted(df[cols[k]].dropna().astype(str).unique().tolist()) for k in FILTERS if k in cols}
    if "year" in cols:
        out["year_range"] = [int(df[cols["year"]].min()), int(df[cols["year"]].max())]
    return jsonify(out)


@app.route("/api/data")
def data():
    df, cols = load_data()
    if df is None:
        return jsonify({"error": "No dataset found. Put compressed_data*.csv.gz in the project folder."}), 404
    try:
        df = apply_filters(df, cols)
    except ValueError:
        return jsonify({"error": "Invalid filter value."}), 400
    kpis = {
        "rows": int(len(df)),
        "total_sales": num(df, cols, "sales", "sum"),
        "avg_rating": num(df, cols, "rating", "mean"),
        "manufacturers": int(df[cols["manufacturer"]].nunique()) if "manufacturer" in cols else None,
        "avg_range": num(df, cols, "range", "mean"),
        "avg_battery": num(df, cols, "battery_capacity", "mean"),
        "total_co2": num(df, cols, "co2", "sum"),
    }
    trend = {"labels": [], "values": []}
    if "year" in cols and "sales" in cols and not df.empty:
        t = df.groupby(cols["year"])[cols["sales"]].sum().sort_index()
        trend = {"labels": [str(int(i)) for i in t.index], "values": [round(float(v), 2) for v in t.values]}
    return jsonify({
        "kpis": kpis,
        "sales_by_manufacturer": group(df, cols, "manufacturer", "sales"),
        "sales_by_battery": group(df, cols, "battery_type", "sales"),
        "sales_by_region": group(df, cols, "region", "sales"),
        "sales_by_category": group(df, cols, "category", "sales"),
        "sales_by_country": group(df, cols, "country", "sales"),
        "rating_by_category": group(df, cols, "category", "rating", "mean"),
        "range_by_category": group(df, cols, "category", "range", "mean"),
        "energy_by_category": group(df, cols, "category", "energy", "mean"),
        "sales_trend": trend,
    })


@app.route("/api/columns")
def columns():
    df, cols = load_data()
    if df is None:
        return jsonify({"error": "No dataset found."}), 404
    return jsonify({"detected_columns": cols, "all_columns": list(df.columns)})


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", port=int(os.environ.get("PORT", 5000)))
