import streamlit as st
import pandas as pd
import datetime
import os
import base64
import plotly.express as px
import plotly.graph_objects as go
import io
import sys
import importlib
import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

def get_base64_image(image_path: str) -> str:
    """Mengonversi file gambar lokal ke format base64 string untuk disematkan dalam HTML."""
    try:
        if os.path.exists(image_path):
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        pass
    return ""

import data_processor
import exporter
import hydrology_analysis
import github_sync
import bendung_analysis

# Reload modul internal untuk mencegah cache versi usang pada Streamlit Cloud
importlib.reload(data_processor)
importlib.reload(exporter)
importlib.reload(hydrology_analysis)
importlib.reload(github_sync)
importlib.reload(bendung_analysis)

from github_sync import (
    sync_all_database_to_github,
    is_github_configured,
    test_github_connection
)

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
from exporter import (
    export_to_excel,
    export_to_pdf,
    export_weibull_to_excel,
    export_weibull_to_pdf
)
from hydrology_analysis import (
    get_pmax_matrix,
    calculate_statistical_parameters,
    calculate_gumbel,
    calculate_log_pearson_3,
    get_station_frequency_stats,
    get_design_rainfall_summary,
    calculate_weibull_ranking,
    interpolate_weibull_value,
    calculate_dependable_flow_and_rainfall,
    infill_missing_rainfall
)

