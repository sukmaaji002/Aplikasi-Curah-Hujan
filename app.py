import streamlit as st
import pandas as pd
import datetime
import os
import plotly.express as px
import plotly.graph_objects as go
import io

from data_processor import (
    parse_rainfall_workbook,
    parse_rainfall_csv,
    get_station_summary,
    get_monthly_matrix,
    get_cross_station_monthly_matrix,
    get_pmax_cross_matrix,
    add_or_update_rainfall_record,
    save_bulk_monthly_records,
    delete_rainfall_record,
    persist_dataframe,
    MONTH_NAMES_ID
)
from exporter import export_to_excel, export_to_pdf
from hydrology_analysis import (
    get_pmax_matrix,
    calculate_statistical_parameters,
    calculate_gumbel,
    calculate_log_pearson_3,
    get_design_rainfall_summary
)

# Set page config
st.set_page_config(
    page_title="Sistem Filter & Analisis Data Curah Hujan",
    page_icon="🌧️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling
st.markdown("""
<style>
    /* Metric Card Styling */
    div[data-testid="stMetric"] {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        padding: 14px 18px;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.85rem;
        font-weight: 600;
        color: #475569;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.6rem;
        font-weight: 700;
        color: #1E3A8A;
    }
    /* Button primary */
    .stDownloadButton > button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 1rem;
        transition: all 0.2s ease-in-out;
    }
    /* Tab headers */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 44px;
        border-radius: 6px;
        padding: 0 16px;
        font-weight: 600;
    }
    /* Section badge */
    .filter-badge {
        display: inline-block;
        background-color: #E0E7FF;
        color: #3730A3;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-right: 6px;
        margin-bottom: 6px;
    }
</style>
""", unsafe_allow_html=True)

DEFAULT_PARQUET = "data_curah_hujan.parquet"
DEFAULT_EXCEL = "data_curah_hujan_default.xlsx"

@st.cache_data(show_spinner=False)
def load_data(source_type="default", uploaded_file=None, raw_text=""):
    """Memuat data curah hujan dari berbagai sumber (parquet, Excel, CSV, teks)."""
    if source_type == "excel" and uploaded_file is not None:
        df = parse_rainfall_workbook(uploaded_file)
        return df, "File Excel Diunggah"
    
    if source_type == "csv_file" and uploaded_file is not None:
        df = parse_rainfall_csv(uploaded_file)
        return df, "File CSV Diunggah"

    if source_type == "csv_text" and raw_text.strip():
        df = parse_rainfall_csv(raw_text)
        return df, "Teks CSV Ditempel"
    
    # Cek apakah parquet default ada
    if os.path.exists(DEFAULT_PARQUET):
        df = pd.read_parquet(DEFAULT_PARQUET)
        df["Tanggal"] = pd.to_datetime(df["Tanggal"])
        return df, "Data Tersimpan (CH 10 Th 2015-2026)"
    
    # Jika parquet belum ada tapi file excel default ada
    if os.path.exists(DEFAULT_EXCEL):
        df = parse_rainfall_workbook(DEFAULT_EXCEL)
        df.to_parquet(DEFAULT_PARQUET, index=False)
        return df, "Data Tersimpan (CH 10 Th 2015-2026)"

    return pd.DataFrame(), "Tidak Ada Data"


# ==============================================================================
# SIDEBAR: SUMBER DATA & FILTER
# ==============================================================================
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/rain.png", width=64)
    st.title("🌧️ Filter Data Curah Hujan")
    st.caption("Aplikasi Analisis & Ekspor Data Hidrologi")
    st.markdown("---")

    # 1. SUMBER DATA
    st.subheader("📂 1. Sumber Data")
    data_source_opt = st.radio(
        "Pilih Data:",
        [
            "Data Tersimpan (2015 - 2026)",
            "Unggah File Excel (.xlsx, .xls)",
            "Unggah File CSV (.csv)",
            "Tempel Teks CSV Langsung"
        ],
        index=0,
        label_visibility="collapsed"
    )

    uploaded_file = None
    raw_pasted_text = ""
    source_key = "default"

    if data_source_opt == "Unggah File Excel (.xlsx, .xls)":
        source_key = "excel"
        uploaded_file = st.file_uploader("Pilih file Excel (.xlsx, .xls)", type=["xlsx", "xls"])
        if uploaded_file is None:
            st.info("Silakan unggah file Excel data curah hujan.")
    elif data_source_opt == "Unggah File CSV (.csv)":
        source_key = "csv_file"
        uploaded_file = st.file_uploader("Pilih file CSV (.csv)", type=["csv", "txt"])
        if uploaded_file is None:
            st.info("Silakan unggah file CSV data curah hujan.")
    elif data_source_opt == "Tempel Teks CSV Langsung":
        source_key = "csv_text"
        raw_pasted_text = st.text_area(
            "Tempelkan baris data CSV di sini:",
            height=160,
            placeholder="Tahun,2015,No. Stasiun :,\nTgl,Jan,Feb,Mar...\n1,25,5,0..."
        )
        if not raw_pasted_text.strip():
            st.info("Silakan tempel teks format data curah hujan.")

    with st.spinner("Memuat dan mengkategorisasikan data curah hujan..."):
        df_raw, source_name = load_data(source_key, uploaded_file, raw_pasted_text)

    if df_raw.empty:
        st.error("Data curah hujan belum tersedia atau format tidak sesuai.")
        st.stop()

    st.success(f"✅ {len(df_raw):,} data ({len(df_raw['Stasiun'].unique())} stasiun)")
    st.markdown("---")

    # Ambil range data
    min_date = df_raw["Tanggal"].min().date()
    max_date = df_raw["Tanggal"].max().date()
    all_stations = sorted(list(df_raw["Stasiun"].unique()))
    all_years = sorted(list(df_raw["Tahun"].unique()))
    all_categories = sorted(list(df_raw["Kategori_BMKG"].dropna().unique()))

    # 2. FILTER WAKTU
    st.subheader("📅 2. Filter Waktu")
    time_filter_mode = st.radio("Metode Filter Waktu:", ["Rentang Tanggal Bebas", "Pilih Tahun & Bulan", "Musim (Kemarau / Hujan)"])

    if time_filter_mode == "Rentang Tanggal Bebas":
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            start_date = st.date_input("Mulai Dari:", value=datetime.date(2020, 1, 1), min_value=min_date, max_value=max_date)
        with col_d2:
            end_date = st.date_input("Sampai Dengan:", value=datetime.date(2020, 12, 31), min_value=min_date, max_value=max_date)
        
        if start_date > end_date:
            st.error("Tanggal awal tidak boleh melebihi tanggal akhir!")
            st.stop()
        
        selected_years = None
        selected_months = None
        selected_season = None

    elif time_filter_mode == "Pilih Tahun & Bulan":
        start_date, end_date = None, None
        selected_season = None
        
        # Pilihan Tahun
        col_y1, col_y2 = st.columns([3, 1])
        with col_y1:
            all_y_check = st.checkbox("Pilih Semua Tahun", value=False)
        default_y = all_years if all_y_check else [2020]
        selected_years = st.multiselect("Pilih Tahun:", all_years, default=default_y)
        
        # Pilihan Bulan
        month_options = list(MONTH_NAMES_ID.items()) # [(1, 'Januari'), ...]
        all_m_check = st.checkbox("Pilih Semua Bulan", value=True)
        default_m = [m[0] for m in month_options] if all_m_check else [1, 2, 3]
        selected_months = st.multiselect(
            "Pilih Bulan:",
            options=[m[0] for m in month_options],
            format_func=lambda x: MONTH_NAMES_ID[x],
            default=default_m
        )
    else:
        # Musim
        start_date, end_date = None, None
        selected_years = st.multiselect("Pilih Tahun:", all_years, default=all_years[-5:])
        selected_season = st.selectbox(
            "Pilih Musim:",
            ["Musim Hujan (Oktober - April)", "Musim Kemarau (Mei - September)"]
        )
        selected_months = [10, 11, 12, 1, 2, 3, 4] if "Hujan" in selected_season else [5, 6, 7, 8, 9]

    st.markdown("---")

    # 3. FILTER STASIUN
    st.subheader("📍 3. Filter Stasiun")
    col_stn_btn1, col_stn_btn2 = st.columns(2)
    select_all_stn = col_stn_btn1.button("Pilih Semua", use_container_width=True)
    clear_stn = col_stn_btn2.button("Reset Pilihan", use_container_width=True)

    if "selected_stations_state" not in st.session_state:
        st.session_state["selected_stations_state"] = all_stations[:5]

    if select_all_stn:
        st.session_state["selected_stations_state"] = all_stations
    elif clear_stn:
        st.session_state["selected_stations_state"] = [all_stations[0]]

    selected_stations = st.multiselect(
        "Pilih Stasiun Pengamatan:",
        options=all_stations,
        default=st.session_state["selected_stations_state"]
    )
    if not selected_stations:
        st.warning("Pilih minimal satu stasiun!")
        st.stop()

    st.markdown("---")

    # 4. FILTER CURAH HUJAN & INTENSITAS
    st.subheader("🌧️ 4. Filter Intensitas Hujan")
    only_rain_days = st.checkbox("Hanya Hari Hujan (> 0 mm)", value=False)
    include_damaged = st.checkbox("Sertakan Data Sensor Rusak", value=True)
    
    with st.expander("Filter Kategori BMKG & Nilai Khusus"):
        selected_bmkg = st.multiselect("Kategori Intensitas BMKG:", all_categories, default=all_categories)
        max_limit_ch = float(df_raw["Curah_Hujan"].max() or 200.0)
        ch_range = st.slider("Rentang Curah Hujan (mm):", min_value=0.0, max_value=max_limit_ch, value=(0.0, max_limit_ch), step=1.0)


# ==============================================================================
# PROSES FILTER DATA
# ==============================================================================
filtered_df = df_raw.copy()

# Filter Stasiun
filtered_df = filtered_df[filtered_df["Stasiun"].isin(selected_stations)]

# Filter Waktu
if time_filter_mode == "Rentang Tanggal Bebas":
    filtered_df = filtered_df[
        (filtered_df["Tanggal"].dt.date >= start_date) & 
        (filtered_df["Tanggal"].dt.date <= end_date)
    ]
    filter_periode_str = f"{start_date.strftime('%d/%m/%Y')} s/d {end_date.strftime('%d/%m/%Y')}"
else:
    if selected_years:
        filtered_df = filtered_df[filtered_df["Tahun"].isin(selected_years)]
    if selected_months:
        filtered_df = filtered_df[filtered_df["Bulan"].isin(selected_months)]
    
    y_str = ", ".join(map(str, selected_years)) if len(selected_years) <= 4 else f"{len(selected_years)} Tahun Terpilih"
    m_str = f"{len(selected_months)} Bulan" if len(selected_months) > 3 else ", ".join([MONTH_NAMES_ID[m][:3] for m in selected_months])
    filter_periode_str = f"Tahun: {y_str} | Bulan: {m_str}"
    if selected_season:
        filter_periode_str += f" ({selected_season})"

# Filter Kondisi Hujan
if only_rain_days:
    filtered_df = filtered_df[filtered_df["Curah_Hujan"] > 0]

if not include_damaged:
    filtered_df = filtered_df[filtered_df["Status"] != "RUSAK"]

if selected_bmkg:
    filtered_df = filtered_df[filtered_df["Kategori_BMKG"].isin(selected_bmkg)]

# Filter Range Angka
filtered_df = filtered_df[
    (filtered_df["Curah_Hujan"].isna()) | 
    ((filtered_df["Curah_Hujan"] >= ch_range[0]) & (filtered_df["Curah_Hujan"] <= ch_range[1]))
]


# ==============================================================================
# MAIN PANEL: HEADER & BADGES
# ==============================================================================
st.title("🌧️ Analisis & Filter Data Curah Hujan")
st.markdown(
    f"Hasil filter data hidrologi berdasarkan kriteria yang dipilih: "
    f"<span class='filter-badge'>📅 {filter_periode_str}</span> "
    f"<span class='filter-badge'>📍 {len(selected_stations)} Stasiun</span> "
    f"<span class='filter-badge'>🌧️ {'Hari Hujan Saja' if only_rain_days else 'Semua Hari'}</span>",
    unsafe_allow_html=True
)

if filtered_df.empty:
    st.warning("⚠️ Tidak ada data yang sesuai dengan kriteria filter yang dipilih. Silakan sesuaikan filter di sidebar.")
    st.stop()

# Hitung statistik ringkasan
valid_ch = filtered_df["Curah_Hujan"].dropna()
total_ch = valid_ch.sum()
mean_ch = valid_ch.mean() if len(valid_ch) > 0 else 0.0
max_ch = valid_ch.max() if len(valid_ch) > 0 else 0.0

if max_ch > 0:
    max_row = filtered_df[filtered_df["Curah_Hujan"] == max_ch].iloc[0]
    max_info = f"{max_row['Tanggal'].strftime('%d/%m/%Y')} (Stn {max_row['Stasiun']})"
else:
    max_info = "-"

hari_hujan_count = (valid_ch > 0).sum()
hari_kering_count = (valid_ch == 0).sum()
rusak_count = (filtered_df["Status"] == "RUSAK").sum()

# Tampilkan Kartu KPI
col_m1, col_m2, col_m3, col_m4, col_m5, col_m6 = st.columns(6)
col_m1.metric("Total Curah Hujan", f"{total_ch:,.1f} mm")
col_m2.metric("Rata-rata Harian", f"{mean_ch:,.2f} mm")
col_m3.metric("CH Maksimum", f"{max_ch:,.1f} mm", help=f"Terjadi pada {max_info}")
col_m4.metric("Hari Hujan (>0mm)", f"{hari_hujan_count:,}")
col_m5.metric("Hari Kering (0mm)", f"{hari_kering_count:,}")
col_m6.metric("Total Data Baris", f"{len(filtered_df):,}")

st.markdown("<br>", unsafe_allow_html=True)


# ==============================================================================
# DOWNLOAD BUTTONS (EXCEL & PDF)
# ==============================================================================
summary_table_df = get_station_summary(filtered_df)

# Helper fungsi format tampilan matriks hidrologi (0 tetap 0, sensor rusak strip -)
def format_matrix_cell(v):
    if pd.isna(v) or str(v).strip() in ("-", "RUSAK"):
        return "-"
    try:
        val_f = float(v)
        if val_f == 0:
            return "0"
        if val_f.is_integer():
            return f"{int(val_f)}"
        return f"{val_f:.1f}"
    except:
        return str(v)

# Siapkan seluruh matriks bulanan untuk SEMUA stasiun terpilih dan SEMUA tahun yang difilter
all_matrices_export = {}
years_in_filter = sorted(list(filtered_df["Tahun"].unique()))
months_in_filter = sorted(list(filtered_df["Bulan"].unique()))

# Saring df_raw lengkap untuk matriks pengamatan agar hari-hari tanpa hujan (0 mm)
# TIDAK hilang atau menjadi strip (-) akibat filter data harian
df_for_matrices = df_raw[
    df_raw["Stasiun"].isin(selected_stations) &
    df_raw["Tahun"].isin(years_in_filter) &
    df_raw["Bulan"].isin(months_in_filter)
]

for stn in selected_stations:
    for yr in years_in_filter:
        mat_item = get_monthly_matrix(df_for_matrices, stn, yr, months=months_in_filter)
        if not mat_item.empty:
            all_matrices_export[(stn, yr)] = mat_item

cross_monthly_export = get_cross_station_monthly_matrix(df_for_matrices, months=months_in_filter)
pmax_export = get_pmax_cross_matrix(df_for_matrices)

mat_stn = selected_stations[0] if selected_stations else "21b"
mat_year = years_in_filter[0] if years_in_filter else 2020
matrix_download = all_matrices_export.get((mat_stn, mat_year), None)

stn_str_label = ", ".join(selected_stations[:5]) + ("..." if len(selected_stations) > 5 else "")
filter_info_dict = {
    "periode": filter_periode_str,
    "stasiun": f"{len(selected_stations)} Stasiun ({stn_str_label})",
    "kategori": f"{'Hari Hujan > 0mm' if only_rain_days else 'Semua Nilai'} ({ch_range[0]}-{ch_range[1]} mm)",
    "stasiun_matriks": mat_stn,
    "tahun_matriks": str(mat_year)
}

col_down1, col_down2, col_down_space = st.columns([2, 2, 4])

with col_down1:
    with st.spinner("Menyiapkan file Excel (seluruh data & matriks)..."):
        excel_data = export_to_excel(
            df=filtered_df,
            summary_df=summary_table_df,
            matrix_df=matrix_download,
            filter_info=filter_info_dict,
            all_matrices_dict=all_matrices_export,
            cross_station_monthly=cross_monthly_export,
            pmax_matrix=pmax_export
        )
    st.download_button(
        label="📥 Download Hasil (Excel .xlsx)",
        data=excel_data.getvalue(),
        file_name=f"Curah_Hujan_Export_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

with col_down2:
    with st.spinner("Menyiapkan laporan PDF..."):
        pdf_data = export_to_pdf(filtered_df, summary_table_df, filter_info_dict)
    st.download_button(
        label="📄 Download Laporan (PDF .pdf)",
        data=pdf_data.getvalue(),
        file_name=f"Laporan_Curah_Hujan_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
        mime="application/pdf",
        use_container_width=True
    )

st.markdown("<br>", unsafe_allow_html=True)


# ==============================================================================
# TABS TAMPILAN DATA & VISUALISASI
# ==============================================================================
tab_table, tab_matrix, tab_charts, tab_summary, tab_hydro, tab_input = st.tabs([
    "📋 Data Detail Harian",
    "📅 Matriks Hidrologi Bulanan",
    "📈 Grafik Visualisasi & Tren",
    "📊 Ringkasan Statistik Per Stasiun",
    "🌊 Analisis Frekuensi & Kala Ulang",
    "✍️ Input Data Manual"
])

# ----------------- TAB 1: DATA DETAIL -----------------
with tab_table:
    st.subheader("📋 Kategorisasi Data Curah Hujan")
    
    view_granularity = st.radio(
        "Pilih Tingkat Kategorisasi:",
        ["Detail Harian (Hari & Tanggal)", "Rekapitulasi Bulanan (Bulan & Tahun)", "Rekapitulasi Tahunan (Tahun)"],
        horizontal=True
    )

    if view_granularity == "Detail Harian (Hari & Tanggal)":
        years_in_data = sorted(list(filtered_df["Tahun"].unique()))
        col_t1, col_t2, col_t3 = st.columns([2, 1, 1])
        with col_t1:
            st.caption(f"Menampilkan {len(filtered_df):,} baris data terfilter. Dikategorisasikan per Stasiun, Tahun, Bulan, dan Hari.")
        with col_t2:
            tab_yr_filter = st.selectbox(
                "Filter Tahun Tabel:",
                ["Semua Tahun"] + [str(y) for y in years_in_data],
                key="table_year_select"
            )
        with col_t3:
            search_kw = st.text_input("🔍 Cari kata kunci:", placeholder="Ketik tanggal, stasiun, dll...")

        view_df = filtered_df.copy()
        if tab_yr_filter != "Semua Tahun":
            view_df = view_df[view_df["Tahun"] == int(tab_yr_filter)]

        if search_kw:
            mask = view_df.astype(str).apply(lambda row: row.str.contains(search_kw, case=False).any(), axis=1)
            view_df = view_df[mask]

        # Susun kolom rapi: Stasiun, Tahun, Bulan, Hari, Tanggal, Curah Hujan, Klasifikasi BMKG, Status
        display_table = view_df[["Stasiun", "Tahun", "Nama_Bulan", "Hari", "Tanggal", "Curah_Hujan", "Kategori_BMKG", "Status"]].copy()
        display_table["Tanggal"] = display_table["Tanggal"].dt.strftime("%Y-%m-%d")
        display_table.rename(columns={
            "Nama_Bulan": "Bulan",
            "Curah_Hujan": "Curah Hujan (mm)",
            "Kategori_BMKG": "Klasifikasi BMKG"
        }, inplace=True)

        st.dataframe(
            display_table,
            use_container_width=True,
            height=480,
            column_config={
                "Curah Hujan (mm)": st.column_config.NumberColumn(format="%.1f mm"),
                "Tanggal": st.column_config.DateColumn(format="YYYY-MM-DD")
            }
        )

    elif view_granularity == "Rekapitulasi Bulanan (Bulan & Tahun)":
        st.caption("Data teragregasi per Stasiun, Tahun, dan Bulan (Total, Rata-rata, Nilai Maksimum, dan Jumlah Hari Hujan).")
        m_agg = filtered_df.groupby(["Stasiun", "Tahun", "Bulan", "Nama_Bulan"]).agg(
            Total_CH=("Curah_Hujan", "sum"),
            Rata_Rata_CH=("Curah_Hujan", "mean"),
            Maks_CH=("Curah_Hujan", "max"),
            Hari_Hujan=("Curah_Hujan", lambda s: (s > 0).sum()),
            Total_Hari=("Curah_Hujan", "count")
        ).reset_index()
        m_agg.sort_values(by=["Stasiun", "Tahun", "Bulan"], inplace=True)
        m_agg.rename(columns={
            "Nama_Bulan": "Bulan",
            "Total_CH": "Total CH (mm)",
            "Rata_Rata_CH": "Rata-rata Harian (mm)",
            "Maks_CH": "CH Maksimum (mm)",
            "Hari_Hujan": "Jumlah Hari Hujan",
            "Total_Hari": "Total Hari Pengamatan"
        }, inplace=True)
        st.dataframe(
            m_agg,
            use_container_width=True,
            height=480,
            column_config={
                "Total CH (mm)": st.column_config.NumberColumn(format="%.1f mm"),
                "Rata-rata Harian (mm)": st.column_config.NumberColumn(format="%.2f mm"),
                "CH Maksimum (mm)": st.column_config.NumberColumn(format="%.1f mm"),
            }
        )

    else:
        st.caption("Data teragregasi per Stasiun dan Tahun (Total CH Tahunan, Curah Hujan Harian Maksimum Tahunan Pmax, dan Hari Hujan).")
        y_agg = filtered_df.groupby(["Stasiun", "Tahun"]).agg(
            Total_CH=("Curah_Hujan", "sum"),
            Rata_Rata_CH=("Curah_Hujan", "mean"),
            Maks_CH=("Curah_Hujan", "max"),
            Hari_Hujan=("Curah_Hujan", lambda s: (s > 0).sum()),
            Total_Hari=("Curah_Hujan", "count")
        ).reset_index()
        y_agg.sort_values(by=["Stasiun", "Tahun"], inplace=True)
        y_agg.rename(columns={
            "Total_CH": "Total Curah Hujan Tahunan (mm)",
            "Rata_Rata_CH": "Rata-rata Harian (mm)",
            "Maks_CH": "CH Harian Maks Tahunan Pmax (mm)",
            "Hari_Hujan": "Jumlah Hari Hujan",
            "Total_Hari": "Total Hari Pengamatan"
        }, inplace=True)
        st.dataframe(
            y_agg,
            use_container_width=True,
            height=480,
            column_config={
                "Total Curah Hujan Tahunan (mm)": st.column_config.NumberColumn(format="%.1f mm"),
                "Rata-rata Harian (mm)": st.column_config.NumberColumn(format="%.2f mm"),
                "CH Harian Maks Tahunan Pmax (mm)": st.column_config.NumberColumn(format="%.1f mm"),
            }
        )

# ----------------- TAB 2: MATRIKS HIDROLOGI -----------------
with tab_matrix:
    st.subheader("📅 Format Matriks Hidrologi (Tabel Harian vs Bulan)")
    st.caption("Format standar yang digunakan pada laporan hidrologi dan dinas PU/BBWS (Tanggal 1-31 vs Bulan Jan-Des beserta rekapitulasi JUMLAH, RATA-RATA, MAKSIMUM, dan HARI HUJAN).")

    matrix_view_mode = st.radio(
        "Pilih Mode Tampilan Matriks:",
        [
            "Seluruh Matriks (Semua Stasiun & Semua Tahun Terpilih)",
            "Matriks Rekap Bulanan Antar Stasiun (Stasiun vs Bulan)",
            "Matriks Curah Hujan Harian Maksimum Tahunan (Pmax)",
            "Tampilan Fokus 1 Matriks Tertentu"
        ],
        horizontal=True
    )

    years_in_filter = sorted(list(filtered_df["Tahun"].unique()))

    if matrix_view_mode == "Seluruh Matriks (Semua Stasiun & Semua Tahun Terpilih)":
        st.markdown(f"##### 📑 Menampilkan Matriks untuk {len(selected_stations)} Stasiun Terpilih dan {len(years_in_filter)} Tahun Pengamatan")
        st.caption("Gunakan tab stasiun di bawah untuk berpindah antar stasiun. Setiap stasiun menampilkan matriks lengkap untuk seluruh tahun yang Anda pilih.")

        # Buat tabs untuk masing-masing stasiun yang dipilih
        stn_tabs = st.tabs([f"📍 Stasiun {stn}" for stn in selected_stations])
        
        for idx_tab, stn_val in enumerate(selected_stations):
            with stn_tabs[idx_tab]:
                # Pilihan tampilan tahun dalam stasiun ini
                col_ctrl1, col_ctrl2 = st.columns([2, 2])
                with col_ctrl1:
                    show_all_yrs = st.checkbox(f"Tampilkan Semua Tahun Sekaligus ({len(years_in_filter)} Tahun)", value=True, key=f"all_yr_{stn_val}")
                with col_ctrl2:
                    if not show_all_yrs:
                        chosen_yr = st.selectbox("Pilih Tahun Spesifik:", years_in_filter, key=f"sel_yr_{stn_val}")
                        years_to_show = [chosen_yr]
                    else:
                        years_to_show = years_in_filter

                for yr_item in years_to_show:
                    with st.expander(f"📅 Stasiun {stn_val} — Tahun {yr_item}", expanded=(show_all_yrs and len(years_to_show) <= 3 or yr_item == years_to_show[0])):
                        mat_df = get_monthly_matrix(df_for_matrices, stn_val, yr_item, months=months_in_filter)
                        if not mat_df.empty:
                            st.dataframe(
                                mat_df.style.format(format_matrix_cell).background_gradient(
                                    cmap="Blues", subset=mat_df.columns, vmin=0, vmax=100
                                ),
                                use_container_width=True,
                                height=420
                            )
                        else:
                            st.info(f"Tidak ada data untuk Stasiun {stn_val} tahun {yr_item}.")

    elif matrix_view_mode == "Matriks Rekap Bulanan Antar Stasiun (Stasiun vs Bulan)":
        st.markdown("##### 📊 Rekapitulasi Curah Hujan Bulanan Seluruh Stasiun Terpilih (Baris: Stasiun, Kolom: Jan s/d Des)")
        col_c1, col_c2 = st.columns([2, 2])
        with col_c1:
            rekap_yr_mode = st.selectbox("Pilih Periode Tahun:", ["Semua Tahun Terpilih (Akumulasi Total)"] + [f"Tahun {y}" for y in years_in_filter])
        
        yr_param = None if "Semua" in rekap_yr_mode else int(rekap_yr_mode.replace("Tahun", "").strip())
        cross_mat = get_cross_station_monthly_matrix(df_for_matrices, year=yr_param, months=months_in_filter)
        
        if not cross_mat.empty:
            st.dataframe(
                cross_mat.style.format(format_matrix_cell).background_gradient(
                    cmap="Tealgrn", subset=cross_mat.columns[:-1]
                ),
                use_container_width=True,
                height=min(600, len(cross_mat) * 35 + 80)
            )
        else:
            st.info("Tidak ada data untuk ditampilkan.")

    elif matrix_view_mode == "Matriks Curah Hujan Harian Maksimum Tahunan (Pmax)":
        st.markdown("##### ⚡ Matriks Curah Hujan Harian Maksimum Tahunan ($P_{max}$) Seluruh Stasiun Terpilih")
        st.caption("Tabel nilai curah hujan harian tertinggi yang terjadi pada tiap tahun untuk setiap stasiun. Data ini merupakan dasar perhitungan kala ulang hidrologi.")
        
        pmax_mat = get_pmax_cross_matrix(df_for_matrices)
        if not pmax_mat.empty:
            st.dataframe(
                pmax_mat.style.format(format_matrix_cell).background_gradient(
                    cmap="YlOrRd", subset=[c for c in pmax_mat.columns if c not in ("RATA-RATA (mm)", "MAKS TERTINGGI (mm)")]
                ),
                use_container_width=True,
                height=min(600, len(pmax_mat) * 35 + 80)
            )
        else:
            st.info("Tidak ada data Pmax yang ditemukan.")

    else:
        # Tampilan Fokus 1 Matriks Tertentu
        st.markdown("##### 🔍 Tampilan Fokus Matriks Tunggal")
        col_m_stn, col_m_yr = st.columns(2)
        with col_m_stn:
            matrix_stn_select = st.selectbox("Pilih Stasiun:", selected_stations, key="focus_stn")
        with col_m_yr:
            avail_years = sorted(list(filtered_df[filtered_df["Stasiun"] == matrix_stn_select]["Tahun"].unique()))
            matrix_yr_select = st.selectbox("Pilih Tahun:", avail_years if avail_years else [2020], key="focus_yr")

        if matrix_stn_select and matrix_yr_select:
            mat_display = get_monthly_matrix(df_for_matrices, matrix_stn_select, matrix_yr_select, months=months_in_filter)
            if not mat_display.empty:
                st.dataframe(
                    mat_display.style.format(format_matrix_cell).background_gradient(
                        cmap="Blues", subset=mat_display.columns, vmin=0, vmax=100
                    ),
                    use_container_width=True,
                    height=520
                )
            else:
                st.info("Tidak ada data untuk kombinasi stasiun dan tahun tersebut.")

# ----------------- TAB 3: GRAFIK VISUALISASI -----------------
with tab_charts:
    st.subheader("📈 Analisis Grafik Interaktif")

    chart_type = st.radio(
        "Pilih Jenis Grafik:",
        ["Tren Curah Hujan Harian (Line)", "Total Curah Hujan Bulanan (Bar)", "Distribusi Intensitas BMKG (Donut)", "Perbandingan Akumulasi Stasiun (Bar)"],
        horizontal=True
    )

    if chart_type == "Tren Curah Hujan Harian (Line)":
        st.markdown("##### 🌊 Tren Curah Hujan Harian Per Stasiun")
        # Batasi stasiun agar grafik tidak terlalu padat jika pilih banyak
        stn_to_plot = selected_stations[:8]
        if len(selected_stations) > 8:
            st.info(f"💡 Menampilkan 8 stasiun pertama ({', '.join(stn_to_plot)}) agar grafik mudah dibaca.")

        chart_df = filtered_df[filtered_df["Stasiun"].isin(stn_to_plot)].copy()
        
        fig = px.line(
            chart_df,
            x="Tanggal",
            y="Curah_Hujan",
            color="Stasiun",
            labels={"Curah_Hujan": "Curah Hujan (mm)", "Tanggal": "Tanggal Pengamatan"},
            title="Tren Fluktuasi Curah Hujan Harian"
        )
        fig.update_layout(
            hovermode="x unified",
            xaxis=dict(rangeslider=dict(visible=True)),
            height=480,
            template="plotly_white"
        )
        st.plotly_chart(fig, use_container_width=True)

    elif chart_type == "Total Curah Hujan Bulanan (Bar)":
        st.markdown("##### 📊 Total Curah Hujan Per Bulan")
        # Agregasi per Tahun dan Bulan
        monthly_agg = filtered_df.groupby(["Tahun", "Bulan", "Nama_Bulan"])["Curah_Hujan"].sum().reset_index()
        monthly_agg["Periode"] = monthly_agg["Nama_Bulan"].str[:3] + " " + monthly_agg["Tahun"].astype(str)
        monthly_agg.sort_values(by=["Tahun", "Bulan"], inplace=True)

        fig_bar = px.bar(
            monthly_agg,
            x="Periode",
            y="Curah_Hujan",
            color="Curah_Hujan",
            color_continuous_scale="Blues",
            labels={"Curah_Hujan": "Total Curah Hujan (mm)", "Periode": "Bulan & Tahun"},
            title="Akumulasi Curah Hujan Per Periode Bulanan"
        )
        fig_bar.update_layout(height=480, template="plotly_white")
        st.plotly_chart(fig_bar, use_container_width=True)

    elif chart_type == "Distribusi Intensitas BMKG (Donut)":
        st.markdown("##### 🍩 Proporsi Klasifikasi Curah Hujan (BMKG)")
        bmkg_counts = filtered_df["Kategori_BMKG"].value_counts().reset_index()
        bmkg_counts.columns = ["Kategori", "Jumlah Hari"]

        color_map = {
            "Berawan / Tanpa Hujan (0 mm)": "#CBD5E1",
            "Hujan Sangat Ringan (0.1 - 5 mm)": "#93C5FD",
            "Hujan Ringan (5 - 20 mm)": "#60A5FA",
            "Hujan Sedang (20 - 50 mm)": "#2563EB",
            "Hujan Lebat (50 - 100 mm)": "#F59E0B",
            "Hujan Sangat Lebat (100 - 150 mm)": "#EF4444",
            "Hujan Ekstrem (> 150 mm)": "#7F1D1D",
            "Sensor Rusak": "#6B7280"
        }

        fig_pie = px.pie(
            bmkg_counts,
            names="Kategori",
            values="Jumlah Hari",
            hole=0.45,
            color="Kategori",
            color_discrete_map=color_map,
            title="Distribusi Kejadian Hujan Berdasarkan Kategori BMKG"
        )
        fig_pie.update_layout(height=480, template="plotly_white")
        st.plotly_chart(fig_pie, use_container_width=True)

    elif chart_type == "Perbandingan Akumulasi Stasiun (Bar)":
        st.markdown("##### 🏆 Ranking Stasiun Berdasarkan Total Curah Hujan")
        stn_sum = summary_table_df.sort_values(by="Total Curah Hujan (mm)", ascending=True)

        fig_stn = px.bar(
            stn_sum,
            x="Total Curah Hujan (mm)",
            y="Stasiun",
            orientation="h",
            color="Total Curah Hujan (mm)",
            color_continuous_scale="Tealgrn",
            labels={"Total Curah Hujan (mm)": "Total Curah Hujan (mm)", "Stasiun": "Nomor Stasiun"},
            title="Perbandingan Total Curah Hujan Antar Stasiun"
        )
        fig_stn.update_layout(height=max(450, len(stn_sum) * 20), template="plotly_white")
        st.plotly_chart(fig_stn, use_container_width=True)

# ----------------- TAB 4: RINGKASAN STASIUN -----------------
with tab_summary:
    st.subheader("📊 Ringkasan Statistik Per Stasiun")
    st.caption("Rangkuman statistik lengkap untuk setiap stasiun pengamatan berdasarkan periode waktu yang difilter.")

    st.dataframe(
        summary_table_df,
        use_container_width=True,
        column_config={
            "Total Curah Hujan (mm)": st.column_config.NumberColumn(format="%.1f mm"),
            "Rata-rata Harian (mm)": st.column_config.NumberColumn(format="%.2f mm"),
            "Curah Hujan Maks (mm)": st.column_config.NumberColumn(format="%.1f mm"),
            "Hari Hujan (>0 mm)": st.column_config.NumberColumn(format="%d hari"),
            "Hari Kering (0 mm)": st.column_config.NumberColumn(format="%d hari"),
            "Sensor Rusak": st.column_config.NumberColumn(format="%d hari"),
            "Total Data Hari": st.column_config.NumberColumn(format="%d hari"),
        }
    )

# ----------------- TAB 5: ANALISIS HIDROLOGI & KALA ULANG -----------------
with tab_hydro:
    st.subheader("🌊 Analisis Frekuensi Hidrologi & Curah Hujan Rancangan (Kala Ulang)")
    st.caption("Perhitungan curah hujan rancangan metode Gumbel dan Log Pearson Tipe III untuk kala ulang T = 2, 5, 10, 25, 50, dan 100 Tahun (Standar SNI & PU Perencanaan Bangunan Air/Drainase).")

    col_h_stn, col_h_info = st.columns([2, 3])
    with col_h_stn:
        h_stn = st.selectbox("Pilih Stasiun untuk Dianalisis:", selected_stations, key="hydro_stn_select")

    if h_stn:
        sub_h = df_raw[(df_raw["Stasiun"] == h_stn) & (df_raw["Curah_Hujan"].notna())]
        pmax_series = sub_h.groupby("Tahun")["Curah_Hujan"].max()
        stats_p = calculate_statistical_parameters(pmax_series)
        
        if stats_p:
            # Metric cards
            col_k1, col_k2, col_k3, col_k4, col_k5, col_k6 = st.columns(6)
            col_k1.metric("Jumlah Tahun (n)", f"{stats_p['n']} Tahun")
            col_k2.metric("Rata-rata Pmax (X)", f"{stats_p['mean']:.1f} mm")
            col_k3.metric("Standar Deviasi (S)", f"{stats_p['std']:.2f} mm")
            col_k4.metric("Koef. Variasi (Cv)", f"{stats_p['cv']:.3f}")
            col_k5.metric("Koef. Skewness (Cs)", f"{stats_p['cs']:.3f}")
            col_k6.metric("Koef. Kurtosis (Ck)", f"{stats_p['ck']:.3f}")

            st.markdown("<br>", unsafe_allow_html=True)

            # Design rainfall table and chart
            col_r1, col_r2 = st.columns([3, 4])
            with col_r1:
                st.markdown("##### 📋 Tabel Curah Hujan Rancangan (mm)")
                design_df = get_design_rainfall_summary(df_raw, h_stn)
                st.dataframe(design_df, use_container_width=True, hide_index=True)

            with col_r2:
                st.markdown("##### 📈 Kurva Pertumbuhan Curah Hujan Rancangan")
                if not design_df.empty:
                    fig_h = go.Figure()
                    fig_h.add_trace(go.Scatter(
                        x=design_df["Kala Ulang (T)"],
                        y=design_df["Gumbel (mm)"],
                        mode="lines+markers",
                        name="Metode Gumbel",
                        line=dict(color="#1E3A8A", width=3)
                    ))
                    fig_h.add_trace(go.Scatter(
                        x=design_df["Kala Ulang (T)"],
                        y=design_df["Log Pearson III (mm)"],
                        mode="lines+markers",
                        name="Metode Log Pearson III",
                        line=dict(color="#0F766E", width=3, dash="dash")
                    ))
                    fig_h.update_layout(
                        height=350,
                        template="plotly_white",
                        xaxis_title="Periode Ulang (T)",
                        yaxis_title="Curah Hujan Rancangan (mm)",
                        hovermode="x unified"
                    )
                    st.plotly_chart(fig_h, use_container_width=True)


# ----------------- TAB 6: INPUT DATA MANUAL -----------------
with tab_input:
    st.subheader("✍️ Input & Pembaruan Data Curah Hujan Manual")
    st.caption("Tambahkan data curah hujan harian terbaru atau perbarui data pengamatan stasiun langsung ke sistem.")

    input_mode = st.radio(
        "Pilih Metode Input:",
        ["Input Data Harian Tunggal (Single Entry)", "Input Matriks 1 Bulan Penuh (Grid Editor)"],
        horizontal=True
    )

    if input_mode == "Input Data Harian Tunggal (Single Entry)":
        st.markdown("##### 📝 Formulir Input Data Harian Tunggal")
        with st.form("form_single_entry"):
            col_in1, col_in2 = st.columns(2)
            
            with col_in1:
                station_mode = st.radio("Pilihan Stasiun:", ["Pilih Stasiun Terdaftar", "Tambah Stasiun Baru"], horizontal=True)
                if station_mode == "Pilih Stasiun Terdaftar":
                    stn_input = st.selectbox("Nama / Kode Stasiun:", all_stations)
                else:
                    stn_input = st.text_input("Kode Stasiun Baru (misal: 69, 70a):").strip()
                
                tgl_input = st.date_input("Tanggal Pengamatan:", value=datetime.date.today())
            
            with col_in2:
                status_input = st.radio("Status Alat Pengukur:", ["Normal", "RUSAK"], horizontal=True,
                                        help="Pilih RUSAK jika alat pengukur hujan tidak berfungsi pada tanggal ini.")
                
                if status_input == "Normal":
                    ch_input = st.number_input("Curah Hujan (mm):", min_value=0.0, max_value=500.0, value=0.0, step=0.1, format="%.1f",
                                              help="Ketik 0 jika cuaca cerah/berawan dan tidak ada hujan sama sekali.")
                else:
                    ch_input = None
                    st.info("⚠️ Sensor berstatus RUSAK. Curah hujan akan otomatis ditandai strip (-) dalam matriks pengamatan.")

            submit_single = st.form_submit_button("💾 Simpan Data Harian", use_container_width=True, type="primary")

            if submit_single:
                if not stn_input:
                    st.error("Silakan tentukan nama / kode stasiun!")
                else:
                    new_df = add_or_update_rainfall_record(
                        df_main=df_raw,
                        station=stn_input,
                        date_val=tgl_input,
                        rain_val=ch_input,
                        status=status_input
                    )
                    saved = persist_dataframe(new_df)
                    if saved:
                        st.cache_data.clear()
                        st.success(f"✅ Data Stasiun {stn_input} tanggal {tgl_input.strftime('%d-%m-%Y')} ({'RUSAK (-)' if status_input == 'RUSAK' else f'{ch_input:.1f} mm'}) berhasil disimpan!")
                        st.rerun()
                    else:
                        st.error("Gagal menyimpan data ke sistem penyimpanan.")

    else:
        st.markdown("##### 📅 Input Matriks 1 Bulan Penuh (Tabel 1 s/d 31 Hari)")
        st.caption("Isi seluruh nilai curah hujan harian untuk stasiun dan bulan yang dipilih dalam satu tabel sekaligus.")

        col_b1, col_b2, col_b3 = st.columns(3)
        with col_b1:
            bulk_stn = st.selectbox("Pilih Stasiun:", all_stations, key="bulk_stn")
        with col_b2:
            bulk_yr = st.number_input("Tahun:", min_value=2015, max_value=2035, value=2026, step=1, key="bulk_yr")
        with col_b3:
            bulk_m = st.selectbox("Bulan:", list(MONTH_NAMES_ID.keys()), format_func=lambda x: f"{x} - {MONTH_NAMES_ID[x]}", key="bulk_m")

        import calendar
        days_in_month = calendar.monthrange(int(bulk_yr), int(bulk_m))[1]

        # Ambil data yang sudah ada untuk bulan ini (jika ada)
        existing_subset = df_raw[
            (df_raw["Stasiun"] == bulk_stn) & 
            (df_raw["Tahun"] == int(bulk_yr)) & 
            (df_raw["Bulan"] == int(bulk_m))
        ].copy()
        
        existing_map = {}
        for _, row in existing_subset.iterrows():
            existing_map[int(row["Hari"])] = {
                "Curah_Hujan": row["Curah_Hujan"] if pd.notna(row["Curah_Hujan"]) else 0.0,
                "Status": str(row["Status"])
            }

        grid_data = []
        for d in range(1, days_in_month + 1):
            ex = existing_map.get(d, {"Curah_Hujan": 0.0, "Status": "Normal"})
            grid_data.append({
                "Hari": d,
                "Tanggal": f"{int(bulk_yr)}-{int(bulk_m):02d}-{d:02d}",
                "Curah Hujan (mm)": float(ex["Curah_Hujan"]) if ex["Status"] != "RUSAK" else 0.0,
                "Status": "RUSAK" if ex["Status"] == "RUSAK" else "Normal"
            })

        df_grid = pd.DataFrame(grid_data)

        st.info(f"💡 Menampilkan {days_in_month} hari untuk **Stasiun {bulk_stn}** — Bulan **{MONTH_NAMES_ID[int(bulk_m)]} {int(bulk_yr)}**. Klik langsung pada sel untuk mengubah angka curah hujan atau status.")

        edited_df = st.data_editor(
            df_grid,
            use_container_width=True,
            num_rows="fixed",
            height=min(500, days_in_month * 36 + 60),
            column_config={
                "Hari": st.column_config.NumberColumn("Hari", disabled=True),
                "Tanggal": st.column_config.TextColumn("Tanggal", disabled=True),
                "Curah Hujan (mm)": st.column_config.NumberColumn("Curah Hujan (mm)", min_value=0.0, max_value=500.0, step=0.1, format="%.1f mm"),
                "Status": st.column_config.SelectboxColumn("Status", options=["Normal", "RUSAK"], required=True)
            }
        )

        col_save1, col_save2 = st.columns([2, 4])
        with col_save1:
            if st.button(f"💾 Simpan Seluruh Bulan ({MONTH_NAMES_ID[int(bulk_m)]} {int(bulk_yr)})", type="primary", use_container_width=True):
                daily_items = []
                for _, r in edited_df.iterrows():
                    daily_items.append({
                        "Hari": int(r["Hari"]),
                        "Curah_Hujan": float(r["Curah Hujan (mm)"]) if r["Status"] != "RUSAK" else None,
                        "Status": r["Status"]
                    })
                new_df = save_bulk_monthly_records(
                    df_main=df_raw,
                    station=bulk_stn,
                    year=int(bulk_yr),
                    month=int(bulk_m),
                    daily_items=daily_items
                )
                saved = persist_dataframe(new_df)
                if saved:
                    st.cache_data.clear()
                    st.success(f"✅ Data {days_in_month} hari untuk Stasiun {bulk_stn} ({MONTH_NAMES_ID[int(bulk_m)]} {int(bulk_yr)}) berhasil disimpan secara permanen!")
                    st.rerun()
                else:
                    st.error("Gagal menyimpan data.")

    # Bagian Riwayat Input Manual
    st.markdown("---")
    st.markdown("##### 📜 Catatan Riwayat Input Data Manual")
    if os.path.exists("manual_records_log.csv"):
        log_df = pd.read_csv("manual_records_log.csv")
        st.dataframe(log_df.tail(25).iloc[::-1], use_container_width=True, height=260)
    else:
        st.caption("Belum ada riwayat input manual yang dicatat.")