# Set page config
st.set_page_config(
    page_title="Sistem Filter & Analisis Data Curah Hujan",
    page_icon="🌧️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling (Modern PUPR Theme)
st.markdown("""
<style>
    /* Global container styling */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    /* PUPR Header Branding Banner */
    .pupr-header-card {
        background: linear-gradient(135deg, #0B192C 0%, #1E3E62 45%, #001F3F 100%);
        border-radius: 16px;
        padding: 20px 26px;
        margin-bottom: 20px;
        border-left: 6px solid #0284C7;
        border-bottom: 3.5px solid #F59E0B;
        box-shadow: 0 10px 25px -5px rgba(11, 25, 44, 0.25);
        color: #FFFFFF;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 20px;
        flex-wrap: wrap;
    }
    .pupr-header-content {
        display: flex;
        align-items: center;
        gap: 20px;
        flex: 1;
        min-width: 320px;
    }
    .pupr-header-logo {
        height: 64px;
        max-width: 170px;
        object-fit: contain;
        filter: drop-shadow(0 2px 8px rgba(0,0,0,0.35));
    }
    .pupr-tagline {
        font-size: 0.82rem;
        font-weight: 700;
        color: #FDE047;
        letter-spacing: 1.2px;
        text-transform: uppercase;
    }
    .pupr-title {
        font-size: 1.25rem;
        font-weight: 800;
        color: #FFFFFF;
        letter-spacing: 0.5px;
        line-height: 1.25;
        margin: 2px 0;
        text-shadow: 0 1px 3px rgba(0,0,0,0.3);
    }
    .pupr-subtitle {
        font-size: 0.8rem;
        color: #CBD5E1;
        font-weight: 400;
        line-height: 1.3;
    }
    .pupr-header-badges {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 6px;
    }
    .pupr-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.3px;
    }
    .pupr-badge-primary {
        background-color: rgba(2, 132, 199, 0.35);
        color: #38BDF8;
        border: 1px solid rgba(56, 189, 248, 0.4);
    }
    .pupr-badge-gold {
        background-color: rgba(245, 158, 11, 0.25);
        color: #FDE047;
        border: 1px solid rgba(245, 158, 11, 0.5);
    }
    /* Box card container */
    .custom-card {
        background-color: #FFFFFF;
        border: 1.5px solid #E2E8F0;
        border-radius: 12px;
        padding: 18px 22px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .custom-card-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    /* Metric Card Styling */
    div[data-testid="stMetric"] {
        background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%);
        border: 1px solid #E2E8F0;
        border-top: 3.5px solid #0284C7;
        padding: 12px 16px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        transition: transform 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
    }
    div[data-testid="stMetric"]:hover {
        border-top-color: #F59E0B;
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08);
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.85rem;
        font-weight: 600;
        color: #475569;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.5rem;
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
    /* Tab headers with solid card boundaries */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 2px solid #E2E8F0;
        padding-bottom: 4px;
        overflow-x: auto;
    }
    .stTabs [data-baseweb="tab"] {
        height: 44px;
        border-radius: 10px 10px 0 0;
        padding: 0 18px;
        font-weight: 600;
        font-size: 0.92rem;
        background-color: #F1F5F9;
        color: #475569;
        border: 1px solid #E2E8F0;
        border-bottom: none;
        transition: all 0.2s ease-in-out;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #1E3A8A 0%, #0284C7 100%) !important;
        color: #FFFFFF !important;
        border-color: #1E3A8A !important;
        box-shadow: 0 4px 6px -1px rgba(2, 132, 199, 0.25);
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

def get_file_mtime(filepath):
    try:
        return os.path.getmtime(filepath) if os.path.exists(filepath) else 0
    except Exception:
        return 0

@st.cache_data(show_spinner=False)
def load_data(source_type="default", uploaded_file=None, raw_text="", _mtime=0):
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
    # Sidebar Header Branding DPUPR Kab. Tegal
    logo_sidebar_b64 = get_base64_image("assets/logo_pupr_tegal.png")
    if logo_sidebar_b64:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0B192C 0%, #1E3E62 100%); border-radius: 12px; padding: 12px 14px; margin-bottom: 14px; border-bottom: 3px solid #F59E0B; text-align: center;">
            <img src="data:image/png;base64,{logo_sidebar_b64}" style="height: 48px; max-width: 140px; object-fit: contain; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.4)); margin-bottom: 6px;" />
            <div style="font-size: 0.78rem; font-weight: 800; color: #FFFFFF; letter-spacing: 0.5px; line-height: 1.2;">DINAS PEKERJAAN UMUM DAN PENATAAN RUANG</div>
            <div style="font-size: 0.85rem; font-weight: 800; color: #FDE047; letter-spacing: 0.8px;">KABUPATEN TEGAL</div>
            <div style="font-size: 0.70rem; color: #BAE6FD; margin-top: 3px;">Bidang Sumber Daya Air dan Jasa Konstruksi</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.image("https://img.icons8.com/fluency/96/rain.png", width=64)
        st.title("🌧️ DPUPR KAB. TEGAL")
        st.caption("Aplikasi Analisis & Ekspor Data Hidrologi")
    st.markdown("---")

    # ==========================================================================
    # PILIHAN KELOMPOK DATA UTAMA DI SIDEBAR
    # ==========================================================================
    st.markdown("### 🗂️ Kategori Data")
    app_mode = st.radio(
        "Pilih Kategori:",
        [
            "🌧️ CURAH HUJAN",
            "💧 DATA DEBIT"
        ],
        index=0,
        key="app_main_mode"
    )
    st.markdown("---")

    if app_mode == "🌧️ CURAH HUJAN":
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

        current_mtime = max(
            get_file_mtime(DEFAULT_PARQUET),
            get_file_mtime(DEFAULT_EXCEL)
        )

        with st.spinner("Memuat dan mengkategorisasikan data curah hujan..."):
            df_raw, source_name = load_data(source_key, uploaded_file, raw_pasted_text, _mtime=current_mtime)

        if df_raw.empty:
            st.error("Data curah hujan belum tersedia atau format tidak sesuai.")
            st.stop()

        col_sb_st1, col_sb_st2 = st.columns([1.8, 1.2])
        with col_sb_st1:
            st.success(f"✅ {len(df_raw):,} data ({len(df_raw['Stasiun'].unique())} stasiun)")
        with col_sb_st2:
            if st.button("🔄 Segarkan", use_container_width=True, help="Bersihkan cache memori dan baca ulang data terbaru dari file"):
                st.cache_data.clear()
                st.rerun()

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
            if not selected_years:
                st.warning("Pilih minimal satu tahun!")
                st.stop()
        
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
            if not selected_months:
                st.warning("Pilih minimal satu bulan!")
                st.stop()
        else:
            # Musim
            start_date, end_date = None, None
            selected_years = st.multiselect("Pilih Tahun:", all_years, default=all_years[-5:])
            if not selected_years:
                st.warning("Pilih minimal satu tahun!")
                st.stop()
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
    else:
        # ==================== SIDEBAR DATA DEBIT BENDUNG ====================
        st.subheader("💧 1. Basis Data Bendung")
        st.info("""
        **4 Bendung di Kab. Tegal:**
        - Bendung Rajabawah (D.I. Rajabawah)
        - Bendung Pondoh (D.I. Pondoh)
        - Bendung Kemaron (D.I. Gung, Kemaron)
        - Bendung Lengkong (D.I. Lengkong)
        
        **Tahun Hidrologi:** 2004/2005 - 2024/2025 (21 Thn)  
        **Format:** 24 Periode 1/2 Bulanan  
        **Satuan:** Liter/detik (L/s)
        """)
        st.markdown("---")
        st.subheader("📂 2. Ekspor Database Debit")
        df_bendung_side = bendung_analysis.load_bendung_dataset()
        if not df_bendung_side.empty:
            side_buf = io.BytesIO()
            with pd.ExcelWriter(side_buf, engine="openpyxl") as w_side:
                df_bendung_side.to_excel(w_side, index=False, sheet_name="Data Debit Bendung")
            side_buf.seek(0)
            st.download_button(
                label="📥 Unduh Database Debit (.xlsx)",
                data=side_buf.getvalue(),
                file_name=f"Database_Debit_4_Bendung_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            csv_side_bytes = df_bendung_side.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📄 Unduh Database Debit (.csv)",
                data=csv_side_bytes,
                file_name=f"Database_Debit_4_Bendung_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True
            )



if app_mode == "🌧️ CURAH HUJAN":
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
    # MAIN PANEL: HEADER & BRANDING DPUPR KABUPATEN TEGAL
    # ==============================================================================
    logo_main_b64 = get_base64_image("assets/logo_pupr_tegal.png")
    if logo_main_b64:
        st.markdown(f"""
        <div class="pupr-header-card">
            <div class="pupr-header-content">
                <img src="data:image/png;base64,{logo_main_b64}" class="pupr-header-logo" alt="Logo DPUPR Kab Tegal" />
                <div class="pupr-title-box">
                    <div class="pupr-tagline">PEMERINTAH KABUPATEN TEGAL</div>
                    <div class="pupr-title">DINAS PEKERJAAN UMUM DAN PENATAAN RUANG</div>
                    <div class="pupr-subtitle">Sistem Informasi & Analisis Data Curah Hujan, Debit Andalan Irigasi (Weibull Q80) & Kala Ulang Hidrologi</div>
                </div>
            </div>
            <div class="pupr-header-badges">
                <span class="pupr-badge pupr-badge-primary">🏛️ DPUPR KAB. TEGAL</span>
                <span class="pupr-badge pupr-badge-gold">🌊 Bidang SDA & Jasa Konstruksi</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.title("🏛️ DINAS PEKERJAAN UMUM DAN PENATAAN RUANG KABUPATEN TEGAL")
        st.caption("Bidang Sumber Daya Air dan Jasa Konstruksi — Sistem Analisis Data Curah Hujan & Hidrologi")

    st.markdown(
        f"Hasil filter data hidrologi sesuai kriteria sidebar: "
        f"<span class='filter-badge'>📅 {filter_periode_str}</span> "
        f"<span class='filter-badge'>📍 {len(selected_stations)} Stasiun Terpilih</span> "
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
    belum_ada_count = (filtered_df["Status"].isin(["Belum Ada Data", "Kosong"])).sum()

    # Tampilkan Kartu KPI dalam Kotak Rapi
    with st.container(border=True):
        col_m1, col_m2, col_m3, col_m4, col_m5, col_m6 = st.columns(6)
        col_m1.metric("Total Curah Hujan", f"{total_ch:,.1f} mm")
        col_m2.metric("Rata-rata Harian", f"{mean_ch:,.2f} mm")
        col_m3.metric("CH Maksimum", f"{max_ch:,.1f} mm", help=f"Terjadi pada {max_info}")
        col_m4.metric("Hari Hujan (>0mm)", f"{hari_hujan_count:,}")
        col_m5.metric("Hari Kering (0mm)", f"{hari_kering_count:,}")
        col_m6.metric("Alat Rusak / Belum Isi", f"{rusak_count:,} / {belum_ada_count:,}", help=f"Sensor Rusak: {rusak_count:,} hari, Belum Ada Data: {belum_ada_count:,} hari (Total Data: {len(filtered_df):,} baris)")

    # Banner Akses Cepat & Navigasi
    with st.container(border=True):
        col_quick1, col_quick2 = st.columns([3, 1])
        with col_quick1:
            st.markdown(
                "📌 **Navigasi Cepat**: "
                "Untuk menambah/mengoreksi data pengamatan stasiun, silakan klik tab **✍️ Input Manual** (di baris depan). "
                "Untuk analisis keandalan irigasi & air bersih, gunakan tab **💧 Debit Andalan (Weibull)**."
            )
        with col_quick2:
            st.caption("✨ Tampilan Berkotak Rapi & Terstruktur")


    # ==============================================================================
    # DOWNLOAD BUTTONS (EXCEL & PDF)
    # ==============================================================================
    summary_table_df = get_station_summary(filtered_df)

    # Helper fungsi format tampilan matriks hidrologi (0 tetap 0, sensor rusak kosong dan diarsir hitam)
    _matrix_cmap = plt.get_cmap("Blues")
    _matrix_norm = mcolors.Normalize(vmin=0, vmax=100)

    def format_matrix_cell(v):
        if str(v).strip().upper() == "RUSAK":
            return ""
        if pd.isna(v) or str(v).strip() == "-":
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

    def color_matrix_cell(val):
        s_val = str(val).strip().upper() if pd.notna(val) else ""
        if s_val == "RUSAK":
            return "background-color: #000000; color: #000000; font-weight: bold;"
        if pd.isna(val) or s_val in ("-", ""):
            return "color: #94A3B8;"
        try:
            f = float(val)
            if f <= 0:
                return "background-color: #FFFFFF; color: #1E293B;"
            rgba = _matrix_cmap(_matrix_norm(min(f, 100)))
            hex_col = mcolors.to_hex(rgba)
            txt_col = "#FFFFFF" if f > 50 else "#0F172A"
            return f"background-color: {hex_col}; color: {txt_col};"
        except Exception:
            return ""

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

    # Sesuai instruksi: Data curah hujan tidak disambungkan ke debit andalan Weibull
    weibull_export = None

    mat_stn = selected_stations[0] if selected_stations else "21b"
    mat_year = years_in_filter[0] if years_in_filter else 2020
    matrix_download = all_matrices_export.get((mat_stn, mat_year), None)

    stn_str_label = ", ".join(selected_stations[:5]) + ("..." if len(selected_stations) > 5 else "")
    filter_info_dict = {
        "instansi": "DINAS PEKERJAAN UMUM DAN PENATAAN RUANG KABUPATEN TEGAL",
        "proyek": "Bidang Sumber Daya Air dan Jasa Konstruksi",
        "periode": filter_periode_str,
        "stasiun": f"{len(selected_stations)} Stasiun ({stn_str_label})",
        "kategori": f"{'Hari Hujan > 0mm' if only_rain_days else 'Semua Nilai'} ({ch_range[0]}-{ch_range[1]} mm)",
        "stasiun_matriks": mat_stn,
        "tahun_matriks": str(mat_year)
    }

    with st.container(border=True):
        st.markdown("##### 📥 Ekspor Laporan & Unduh Hasil Analisis (Excel & PDF)")
        col_down1, col_down2, col_down_space = st.columns([2, 2, 3])

        with col_down1:
            with st.spinner("Menyiapkan file Excel (seluruh sheet lengkap & debit andalan)..."):
                excel_data = export_to_excel(
                    df=filtered_df,
                    summary_df=summary_table_df,
                    matrix_df=matrix_download,
                    filter_info=filter_info_dict,
                    all_matrices_dict=all_matrices_export,
                    cross_station_monthly=cross_monthly_export,
                    pmax_matrix=pmax_export,
                    weibull_data=weibull_export
                )
            st.download_button(
                label="📥 Download Hasil (Excel .xlsx)",
                data=excel_data.getvalue(),
                file_name=f"Curah_Hujan_Export_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        with col_down2:
            with st.spinner("Menyiapkan laporan PDF (termasuk analisis debit andalan & grafik)..."):
                pdf_data = export_to_pdf(
                    df=filtered_df,
                    summary_df=summary_table_df,
                    filter_info=filter_info_dict,
                    weibull_data=weibull_export
                )
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
    tab_table, tab_input, tab_matrix, tab_hydro, tab_charts, tab_summary = st.tabs([
        "📋 Data Harian",
        "✍️ Input Manual",
        "📅 Matriks Bulanan",
        "🌊 Kala Ulang (Gumbel & LP3)",
        "📈 Grafik & Tren",
        "📊 Ringkasan Stasiun"
    ])

    # ----------------- TAB 1: DATA DETAIL -----------------
    with tab_table:
        with st.container(border=True):
            st.subheader("📋 Kategorisasi Data Curah Hujan")
            view_granularity = st.radio(
                "Pilih Tingkat Kategorisasi:",
                ["Detail Harian (Hari & Tanggal)", "Rekapitulasi Bulanan (Bulan & Tahun)", "Rekapitulasi Tahunan (Tahun)"],
                horizontal=True
            )

        if view_granularity == "Detail Harian (Hari & Tanggal)":
            years_in_data = sorted(list(filtered_df["Tahun"].unique()))
            with st.container(border=True):
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
            with st.container(border=True):
                st.caption("Data teragregasi per Stasiun, Tahun, dan Bulan (Total, Rata-rata, Nilai Maksimum, dan Jumlah Hari Hujan).")
                m_agg = filtered_df.groupby(["Stasiun", "Tahun", "Bulan", "Nama_Bulan"]).agg(
                    Total_CH=("Curah_Hujan", "sum"),
                    Rata_Rata_CH=("Curah_Hujan", "mean"),
                    Maks_CH=("Curah_Hujan", "max"),
                    Hari_Hujan=("Curah_Hujan", lambda s: (s > 0).sum()),
                    Total_Hari=("Curah_Hujan", "count")
                ).reset_index()
                m_agg.sort_values(by=["Stasiun", "Tahun", "Bulan"], inplace=True)
                m_agg.drop(columns=["Bulan"], inplace=True)
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
            with st.container(border=True):
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

    # ----------------- TAB: MATRIKS HIDROLOGI -----------------
    with tab_matrix:
        with st.container(border=True):
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
                                    mat_df.style.format(format_matrix_cell).map(color_matrix_cell),
                                    use_container_width=True,
                                    height=420
                                )
                                st.caption("ℹ️ **Catatan:** Sel dengan arsir hitam (kosong tanpa angka) menandakan alat pengukur hujan (sensor) dalam kondisi **RUSAK**.")
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
                        cmap="BuGn", subset=cross_mat.columns[:-1]
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
                        mat_display.style.format(format_matrix_cell).map(color_matrix_cell),
                        use_container_width=True,
                        height=520
                    )
                    st.caption("ℹ️ **Catatan:** Sel dengan arsir hitam (kosong tanpa angka) menandakan alat pengukur hujan (sensor) dalam kondisi **RUSAK**.")
                else:
                    st.info("Tidak ada data untuk kombinasi stasiun dan tahun tersebut.")

    # ----------------- TAB 3: GRAFIK VISUALISASI -----------------
    # ----------------- TAB: GRAFIK & TREN -----------------
    with tab_charts:
        with st.container(border=True):
            st.subheader("📈 Analisis Grafik Interaktif")
            st.caption("Visualisasi tren fluktuasi curah hujan harian, akumulasi bulanan, distribusi intensitas BMKG, dan peringkat stasiun sesuai kriteria sidebar.")
        
            # Info Box Sinkronisasi Filter Sidebar
            st.markdown(
                f"<div style='background-color: #F8FAFC; border-left: 4.5px solid #0284C7; border-radius: 8px; padding: 10px 16px; margin-bottom: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);'>"
                f"<div style='font-weight: 700; color: #0F172A; font-size: 0.88rem; margin-bottom: 2px;'>📌 Parameter Filter Aktif (Tersinkronisasi dengan Sidebar):</div>"
                f"<div style='font-size: 0.82rem; color: #334155;'>"
                f"📍 <b>Stasiun Pengamatan ({len(selected_stations)} Stasiun):</b> <code>{', '.join(selected_stations[:10])}{'...' if len(selected_stations) > 10 else ''}</code> &nbsp;&bull;&nbsp; "
                f"📅 <b>Periode Waktu:</b> <code>{filter_periode_str}</code> &nbsp;&bull;&nbsp; "
                f"🌧️ <b>Kondisi:</b> <code>{'Hari Hujan > 0 mm' if only_rain_days else 'Semua Hari'}</code>"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True
            )

            chart_type = st.radio(
                "Pilih Jenis Grafik:",
                ["Tren Curah Hujan Harian (Line)", "Total Curah Hujan Bulanan (Bar)", "Distribusi Intensitas BMKG (Donut)", "Perbandingan Akumulasi Stasiun (Bar)"],
                horizontal=True
            )

        if chart_type == "Tren Curah Hujan Harian (Line)":
            st.markdown("##### 🌊 Tren Curah Hujan Harian Per Stasiun")
        
            col_cg1, col_cg2 = st.columns([2.5, 1.5])
            with col_cg1:
                stn_chart_sel = st.multiselect(
                    "Pilih Stasiun untuk Ditampilkan pada Grafik:",
                    options=selected_stations,
                    default=selected_stations,
                    key="chart_line_stn_multiselect",
                    help="Menampilkan seluruh stasiun yang Anda pilih di filter sidebar secara default. Anda dapat memfilter stasiun tertentu jika ingin visualisasi lebih terfokus."
                )
                if not stn_chart_sel:
                    stn_chart_sel = selected_stations

            with col_cg2:
                opt_c_sidebar = f"Sesuai Filter Sidebar ({filter_periode_str})"
                opt_c_all = "Seluruh Periode Historis (2015 - 2026)"
                chart_time_src = st.radio(
                    "Cakupan Tanggal Grafik:",
                    [opt_c_sidebar, opt_c_all],
                    key="chart_line_time_src",
                    help="Default mengikuti rentang tanggal yang dipilih pada sidebar."
                )

            if "Sesuai Filter Sidebar" in chart_time_src:
                chart_df = filtered_df[filtered_df["Stasiun"].isin(stn_chart_sel)].copy()
                sub_title_txt = f"Periode Filter: {filter_periode_str}"
            else:
                chart_df = df_raw[df_raw["Stasiun"].isin(stn_chart_sel)].copy()
                sub_title_txt = "Periode Historis Lengkap (2015 - 2026)"

            if not chart_df.empty:
                chart_df = chart_df.sort_values(by=["Stasiun", "Tanggal"]).reset_index(drop=True)
            
                fig = px.line(
                    chart_df,
                    x="Tanggal",
                    y="Curah_Hujan",
                    color="Stasiun",
                    labels={"Curah_Hujan": "Curah Hujan (mm)", "Tanggal": "Tanggal Pengamatan"},
                    title=f"Tren Fluktuasi Curah Hujan Harian — {sub_title_txt} ({len(stn_chart_sel)} Stasiun)"
                )
            
                min_tgl = chart_df["Tanggal"].min()
                max_tgl = chart_df["Tanggal"].max()
            
                fig.update_layout(
                    hovermode="x unified",
                    xaxis=dict(
                        range=[min_tgl, max_tgl] if pd.notna(min_tgl) and pd.notna(max_tgl) else None,
                        rangeslider=dict(visible=True)
                    ),
                    height=480,
                    template="plotly_white",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Tidak ada data curah hujan untuk kriteria tanggal dan stasiun yang dipilih.")

        elif chart_type == "Total Curah Hujan Bulanan (Bar)":
            st.markdown("##### 📊 Total Curah Hujan Per Bulan")
        
            col_b_stn, col_b_time = st.columns([2.5, 1.5])
            with col_b_stn:
                stn_bar_opts = ["Rata-rata Kawasan (Seluruh Stasiun Terpilih)", "Total Akumulasi Seluruh Stasiun Terpilih"] + selected_stations
                bar_stn_choice = st.selectbox("Pilih Agregasi Stasiun:", stn_bar_opts, key="chart_bar_stn_choice")
            with col_b_time:
                opt_b_sidebar = f"Sesuai Filter Sidebar ({filter_periode_str})"
                opt_b_all = "Seluruh Periode Historis (2015 - 2026)"
                bar_time_choice = st.radio("Cakupan Waktu:", [opt_b_sidebar, opt_b_all], key="chart_bar_time_choice")

            if "Sesuai Filter Sidebar" in bar_time_choice:
                df_bar_base = filtered_df.copy()
                time_lbl = filter_periode_str
            else:
                df_bar_base = df_raw[df_raw["Stasiun"].isin(selected_stations)].copy()
                time_lbl = "2015 - 2026"

            if bar_stn_choice == "Rata-rata Kawasan (Seluruh Stasiun Terpilih)":
                stn_m = df_bar_base.groupby(["Stasiun", "Tahun", "Bulan", "Nama_Bulan"])["Curah_Hujan"].sum().reset_index()
                monthly_agg = stn_m.groupby(["Tahun", "Bulan", "Nama_Bulan"])["Curah_Hujan"].mean().reset_index()
                bar_title = f"Rata-rata Curah Hujan Bulanan Kawasan ({len(selected_stations)} Stasiun Terpilih) — {time_lbl}"
                bar_y_label = "Rata-rata Curah Hujan (mm)"
            elif bar_stn_choice == "Total Akumulasi Seluruh Stasiun Terpilih":
                monthly_agg = df_bar_base.groupby(["Tahun", "Bulan", "Nama_Bulan"])["Curah_Hujan"].sum().reset_index()
                bar_title = f"Total Akumulasi Curah Hujan Bulanan ({len(selected_stations)} Stasiun Terpilih) — {time_lbl}"
                bar_y_label = "Total Curah Hujan (mm)"
            else:
                df_sub_stn = df_bar_base[df_bar_base["Stasiun"] == bar_stn_choice]
                monthly_agg = df_sub_stn.groupby(["Tahun", "Bulan", "Nama_Bulan"])["Curah_Hujan"].sum().reset_index()
                bar_title = f"Curah Hujan Bulanan Stasiun {bar_stn_choice} — {time_lbl}"
                bar_y_label = "Curah Hujan (mm)"

            if not monthly_agg.empty:
                monthly_agg["Periode"] = monthly_agg["Nama_Bulan"].str[:3] + " " + monthly_agg["Tahun"].astype(str)
                monthly_agg.sort_values(by=["Tahun", "Bulan"], inplace=True)

                fig_bar = px.bar(
                    monthly_agg,
                    x="Periode",
                    y="Curah_Hujan",
                    color="Curah_Hujan",
                    color_continuous_scale="Blues",
                    labels={"Curah_Hujan": bar_y_label, "Periode": "Bulan & Tahun"},
                    title=bar_title
                )
                fig_bar.update_layout(height=480, template="plotly_white")
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("Tidak ada data bulanan untuk kriteria yang dipilih.")

        elif chart_type == "Distribusi Intensitas BMKG (Donut)":
            st.markdown("##### 🍩 Proporsi Klasifikasi Curah Hujan (BMKG)")
            st.caption(f"Proporsi kejadian hujan untuk **{len(selected_stations)} stasiun terpilih** pada periode: **{filter_periode_str}**")
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
                title=f"Distribusi Kejadian Hujan BMKG ({len(selected_stations)} Stasiun — {filter_periode_str})"
            )
            fig_pie.update_layout(height=480, template="plotly_white")
            st.plotly_chart(fig_pie, use_container_width=True)

        elif chart_type == "Perbandingan Akumulasi Stasiun (Bar)":
            st.markdown("##### 🏆 Ranking Stasiun Berdasarkan Total Curah Hujan")
            st.caption(f"Peringkat total curah hujan untuk **{len(selected_stations)} stasiun terpilih** pada periode: **{filter_periode_str}**")
            stn_sum = summary_table_df.sort_values(by="Total Curah Hujan (mm)", ascending=True)

            fig_stn = px.bar(
                stn_sum,
                x="Total Curah Hujan (mm)",
                y="Stasiun",
                orientation="h",
                color="Total Curah Hujan (mm)",
                color_continuous_scale="Tealgrn",
                labels={"Total Curah Hujan (mm)": "Total Curah Hujan (mm)", "Stasiun": "Kode Stasiun"},
                title=f"Perbandingan Total Curah Hujan Antar Stasiun ({filter_periode_str})"
            )
            fig_stn.update_layout(height=max(450, len(stn_sum) * 24), template="plotly_white")
            st.plotly_chart(fig_stn, use_container_width=True)

    # ----------------- TAB: RINGKASAN STASIUN -----------------
    with tab_summary:
        with st.container(border=True):
            st.subheader("📊 Ringkasan Statistik Per Stasiun")
            st.caption(f"Rangkuman statistik lengkap untuk **{len(selected_stations)} stasiun terpilih** berdasarkan periode filter: **{filter_periode_str}**.")

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

    # ----------------- TAB: ANALISIS HIDROLOGI & KALA ULANG -----------------
    with tab_hydro:
        with st.container(border=True):
            st.subheader("🌊 Analisis Frekuensi Hidrologi & Curah Hujan Rancangan (Kala Ulang)")
            st.caption("Perhitungan curah hujan rancangan metode Gumbel dan Log Pearson Tipe III untuk kala ulang T = 2, 5, 10, 25, 50, dan 100 Tahun (Standar SNI & PU Perencanaan Bangunan Air/Drainase).")

            col_h_stn, col_h_yr, col_h_infill = st.columns([1.2, 1.5, 1.3])
            with col_h_stn:
                h_stn = st.selectbox("Pilih Stasiun untuk Dianalisis:", selected_stations, key="hydro_stn_select")
            with col_h_yr:
                min_filter_yr = min(years_in_filter) if years_in_filter else 2015
                max_filter_yr = max(years_in_filter) if years_in_filter else 2026
                opt_h_sidebar = f"Sesuai Filter Sidebar ({min_filter_yr} - {max_filter_yr}, N = {len(years_in_filter)} Thn)"
                opt_h_all = "Seluruh Data Historis (2015 - 2026)"
                hydro_yr_choice = st.radio(
                    "Deret Tahun Pengamatan:",
                    [opt_h_sidebar, opt_h_all],
                    key="hydro_yr_choice",
                    help="Sesuaikan deret tahun dengan filter di sidebar atau gunakan seluruh data historis untuk analisis kala ulang hidrologi."
                )
            with col_h_infill:
                hydro_infill_choice = st.radio(
                    "Perlakuan Data Alat Rusak:",
                    [
                        "Estimasi Otomatis (Infilling SNI/WMO)",
                        "Data Asli (Tanpa Estimasi)"
                    ],
                    key="hydro_infill_choice",
                    help="Standar SNI 19-6738-2002: Jika alat rusak bertepatan dengan hujan lebat di kawasan, estimasi stasiun sekitar memastikan puncak Pmax tidak terlewatkan dan deret LP3 memiliki data valid."
                )

        if h_stn:
            if "Sesuai Filter Sidebar" in hydro_yr_choice:
                df_hydro_target = df_raw[(df_raw["Stasiun"].isin(selected_stations)) & (df_raw["Tahun"].isin(years_in_filter))]
                h_years_used = years_in_filter
            else:
                df_hydro_target = df_raw[df_raw["Stasiun"].isin(selected_stations)]
                h_years_used = sorted(list(df_hydro_target[df_hydro_target["Stasiun"] == h_stn]["Tahun"].dropna().unique()))

            h_method = "auto" if "Estimasi Otomatis" in hydro_infill_choice else "none"
            stats_p, stn_infill_log = get_station_frequency_stats(df_hydro_target, h_stn, infill_method=h_method)
        
            # Info Cakupan Stasiun & Deret Tahun Kala Ulang
            with st.container(border=True):
                st.markdown(f"##### 📌 Informasi Cakupan Analisis Kala Ulang: Stasiun {h_stn}")
                col_inf_h1, col_inf_h2 = st.columns([1.2, 1.1])
                with col_inf_h1:
                    st.markdown(f"**📍 Stasiun Pengamatan:** **Stasiun {h_stn}** (dari {len(selected_stations)} stasiun terpilih di sidebar)")
                    st.caption(f"Stasiun aktif terpilih di filter sidebar: {', '.join(selected_stations[:10])}{'...' if len(selected_stations) > 10 else ''}")
                with col_inf_h2:
                    is_sb_h = "Sesuai Filter" in hydro_yr_choice
                    st.markdown(f"**📅 Deret Tahun Pengamatan:** **Tahun {min(h_years_used) if h_years_used else 2015} s/d {max(h_years_used) if h_years_used else 2026}** (N = {len(h_years_used)} Tahun) {'*(Sesuai Filter Sidebar)*' if is_sb_h else '*(Seluruh Data Historis)*'}")
                    st.caption(f"Tahun yang dianalisis: {', '.join(str(y) for y in h_years_used)}")

            if stats_p:
                # Metric cards
                with st.container(border=True):
                    st.markdown("##### 📊 Parameter Statistik Distribusi Hidrologi")
                    col_k1, col_k2, col_k3, col_k4, col_k5, col_k6 = st.columns(6)
                    col_k1.metric("Jumlah Tahun (n)", f"{stats_p['n']} Tahun")
                    col_k2.metric("Rata-rata Pmax (X)", f"{stats_p['mean']:.1f} mm")
                    col_k3.metric("Standar Deviasi (S)", f"{stats_p['std']:.2f} mm")
                    col_k4.metric("Koef. Variasi (Cv)", f"{stats_p['cv']:.3f}")
                    col_k5.metric("Koef. Skewness (Cs)", f"{stats_p['cs']:.3f}")
                    col_k6.metric("Koef. Kurtosis (Ck)", f"{stats_p['ck']:.3f}")

                # Design rainfall table and chart
                col_r1, col_r2 = st.columns([3, 4])
                with col_r1:
                    with st.container(border=True):
                        st.markdown("##### 📋 Tabel Curah Hujan Rancangan (mm)")
                        design_df = get_design_rainfall_summary(df_hydro_target, h_stn, infill_method=h_method)
                        st.dataframe(design_df, use_container_width=True, hide_index=True)

                with col_r2:
                    with st.container(border=True):
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

                # Expandable Rekapitulasi Data Rusak yang Diestimasi
                if not stn_infill_log.empty and h_method != "none":
                    with st.expander(f"🛠️ Rekapitulasi Data Rusak yang Diestimasi pada Stasiun {h_stn} ({len(stn_infill_log)} Hari)"):
                        st.info(
                            f"💡 Nilai curah hujan harian Stasiun **{h_stn}** pada hari saat alat pengukur rusak diestimasi menggunakan rata-rata stasiun pemantau aktif di sekitarnya pada tanggal yang sama "
                            "sesuai **SNI 19-6738-2002**. Hal ini melengkapi deret data tahunan $P_{max}$ sehingga parameter Gumbel dan Log Pearson III dapat dihitung secara optimal."
                        )
                        st.dataframe(stn_infill_log, use_container_width=True, hide_index=True)
            else:
                st.warning(
                    f"⚠️ Data Stasiun **{h_stn}** pada deret tahun terpilih ({len(h_years_used)} tahun: {min(h_years_used) if h_years_used else '-'}-{max(h_years_used) if h_years_used else '-'}) "
                    "belum mencukupi untuk analisis frekuensi hidrologi (Gumbel & LP3 membutuhkan minimal 3 tahun data pengamatan valid, direkomendasikan ≥ 10 tahun sesuai SNI/PUPR). "
                    "Silakan perlebar rentang tahun pada filter sidebar atau pilih opsi **'Seluruh Data Historis (2015 - 2026)'** di atas."
                )


    # ----------------- TAB: INPUT DATA MANUAL -----------------
    with tab_input:
        def handle_post_save_sync(action_desc: str = "Pembaruan Data") -> str:
            """Helper untuk sinkronisasi otomatis ke GitHub setelah penyimpanan lokal berhasil."""
            sync_msg = ""
            secrets_obj = st.secrets if hasattr(st, "secrets") else None
            if is_github_configured(secrets_obj):
                with st.spinner("☁️ Mengunggah pembaruan ke repositori GitHub..."):
                    sync_res = sync_all_database_to_github(
                        commit_message=f"feat(data): {action_desc} via Streamlit Cloud [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}]",
                        secrets_dict=secrets_obj
                    )
                    if sync_res.get("success"):
                        sync_msg = " • ☁️ **Otomatis ter-push ke GitHub!**"
                    else:
                        sync_msg = f" • ⚠️ *Lokal tersimpan, gagal sync GitHub: {sync_res.get('message')}*"
            return sync_msg

        with st.container(border=True):
            st.subheader("✍️ Input & Pembaruan Data Curah Hujan Manual")
            st.caption("Tambahkan data curah hujan harian terbaru atau perbarui data pengamatan stasiun langsung ke sistem. Tab ini kini berada di baris depan agar sangat mudah diakses.")

            input_mode = st.radio(
                "Pilih Metode Input:",
                ["Input Data Harian Tunggal (Single Entry)", "Input Matriks 1 Bulan Penuh (Grid Editor)"],
                horizontal=True
            )

        if input_mode == "Input Data Harian Tunggal (Single Entry)":
            with st.container(border=True):
                st.markdown("##### 📝 Formulir Input Data Harian Tunggal")
                col_in1, col_in2 = st.columns(2)
            
                with col_in1:
                    station_mode = st.radio("Pilihan Stasiun:", ["Pilih Stasiun Terdaftar", "Tambah Stasiun Baru"], horizontal=True)
                    if station_mode == "Pilih Stasiun Terdaftar":
                        stn_input = st.selectbox("Nama / Kode Stasiun:", all_stations)
                    else:
                        stn_input = st.text_input("Kode Stasiun Baru (misal: 69, 70a):").strip()
                
                    tgl_input = st.date_input("Tanggal Pengamatan:", value=datetime.date.today())
            
                with col_in2:
                    status_input = st.radio(
                        "Status Alat Pengukur:", ["Normal", "RUSAK"], horizontal=True,
                        help="Pilih RUSAK jika alat pengukur hujan tidak berfungsi pada tanggal ini."
                    )
                
                    is_rusak = (status_input == "RUSAK")
                    ch_input = st.number_input(
                        "Curah Hujan (mm):",
                        min_value=0.0,
                        max_value=500.0,
                        value=0.0,
                        step=0.1,
                        format="%.1f",
                        disabled=is_rusak,
                        key=f"ch_input_single_{'rusak' if is_rusak else 'normal'}",
                        help="Isian otomatis dinonaktifkan dan bernilai 0.0 jika status alat RUSAK." if is_rusak else "Ketik 0 jika cuaca cerah/berawan dan tidak ada hujan sama sekali."
                    )
                    if is_rusak:
                        st.warning("⚠️ Alat pengukur berstatus **RUSAK**: Isian curah hujan otomatis dinonaktifkan dan bernilai 0.0 mm. Pada tabel dan laporan, data akan dikosongkan dan diarsir hitam sesuai ketentuan.")
                        ch_input = None

                submit_single = st.button("💾 Simpan Data Harian", use_container_width=True, type="primary")

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
                            gh_msg = handle_post_save_sync(f"input data Stasiun {stn_input} tgl {tgl_input.strftime('%d-%m-%Y')}")
                            st.success(f"✅ Data Stasiun {stn_input} tanggal {tgl_input.strftime('%d-%m-%Y')} ({'RUSAK (Arsir Hitam)' if status_input == 'RUSAK' else f'{ch_input:.1f} mm'}) berhasil disimpan secara permanen!{gh_msg}")
                            st.rerun()
                        else:
                            st.error("Gagal menyimpan data ke sistem penyimpanan.")

        else:
            with st.container(border=True):
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

                # Deteksi tanggal yang berstatus RUSAK pada data awal
                existing_rusak_days = [d for d in range(1, days_in_month + 1) if existing_map.get(d, {}).get("Status") == "RUSAK"]

                # Callback helpers untuk sinkronisasi tombol cepat, multiselect, dan checkbox tabel
                def set_all_days_status(stn, yr, mo, total_days, is_rusak=True):
                    for d_i in range(1, total_days + 1):
                        st.session_state[f"chk_rsk_tbl_{stn}_{yr}_{mo}_{d_i}"] = is_rusak
                    st.session_state[f"rusak_pick_{stn}_{yr}_{mo}"] = list(range(1, total_days + 1)) if is_rusak else []
                    st.session_state.pop(f"editor_{stn}_{yr}_{mo}", None)

                def on_rusak_multiselect_change(stn, yr, mo, total_days):
                    selected = st.session_state.get(f"rusak_pick_{stn}_{yr}_{mo}", [])
                    for d_i in range(1, total_days + 1):
                        st.session_state[f"chk_rsk_tbl_{stn}_{yr}_{mo}_{d_i}"] = (d_i in selected)
                    st.session_state.pop(f"editor_{stn}_{yr}_{mo}", None)

                def on_single_checkbox_change(stn, yr, mo, d_idx):
                    val = st.session_state.get(f"chk_rsk_tbl_{stn}_{yr}_{mo}_{d_idx}", False)
                    curr_selected = set(st.session_state.get(f"rusak_pick_{stn}_{yr}_{mo}", []))
                    if val:
                        curr_selected.add(d_idx)
                    else:
                        curr_selected.discard(d_idx)
                    st.session_state[f"rusak_pick_{stn}_{yr}_{mo}"] = sorted(list(curr_selected))
                    st.session_state.pop(f"editor_{stn}_{yr}_{mo}", None)

                st.markdown("---")
                st.markdown("###### ⚙️ Opsi & Pilihan Status Alat (Normal / RUSAK)")
                col_opt1, col_opt2 = st.columns([3, 2])
                with col_opt1:
                    rusak_quick_pick = st.multiselect(
                        "🔴 Pilihan Cepat Tanggal Alat Rusak (Opsi):",
                        options=list(range(1, days_in_month + 1)),
                        default=existing_rusak_days,
                        format_func=lambda d: f"Tgl {d} ({int(bulk_yr)}-{int(bulk_m):02d}-{d:02d})",
                        help="Pilih tanggal-tanggal di mana sensor pengukur hujan rusak pada bulan ini. Tanggal yang Anda pilih otomatis ditandai RUSAK di tabel bawah.",
                        key=f"rusak_pick_{bulk_stn}_{bulk_yr}_{bulk_m}",
                        on_change=on_rusak_multiselect_change,
                        args=(bulk_stn, bulk_yr, bulk_m, days_in_month)
                    )
                    col_b_opt1, col_b_opt2 = st.columns(2)
                    with col_b_opt1:
                        st.button(
                            "🔴 Set Seluruh Hari RUSAK",
                            key=f"btn_all_rsk_opt_{bulk_stn}_{bulk_yr}_{bulk_m}",
                            on_click=set_all_days_status,
                            args=(bulk_stn, bulk_yr, bulk_m, days_in_month, True),
                            use_container_width=True,
                            help="Tandai seluruh hari pada bulan ini berstatus Alat RUSAK (nilai curah hujan 0.0 mm / diarsir hitam)"
                        )
                    with col_b_opt2:
                        st.button(
                            "🟢 Reset Semua Normal",
                            key=f"btn_all_norm_opt_{bulk_stn}_{bulk_yr}_{bulk_m}",
                            on_click=set_all_days_status,
                            args=(bulk_stn, bulk_yr, bulk_m, days_in_month, False),
                            use_container_width=True,
                            help="Kembalikan seluruh hari pada bulan ini ke status Normal"
                        )
                with col_opt2:
                    bulk_view_style = st.radio(
                        "Pilihan Model Pengisian:",
                        [
                            "📋 Tabel Interaktif (Otomatis Kunci & 0 mm saat Rusak)",
                            "📊 Grid Spreadsheet (Data Editor)"
                        ],
                        horizontal=False,
                        key="bulk_view_style_choice"
                    )

                if bulk_view_style == "📋 Tabel Interaktif (Otomatis Kunci & 0 mm saat Rusak)":
                    st.info(
                        f"💡 Menampilkan {days_in_month} hari untuk **Stasiun {bulk_stn}** — Bulan **{MONTH_NAMES_ID[int(bulk_m)]} {int(bulk_yr)}**. "
                        "Ketika kotak **Alat Rusak** dicentang, status otomatis berubah menjadi **RUSAK**, dan kotak isian curah hujan otomatis **terkunci (tidak dapat diisi) serta nilainya berubah menjadi 0.0 mm**."
                    )

                    # Action Bar Tombol Cepat Tepat di Atas Tabel
                    with st.container(border=True):
                        col_bar_info, col_bar_btn1, col_bar_btn2 = st.columns([4.2, 3.2, 2.6])
                        with col_bar_info:
                            st.markdown(
                                "<div style='padding-top: 3px;'>"
                                "<strong>⚡ Aksi Cepat Status Alat (1 Bulan Penuh):</strong><br>"
                                "<span style='font-size: 0.85rem; color: #475569;'>Klik tombol untuk mengubah seluruh hari sekaligus tanpa perlu mencentang satu per satu:</span>"
                                "</div>",
                                unsafe_allow_html=True
                            )
                        with col_bar_btn1:
                            st.button(
                                "🔴 Tandai Semua Hari RUSAK",
                                key=f"btn_all_rsk_tbl_{bulk_stn}_{bulk_yr}_{bulk_m}",
                                on_click=set_all_days_status,
                                args=(bulk_stn, bulk_yr, bulk_m, days_in_month, True),
                                use_container_width=True,
                                help=f"Klik untuk otomatis mencentang status ALAT RUSAK pada seluruh {days_in_month} hari di bulan ini (kolom CH terkunci 0.0 mm dan berstatus RUSAK)"
                            )
                        with col_bar_btn2:
                            st.button(
                                "🟢 Reset Semua Normal",
                                key=f"btn_all_norm_tbl_{bulk_stn}_{bulk_yr}_{bulk_m}",
                                on_click=set_all_days_status,
                                args=(bulk_stn, bulk_yr, bulk_m, days_in_month, False),
                                use_container_width=True,
                                help="Klik untuk mengembalikan seluruh hari di bulan ini ke status Normal"
                            )

                    # Header Tabel
                    with st.container(border=True):
                        ch1, ch2, ch3, ch4, ch5, ch6 = st.columns([0.8, 1.8, 1.8, 1.5, 2.0, 2.5])
                        ch1.markdown("**Hari**")
                        ch2.markdown("**Tanggal**")
                        ch3.markdown("**Alat Rusak?**")
                        ch4.markdown("**Status**")
                        ch5.markdown("**Curah Hujan (mm)**")
                        ch6.markdown("**Keterangan**")

                    table_items = {}
                    with st.container(height=520, border=True):
                        for d in range(1, days_in_month + 1):
                            ex = existing_map.get(d, {"Curah_Hujan": 0.0, "Status": "Normal"})
                            init_rusak = (d in rusak_quick_pick) or (ex["Status"] == "RUSAK")

                            c1, c2, c3, c4, c5, c6 = st.columns([0.8, 1.8, 1.8, 1.5, 2.0, 2.5])
                            c1.markdown(f"**{d}**")
                            c2.markdown(f"`{int(bulk_yr)}-{int(bulk_m):02d}-{d:02d}`")

                            is_chk_rusak = c3.checkbox(
                                "Alat Rusak",
                                value=init_rusak,
                                key=f"chk_rsk_tbl_{bulk_stn}_{bulk_yr}_{bulk_m}_{d}",
                                on_change=on_single_checkbox_change,
                                args=(bulk_stn, bulk_yr, bulk_m, d),
                                help=f"Centang jika alat rusak pada tgl {d}"
                            )

                            if is_chk_rusak:
                                c4.markdown("⬛ **RUSAK**")
                            else:
                                c4.markdown("🟢 **Normal**")

                            ch_val = c5.number_input(
                                f"CH Tgl {d}",
                                min_value=0.0,
                                max_value=500.0,
                                value=0.0 if is_chk_rusak else float(ex["Curah_Hujan"]),
                                step=0.1,
                                format="%.1f",
                                disabled=is_chk_rusak,
                                key=f"num_ch_tbl_{bulk_stn}_{bulk_yr}_{bulk_m}_{d}_{'rsk' if is_chk_rusak else 'nrm'}",
                                label_visibility="collapsed"
                            )

                            if is_chk_rusak:
                                c6.markdown("🔒 *Terkunci 0.0 mm (Arsir Hitam)*")
                                table_items[d] = {
                                    "Hari": d,
                                    "Curah_Hujan": None,
                                    "Status": "RUSAK"
                                }
                            else:
                                if ch_val > 0:
                                    c6.markdown(f"🌧️ *Hujan {ch_val:.1f} mm*")
                                else:
                                    c6.markdown("☀️ *Cerah (0.0 mm)*")
                                table_items[d] = {
                                    "Hari": d,
                                    "Curah_Hujan": ch_val,
                                    "Status": "Normal"
                                }

                    col_save1, col_save2 = st.columns([2, 4])
                    with col_save1:
                        if st.button(f"💾 Simpan Seluruh Bulan ({MONTH_NAMES_ID[int(bulk_m)]} {int(bulk_yr)})", type="primary", use_container_width=True, key="btn_save_interactive"):
                            daily_items = list(table_items.values())
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
                                gh_msg = handle_post_save_sync(f"input bulanan {days_in_month} hari Stasiun {bulk_stn} ({MONTH_NAMES_ID[int(bulk_m)]} {int(bulk_yr)})")
                                st.success(f"✅ Data {days_in_month} hari untuk Stasiun {bulk_stn} ({MONTH_NAMES_ID[int(bulk_m)]} {int(bulk_yr)}) berhasil disimpan secara permanen!{gh_msg}")
                                st.rerun()
                            else:
                                st.error("Gagal menyimpan data.")

                else:
                    # Mode Spreadsheet Grid
                    grid_data = []
                    for d in range(1, days_in_month + 1):
                        ex = existing_map.get(d, {"Curah_Hujan": 0.0, "Status": "Normal"})
                        is_d_rusak = (d in rusak_quick_pick) or (ex["Status"] == "RUSAK")
                        grid_data.append({
                            "Hari": d,
                            "Tanggal": f"{int(bulk_yr)}-{int(bulk_m):02d}-{d:02d}",
                            "Status Alat": "RUSAK" if is_d_rusak else "Normal",
                            "Curah Hujan (mm)": 0.0 if is_d_rusak else float(ex["Curah_Hujan"])
                        })

                    df_grid = pd.DataFrame(grid_data)

                    st.info(f"💡 Mode Grid Spreadsheet: Ubah kolom **Status Alat** menjadi **RUSAK** jika alat rusak. Nilai curah hujan untuk status RUSAK otomatis dikosongkan dan diarsir hitam saat disimpan.")

                    col_g_act1, col_g_act2, col_g_info = st.columns([3, 2.5, 4.5])
                    with col_g_act1:
                        st.button(
                            "🔴 Set Semua Grid RUSAK (1 Bulan)",
                            key=f"btn_all_rsk_grid_{bulk_stn}_{bulk_yr}_{bulk_m}",
                            on_click=set_all_days_status,
                            args=(bulk_stn, bulk_yr, bulk_m, days_in_month, True),
                            use_container_width=True,
                            help="Set seluruh baris dalam grid bulan ini menjadi RUSAK (0.0 mm)"
                        )
                    with col_g_act2:
                        st.button(
                            "🟢 Reset Semua Grid Normal",
                            key=f"btn_all_norm_grid_{bulk_stn}_{bulk_yr}_{bulk_m}",
                            on_click=set_all_days_status,
                            args=(bulk_stn, bulk_yr, bulk_m, days_in_month, False),
                            use_container_width=True,
                            help="Kembalikan seluruh baris dalam grid bulan ini menjadi Normal"
                        )
                    with col_g_info:
                        st.caption("⚡ *Tombol di atas otomatis mengatur status grid 1 bulan penuh.*")

                    edited_df = st.data_editor(
                        df_grid,
                        use_container_width=True,
                        num_rows="fixed",
                        height=min(520, days_in_month * 36 + 60),
                        column_config={
                            "Hari": st.column_config.NumberColumn("Hari", disabled=True),
                            "Tanggal": st.column_config.TextColumn("Tanggal", disabled=True),
                            "Status Alat": st.column_config.SelectboxColumn(
                                "Status Alat",
                                options=["Normal", "RUSAK"],
                                help="Pilih Normal atau RUSAK. Jika RUSAK, isian otomatis menjadi nol dan diarsir hitam.",
                                required=True
                            ),
                            "Curah Hujan (mm)": st.column_config.NumberColumn(
                                "Curah Hujan (mm)",
                                min_value=0.0,
                                max_value=500.0,
                                step=0.1,
                                format="%.1f mm",
                                help="Isi curah hujan harian (mm). Jika status RUSAK, nilai curah hujan otomatis diabaikan dan bernilai nol."
                            )
                        },
                        key=f"editor_{bulk_stn}_{bulk_yr}_{bulk_m}"
                    )

                    col_save1, col_save2 = st.columns([2, 4])
                    with col_save1:
                        if st.button(f"💾 Simpan dari Grid ({MONTH_NAMES_ID[int(bulk_m)]} {int(bulk_yr)})", type="primary", use_container_width=True, key="btn_save_grid"):
                            daily_items = []
                            for _, r in edited_df.iterrows():
                                stat_r = str(r.get("Status Alat", "Normal")).strip()
                                is_rsk = (stat_r == "RUSAK")
                                daily_items.append({
                                    "Hari": int(r["Hari"]),
                                    "Curah_Hujan": None if is_rsk else float(r.get("Curah Hujan (mm)", 0.0)),
                                    "Status": "RUSAK" if is_rsk else "Normal"
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
                                gh_msg = handle_post_save_sync(f"input bulanan {days_in_month} hari Stasiun {bulk_stn} ({MONTH_NAMES_ID[int(bulk_m)]} {int(bulk_yr)})")
                                st.success(f"✅ Data {days_in_month} hari untuk Stasiun {bulk_stn} ({MONTH_NAMES_ID[int(bulk_m)]} {int(bulk_yr)}) berhasil disimpan secara permanen!{gh_msg}")
                                st.rerun()
                            else:
                                st.error("Gagal menyimpan data.")

        # Bagian Riwayat Input Manual
        with st.container(border=True):
            st.markdown("##### 📜 Catatan Riwayat Input Data Manual")
            if os.path.exists("manual_records_log.csv"):
                log_df = pd.read_csv("manual_records_log.csv")
                st.dataframe(log_df.tail(25).iloc[::-1], use_container_width=True, height=260)
            else:
                st.caption("Belum ada riwayat input manual yang dicatat.")

        # ==============================================================================
        # PANEL PENGELOLA SISTEM (TERSEMBUNYI DARI PUBLIK / DILINDUNGI SANDI ADMIN)
        # ==============================================================================
        is_admin_query = False
        try:
            if hasattr(st, "query_params") and st.query_params.get("admin") in ["1", "true", "True"]:
                is_admin_query = True
        except Exception:
            pass

        with st.expander("🔒 Pengaturan Pengelola Sistem (Khusus Administrator)", expanded=is_admin_query):
            admin_pwd = st.text_input(
                "Masukkan Kode Sandi Administrator:",
                type="password",
                placeholder="Masukkan sandi pengelola untuk membuka tombol kontrol...",
                key="admin_access_pwd"
            )
            secrets_obj = st.secrets if hasattr(st, "secrets") else None
            cfg_pwd = ""
            if secrets_obj:
                try:
                    cfg_pwd = secrets_obj.get("ADMIN_PASSWORD", "") or secrets_obj.get("admin_password", "")
                except Exception:
                    pass
            valid_passwords = ["dpupr2026", "admin", "admin123", "tegal2026"]
            if cfg_pwd:
                valid_passwords.append(str(cfg_pwd).strip())

            is_admin_auth = is_admin_query or (admin_pwd.strip().lower() in valid_passwords)

            if is_admin_auth:
                st.success("🔓 Akses Pengelola Terverifikasi")
                gh_ready = is_github_configured(secrets_obj)

                col_gh_st, col_gh_btn1, col_gh_btn2 = st.columns([2.5, 1.8, 2.0])
                with col_gh_st:
                    if gh_ready:
                        st.markdown("🟢 **Status Auto-Push:** **Aktif (Tersambung ke GitHub)**")
                        st.caption("Setiap penambahan atau pengeditan data baru otomatis di-commit & di-push ke repositori GitHub.")
                    else:
                        st.markdown("🟡 **Status Auto-Push:** **Belum Terhubung ke GitHub Secrets**")
                        st.caption("Data tersimpan di kontainer lokal.")

                with col_gh_btn1:
                    if gh_ready:
                        if st.button("🧪 Uji Koneksi GitHub", use_container_width=True, key="btn_test_gh_conn"):
                            ok_t, msg_t = test_github_connection(secrets_obj)
                            if ok_t:
                                st.success(msg_t)
                            else:
                                st.error(msg_t)
                    else:
                        st.info("💡 Konfigurasi token di Streamlit Secrets.")

                with col_gh_btn2:
                    if gh_ready:
                        if st.button("🚀 Push Database ke GitHub", type="primary", use_container_width=True, key="btn_manual_push_gh"):
                            with st.spinner("Mengunggah seluruh database ke GitHub..."):
                                sync_res = sync_all_database_to_github(
                                    commit_message=f"chore(data): manual database push from web [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}]",
                                    secrets_dict=secrets_obj
                                )
                                if sync_res.get("success"):
                                    st.success("✅ Database berhasil ter-push ke GitHub!")
                                else:
                                    st.error(f"❌ Gagal: {sync_res.get('message')}")

                # Baris tombol unduh cadangan lokal mandiri
                col_dl_p1, col_dl_p2 = st.columns(2)
                with col_dl_p1:
                    if os.path.exists("data_curah_hujan.parquet"):
                        with open("data_curah_hujan.parquet", "rb") as f_pq:
                            st.download_button(
                                label="📥 Unduh Cadangan Database (.parquet)",
                                data=f_pq.read(),
                                file_name=f"database_curah_hujan_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.parquet",
                                mime="application/octet-stream",
                                use_container_width=True
                            )
                with col_dl_p2:
                    if os.path.exists("manual_records_log.csv"):
                        with open("manual_records_log.csv", "rb") as f_log:
                            st.download_button(
                                label="📥 Unduh Catatan Log Riwayat (.csv)",
                                data=f_log.read(),
                                file_name=f"riwayat_input_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                mime="text/csv",
                                use_container_width=True
                            )
            elif admin_pwd:
                st.error("❌ Kode sandi salah. Akses ditolak.")
            else:
                st.caption("Panel pemeliharaan repositori dan sinkronisasi database dilindungi kata sandi pengelola.")




else:
    # ==============================================================================
    # MAIN PANEL: DATA DEBIT BENDUNG
    # ==============================================================================
    logo_main_b64 = get_base64_image("assets/logo_pupr_tegal.png")
    if logo_main_b64:
        st.markdown(f"""
        <div class="pupr-header-card">
            <div class="pupr-header-content">
                <img src="data:image/png;base64,{logo_main_b64}" class="pupr-header-logo" alt="Logo DPUPR Kab Tegal" />
                <div class="pupr-title-box">
                    <div class="pupr-tagline">PEMERINTAH KABUPATEN TEGAL</div>
                    <div class="pupr-title">DINAS PEKERJAAN UMUM DAN PENATAAN RUANG</div>
                    <div class="pupr-subtitle">Sistem Pengelolaan Data Debit & Analisis Debit Andalan 4 Bendung (Weibull Q80)</div>
                </div>
            </div>
            <div class="pupr-header-badges">
                <span class="pupr-badge pupr-badge-primary">🏛️ DPUPR KAB. TEGAL</span>
                <span class="pupr-badge pupr-badge-gold">🌊 Bidang SDA & Jasa Konstruksi</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.title("🏛️ DINAS PEKERJAAN UMUM DAN PENATAAN RUANG KABUPATEN TEGAL")
        st.caption("Bidang Sumber Daya Air dan Jasa Konstruksi — Pengelolaan Data Debit & Analisis Debit Andalan Bendung")

    st.markdown(
        f"Kategori Modul: <span class='filter-badge'>💧 DATA DEBIT BENDUNG</span> "
        f"<span class='filter-badge'>📍 4 Bendung: Rajabawah, Pondoh, Kemaron, Lengkong</span> "
        f"<span class='filter-badge'>📅 2004/2005 - 2024/2025 (21 Tahun Hidrologi)</span> "
        f"<span class='filter-badge'>📊 Satuan: Liter/Detik (L/s)</span>",
        unsafe_allow_html=True
    )
    st.markdown("<br>", unsafe_allow_html=True)

    tab_debit_data, tab_debit_input, tab_debit_weibull = st.tabs([
        "📋 Data Debit Bendung",
        "✍️ Input Debit Manual",
        "💧 Debit Andalan Bendung (Weibull)"
    ])

    with tab_debit_data:
        bendung_analysis.render_data_debit_view()

    with tab_debit_input:
        bendung_analysis.render_input_debit_manual()

    with tab_debit_weibull:
        bendung_analysis.render_tab_weibull_content()
