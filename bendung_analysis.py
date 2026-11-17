import os
import io
import datetime
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

BENDUNG_PARQUET = "data_debit_bendung.parquet"
BENDUNG_EXCEL = "data_debit_bendung.xlsx"

BENDUNG_INFO = {
    "RAJABAWAH": {
        "nama": "Bendung Rajabawah",
        "di": "D.I. Rajabawah",
        "kab": "Kabupaten Tegal"
    },
    "PONDOH": {
        "nama": "Bendung Pondoh",
        "di": "D.I. Pondoh",
        "kab": "Kabupaten Tegal"
    },
    "KEMARON": {
        "nama": "Bendung Kemaron",
        "di": "D.I. Gung, Kemaron",
        "kab": "Kabupaten Tegal"
    },
    "LENGKONG": {
        "nama": "Bendung Lengkong",
        "di": "D.I. Lengkong",
        "kab": "Kabupaten Tegal"
    }
}

MONTH_NAMES_ORDER = [
    "OKTOBER", "NOVEMBER", "DESEMBER", 
    "JANUARI", "FEBRUARI", "MARET", 
    "APRIL", "MEI", "JUNI", 
    "JULI", "AGUSTUS", "SEPTEMBER"
]

SEMI_MONTHLY_COLS = []
for m in MONTH_NAMES_ORDER:
    SEMI_MONTHLY_COLS.append(f"{m} I")
    SEMI_MONTHLY_COLS.append(f"{m} II")


def load_bendung_dataset() -> pd.DataFrame:
    """Memuat seluruh data historis debit bendung dari parquet atau excel."""
    if os.path.exists(BENDUNG_PARQUET):
        return pd.read_parquet(BENDUNG_PARQUET)
    elif os.path.exists(BENDUNG_EXCEL):
        df = pd.read_excel(BENDUNG_EXCEL)
        df.to_parquet(BENDUNG_PARQUET, index=False)
        return df
    return pd.DataFrame()


def get_bendungs_list() -> List[str]:
    """Mendapatkan daftar nama bendung yang tersedia."""
    df = load_bendung_dataset()
    if df.empty:
        return list(BENDUNG_INFO.keys())
    return sorted(list(df["Bendung"].unique()))


def calculate_weibull_ranking(series: pd.Series, years: pd.Series = None) -> pd.DataFrame:
    """
    Menghitung tabel peringkat Weibull untuk satu deret data debit historis.
    Rumus: P = [m / (N + 1)] * 100%
    Data diurutkan dari nilai terbesar ke terkecil (descending).
    """
    if series.empty:
        return pd.DataFrame()

    if years is not None:
        work_df = pd.DataFrame({"Tahun": years, "Debit": series}).dropna(subset=["Debit"])
    else:
        work_df = pd.DataFrame({"Tahun": series.index, "Debit": series}).dropna(subset=["Debit"])

    if work_df.empty:
        return pd.DataFrame()

    work_df = work_df.sort_values(by="Debit", ascending=False).reset_index(drop=True)
    n = len(work_df)

    work_df["Peringkat (m)"] = range(1, n + 1)
    work_df["P (%)"] = [round((m / (n + 1)) * 100.0, 2) for m in range(1, n + 1)]
    work_df["Debit (L/s)"] = work_df["Debit"].round(2)

    return work_df[["Peringkat (m)", "Tahun", "Debit (L/s)", "P (%)"]]


def interpolate_weibull_quantile(rank_df: pd.DataFrame, target_p: float = 80.0) -> float:
    """
    Melakukan interpolasi linier untuk mencari debit pada probabilitas target P (%)
    m_target = (target_p / 100.0) * (N + 1)
    """
    if rank_df.empty:
        return 0.0

    n = len(rank_df)
    m_target = (float(target_p) / 100.0) * (n + 1)

    if m_target <= 1:
        return float(rank_df.iloc[0]["Debit (L/s)"])
    if m_target >= n:
        return float(rank_df.iloc[-1]["Debit (L/s)"])

    m1 = int(np.floor(m_target))
    m2 = m1 + 1

    row1 = rank_df[rank_df["Peringkat (m)"] == m1]
    row2 = rank_df[rank_df["Peringkat (m)"] == m2]
    if row1.empty or row2.empty:
        return 0.0

    val1 = float(row1.iloc[0]["Debit (L/s)"])
    val2 = float(row2.iloc[0]["Debit (L/s)"])

    fraction = m_target - m1
    interpolated = val1 + fraction * (val2 - val1)
    return max(0.0, round(interpolated, 2))


def analyze_bendung_debit(
    df_bendung: pd.DataFrame,
    bendung_name: str,
    target_p: float = 80.0,
    selected_years: List[str] = None
) -> Dict[str, Any]:
    """
    Menganalisis debit andalan bendung menggunakan rumus Weibull P = [m / (N+1)] * 100%.
    Menghasilkan:
    1. Tabel Rekapitulasi 1/2 Bulanan (24 periode)
    2. Tabel Rekapitulasi Bulanan (12 bulan)
    3. Rincian Peringkat Weibull (24 periode + 12 bulan)
    4. Indikator Kunci (KPI: Rata-rata Q80 tahunan, musim basah/kering, min, max)
    5. Matriks Historis Bersih
    """
    sub_df = df_bendung[df_bendung["Bendung"] == bendung_name].copy()
    if sub_df.empty:
        return {}

    if selected_years:
        sub_df = sub_df[sub_df["Tahun_Hidrologi"].isin(selected_years)]

    di_name = sub_df["Daerah_Irigasi"].iloc[0] if "Daerah_Irigasi" in sub_df.columns else bendung_name

    # ==================== 1. ANALISIS 1/2 BULANAN (24 PERIODE) ====================
    semi_monthly_results = []
    rankings_semi = {}

    for idx, col in enumerate(SEMI_MONTHLY_COLS):
        parts = col.split(" ")
        m_name = parts[0]
        period_rom = parts[1]

        series_col = sub_df[col].dropna()
        years_col = sub_df.loc[series_col.index, "Tahun_Hidrologi"]

        rank_df = calculate_weibull_ranking(series_col, years_col)
        rankings_semi[col] = rank_df

        q_target = interpolate_weibull_quantile(rank_df, target_p)

        # Nilai pembanding lainnya (Q50, Q90)
        q50 = interpolate_weibull_quantile(rank_df, 50.0)
        q90 = interpolate_weibull_quantile(rank_df, 90.0)

        n_obs = len(series_col)
        mean_val = round(float(series_col.mean()), 2) if n_obs > 0 else 0.0
        min_val = round(float(series_col.min()), 2) if n_obs > 0 else 0.0
        max_val = round(float(series_col.max()), 2) if n_obs > 0 else 0.0

        semi_monthly_results.append({
            "No": idx + 1,
            "Periode": col,
            "Bulan": m_name,
            "Setengah_Bulan": period_rom,
            "N_Tahun": n_obs,
            f"Q{int(target_p)} Andalan (L/s)": q_target,
            "Q50 Normal (L/s)": q50,
            "Q90 Kering (L/s)": q90,
            "Rata-rata Historis (L/s)": mean_val,
            "Min (L/s)": min_val,
            "Max (L/s)": max_val
        })

    semi_df = pd.DataFrame(semi_monthly_results)

    # ==================== 2. ANALISIS REKAP BULANAN (12 BULAN) ====================
    monthly_results = []
    rankings_monthly = {}

    for m_idx, m_name in enumerate(MONTH_NAMES_ORDER):
        c1 = f"{m_name} I"
        c2 = f"{m_name} II"

        # Hitung debit rata-rata bulanan historis per tahun baris
        m_series = sub_df[[c1, c2]].mean(axis=1).dropna()
        m_years = sub_df.loc[m_series.index, "Tahun_Hidrologi"]

        rank_m_df = calculate_weibull_ranking(m_series, m_years)
        rankings_monthly[m_name] = rank_m_df

        q_target_m = interpolate_weibull_quantile(rank_m_df, target_p)

        # Ambil Q80 periode I dan II dari semi_df
        q_target_p1 = semi_df.loc[semi_df["Periode"] == c1, f"Q{int(target_p)} Andalan (L/s)"].values[0]
        q_target_p2 = semi_df.loc[semi_df["Periode"] == c2, f"Q{int(target_p)} Andalan (L/s)"].values[0]
        avg_q_target_periods = round((q_target_p1 + q_target_p2) / 2.0, 2)

        mean_m = round(float(m_series.mean()), 2) if len(m_series) > 0 else 0.0
        min_m = round(float(m_series.min()), 2) if len(m_series) > 0 else 0.0
        max_m = round(float(m_series.max()), 2) if len(m_series) > 0 else 0.0

        monthly_results.append({
            "No": m_idx + 1,
            "Bulan": m_name,
            f"Q{int(target_p)} Periode I (L/s)": q_target_p1,
            f"Q{int(target_p)} Periode II (L/s)": q_target_p2,
            f"Rata-rata Q{int(target_p)} 1/2 Bulanan (L/s)": avg_q_target_periods,
            f"Q{int(target_p)} Debit Bulanan (L/s)": q_target_m,
            "Rata-rata Historis (L/s)": mean_m,
            "Min (L/s)": min_m,
            "Max (L/s)": max_m
        })

    monthly_df = pd.DataFrame(monthly_results)

    # ==================== 3. INDIKATOR UTAMA (KPI) ====================
    q_target_col = f"Q{int(target_p)} Andalan (L/s)"
    avg_annual_q = round(semi_df[q_target_col].mean(), 2)

    wet_season_q = round(semi_df.iloc[:12][q_target_col].mean(), 2)
    dry_season_q = round(semi_df.iloc[12:][q_target_col].mean(), 2)

    min_period = semi_df.loc[semi_df[q_target_col].idxmin()]
    max_period = semi_df.loc[semi_df[q_target_col].idxmax()]

    kpi = {
        "bendung": bendung_name,
        "di": di_name,
        "target_p": target_p,
        "avg_annual_q": avg_annual_q,
        "wet_season_q": wet_season_q,
        "dry_season_q": dry_season_q,
        "min_q": float(min_period[q_target_col]),
        "min_period": str(min_period["Periode"]),
        "max_q": float(max_period[q_target_col]),
        "max_period": str(max_period["Periode"]),
        "total_years": len(sub_df)
    }

    return {
        "bendung": bendung_name,
        "daerah_irigasi": di_name,
        "target_p": target_p,
        "kpi": kpi,
        "semi_monthly_df": semi_df,
        "monthly_df": monthly_df,
        "rankings_semi": rankings_semi,
        "rankings_monthly": rankings_monthly,
        "matrix_df": sub_df[["Tahun_Hidrologi"] + SEMI_MONTHLY_COLS]
    }


def compare_all_bendungs(target_p: float = 80.0, df_all: pd.DataFrame = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Menghasilkan tabel perbandingan 1/2 bulanan dan bulanan untuk ke-4 bendung secara berdampingan.
    """
    if df_all is None:
        df_all = load_bendung_dataset()

    bendungs = get_bendungs_list()
    if not bendungs:
        return pd.DataFrame(), pd.DataFrame()

    semi_comp = pd.DataFrame({"Periode": SEMI_MONTHLY_COLS})
    monthly_comp = pd.DataFrame({"Bulan": MONTH_NAMES_ORDER})

    for b in bendungs:
        res = analyze_bendung_debit(df_all, b, target_p)
        if not res:
            continue
        semi_df = res["semi_monthly_df"]
        monthly_df = res["monthly_df"]

        semi_comp[f"{b} (L/s)"] = semi_df[f"Q{int(target_p)} Andalan (L/s)"].values
        monthly_comp[f"{b} (L/s)"] = monthly_df[f"Q{int(target_p)} Debit Bulanan (L/s)"].values

    return semi_comp, monthly_comp


def export_bendung_debit_to_excel(
    bendung_name: str,
    analysis_res: Dict[str, Any],
    all_bendungs_res: Tuple[pd.DataFrame, pd.DataFrame] = None
) -> io.BytesIO:
    """
    Mengekspor laporan lengkap analisis debit andalan Weibull bendung ke format Excel (.xlsx)
    dengan format profesional DPUPR Kab. Tegal.
    """
    output = io.BytesIO()
    wb = openpyxl.Workbook()

    font_title = Font(name="Calibri", size=14, bold=True, color="1E3A8A")
    font_subtitle = Font(name="Calibri", size=10, italic=True, color="475569")
    font_section = Font(name="Calibri", size=11, bold=True, color="0F766E")
    font_header = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    font_bold = Font(name="Calibri", size=10, bold=True, color="1E293B")
    font_regular = Font(name="Calibri", size=10, color="1E293B")

    fill_header_navy = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    fill_header_teal = PatternFill(start_color="0F766E", end_color="0F766E", fill_type="solid")
    fill_zebra = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    fill_highlight = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
    fill_kpi = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")

    thin_side = Side(border_style="thin", color="CBD5E1")
    thin_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
    double_bottom = Border(bottom=Side(border_style="double", color="1E3A8A"), left=thin_side, right=thin_side, top=thin_side)

    kpi = analysis_res.get("kpi", {})
    target_p = int(analysis_res.get("target_p", 80))
    semi_df = analysis_res.get("semi_monthly_df", pd.DataFrame())
    monthly_df = analysis_res.get("monthly_df", pd.DataFrame())
    matrix_df = analysis_res.get("matrix_df", pd.DataFrame())
    rankings_semi = analysis_res.get("rankings_semi", {})

    # ==================== SHEET 1: REKAP DEBIT ANDALAN (1/2 BULANAN & BULANAN) ====================
    ws1 = wb.active
    ws1.title = "Rekap Debit Andalan"
    ws1.views.sheetView[0].showGridLines = True

    # Header Dokumen
    ws1.merge_cells("A1:G1")
    ws1["A1"] = "PEMERINTAH KABUPATEN TEGAL - DINAS PEKERJAAN UMUM DAN PENATAAN RUANG"
    ws1["A1"].font = font_subtitle
    ws1["A1"].alignment = align_left

    ws1.merge_cells("A2:G2")
    ws1["A2"] = f"LAPORAN PERHITUNGAN DEBIT ANDALAN WEIBULL (Q{target_p}) - {kpi.get('bendung', bendung_name)}"
    ws1["A2"].font = font_title
    ws1["A2"].alignment = align_left

    ws1.merge_cells("A3:G3")
    ws1["A3"] = f"Daerah Irigasi: {kpi.get('di', '-')} | Satuan: Liter/detik (L/s) | Tanggal Cetak: {datetime.datetime.now().strftime('%d-%m-%Y %H:%M')}"
    ws1["A3"].font = font_subtitle
    ws1["A3"].alignment = align_left

    # KPI Summary Box
    ws1.cell(row=5, column=1, value="RINGKASAN INDIKATOR KEANDALAN DEBIT (KPI)").font = font_section
    kpis = [
        ("Rata-rata Q80 Tahunan", f"{kpi.get('avg_annual_q', 0.0)} L/s"),
        ("Musim Hujan (Rendeng: Okt-Mar)", f"{kpi.get('wet_season_q', 0.0)} L/s"),
        ("Musim Kemarau (Gadu: Apr-Sep)", f"{kpi.get('dry_season_q', 0.0)} L/s"),
        ("Debit Terendah Q80", f"{kpi.get('min_q', 0.0)} L/s ({kpi.get('min_period', '-')})"),
        ("Debit Tertinggi Q80", f"{kpi.get('max_q', 0.0)} L/s ({kpi.get('max_period', '-')})")
    ]
    for k_idx, (k_lbl, k_val) in enumerate(kpis):
        r_box = 6 + k_idx
        ws1.cell(row=r_box, column=1, value=k_lbl).font = font_bold
        ws1.cell(row=r_box, column=1).fill = fill_kpi
        ws1.cell(row=r_box, column=1).border = thin_border
        ws1.cell(row=r_box, column=2, value=k_val).font = font_bold
        ws1.cell(row=r_box, column=2).fill = fill_highlight
        ws1.cell(row=r_box, column=2).alignment = align_right
        ws1.cell(row=r_box, column=2).border = thin_border

    # TABEL 1: 1/2 BULANAN
    r_semi_start = 12
    ws1.cell(row=r_semi_start, column=1, value="1. REKAPITULASI DEBIT ANDALAN 1/2 BULANAN (LITER/DETIK)").font = font_section
    
    headers_semi = ["No", "Periode", f"Q{target_p} Andalan (L/s)", "Q50 Normal (L/s)", "Q90 Kering (L/s)", "Rata-rata Historis (L/s)", "Min (L/s)", "Max (L/s)", "N Tahun"]
    for c_idx, h_text in enumerate(headers_semi):
        c_cell = ws1.cell(row=r_semi_start + 1, column=c_idx + 1, value=h_text)
        c_cell.font = font_header
        c_cell.fill = fill_header_navy
        c_cell.alignment = align_center
        c_cell.border = thin_border

    curr_r = r_semi_start + 2
    for _, row in semi_df.iterrows():
        ws1.cell(row=curr_r, column=1, value=int(row["No"])).alignment = align_center
        ws1.cell(row=curr_r, column=2, value=str(row["Periode"])).alignment = align_left
        ws1.cell(row=curr_r, column=3, value=float(row[f"Q{target_p} Andalan (L/s)"])).alignment = align_right
        ws1.cell(row=curr_r, column=4, value=float(row["Q50 Normal (L/s)"])).alignment = align_right
        ws1.cell(row=curr_r, column=5, value=float(row["Q90 Kering (L/s)"])).alignment = align_right
        ws1.cell(row=curr_r, column=6, value=float(row["Rata-rata Historis (L/s)"])).alignment = align_right
        ws1.cell(row=curr_r, column=7, value=float(row["Min (L/s)"])).alignment = align_right
        ws1.cell(row=curr_r, column=8, value=float(row["Max (L/s)"])).alignment = align_right
        ws1.cell(row=curr_r, column=9, value=int(row["N_Tahun"])).alignment = align_center

        for col_i in range(1, 10):
            cell = ws1.cell(row=curr_r, column=col_i)
            cell.font = font_regular
            cell.border = thin_border
            if curr_r % 2 == 1:
                cell.fill = fill_zebra
            if col_i == 3:
                cell.font = font_bold
                cell.fill = fill_highlight
        curr_r += 1

    # TABEL 2: REKAP BULANAN
    r_month_start = curr_r + 2
    ws1.cell(row=r_month_start, column=1, value="2. REKAPITULASI DEBIT ANDALAN BULANAN (LITER/DETIK)").font = font_section
    
    headers_month = ["No", "Bulan", f"Q{target_p} Periode I (L/s)", f"Q{target_p} Periode II (L/s)", f"Rata-rata Q{target_p} 1/2 Bln (L/s)", f"Q{target_p} Bulanan (L/s)", "Rata-rata Historis (L/s)", "Min (L/s)", "Max (L/s)"]
    for c_idx, h_text in enumerate(headers_month):
        c_cell = ws1.cell(row=r_month_start + 1, column=c_idx + 1, value=h_text)
        c_cell.font = font_header
        c_cell.fill = fill_header_teal
        c_cell.alignment = align_center
        c_cell.border = thin_border

    curr_r = r_month_start + 2
    for _, row in monthly_df.iterrows():
        ws1.cell(row=curr_r, column=1, value=int(row["No"])).alignment = align_center
        ws1.cell(row=curr_r, column=2, value=str(row["Bulan"])).alignment = align_left
        ws1.cell(row=curr_r, column=3, value=float(row[f"Q{target_p} Periode I (L/s)"])).alignment = align_right
        ws1.cell(row=curr_r, column=4, value=float(row[f"Q{target_p} Periode II (L/s)"])).alignment = align_right
        ws1.cell(row=curr_r, column=5, value=float(row[f"Rata-rata Q{target_p} 1/2 Bulanan (L/s)"])).alignment = align_right
        ws1.cell(row=curr_r, column=6, value=float(row[f"Q{target_p} Debit Bulanan (L/s)"])).alignment = align_right
        ws1.cell(row=curr_r, column=7, value=float(row["Rata-rata Historis (L/s)"])).alignment = align_right
        ws1.cell(row=curr_r, column=8, value=float(row["Min (L/s)"])).alignment = align_right
        ws1.cell(row=curr_r, column=9, value=float(row["Max (L/s)"])).alignment = align_right

        for col_i in range(1, 10):
            cell = ws1.cell(row=curr_r, column=col_i)
            cell.font = font_regular
            cell.border = thin_border
            if curr_r % 2 == 1:
                cell.fill = fill_zebra
            if col_i in (5, 6):
                cell.font = font_bold
                cell.fill = fill_highlight
        curr_r += 1

    # Auto-fit kolom ws1
    for col in ws1.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws1.column_dimensions[col_letter].width = max(max_len + 3, 12)

    # ==================== SHEET 2: KOMPARASI 4 BENDUNG ====================
    if all_bendungs_res:
        semi_comp, m_comp = all_bendungs_res
        ws2 = wb.create_sheet(title="Komparasi 4 Bendung")
        ws2.views.sheetView[0].showGridLines = True

        ws2.merge_cells("A1:E1")
        ws2["A1"] = f"PERBANDINGAN DEBIT ANDALAN Q{target_p} 4 BENDUNG KABUPATEN TEGAL"
        ws2["A1"].font = font_title
        ws2["A1"].alignment = align_left

        ws2.cell(row=3, column=1, value="A. PERBANDINGAN 1/2 BULANAN (L/s)").font = font_section
        for c_idx, col_name in enumerate(semi_comp.columns):
            c_cell = ws2.cell(row=4, column=c_idx + 1, value=col_name)
            c_cell.font = font_header
            c_cell.fill = fill_header_navy
            c_cell.alignment = align_center
            c_cell.border = thin_border

        r_comp = 5
        for _, row in semi_comp.iterrows():
            for c_idx, col_name in enumerate(semi_comp.columns):
                val = row[col_name]
                cell = ws2.cell(row=r_comp, column=c_idx + 1, value=val)
                cell.font = font_regular
                cell.border = thin_border
                cell.alignment = align_right if isinstance(val, (int, float)) else align_left
                if r_comp % 2 == 1:
                    cell.fill = fill_zebra
            r_comp += 1

        r_comp += 2
        ws2.cell(row=r_comp, column=1, value="B. PERBANDINGAN BULANAN (L/s)").font = font_section
        r_comp += 1
        for c_idx, col_name in enumerate(m_comp.columns):
            c_cell = ws2.cell(row=r_comp, column=c_idx + 1, value=col_name)
            c_cell.font = font_header
            c_cell.fill = fill_header_teal
            c_cell.alignment = align_center
            c_cell.border = thin_border

        r_comp += 1
        for _, row in m_comp.iterrows():
            for c_idx, col_name in enumerate(m_comp.columns):
                val = row[col_name]
                cell = ws2.cell(row=r_comp, column=c_idx + 1, value=val)
                cell.font = font_regular
                cell.border = thin_border
                cell.alignment = align_right if isinstance(val, (int, float)) else align_left
                if r_comp % 2 == 1:
                    cell.fill = fill_zebra
            r_comp += 1

        for col in ws2.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws2.column_dimensions[col_letter].width = max(max_len + 3, 14)

    # ==================== SHEET 3: DATA MENTAH HISTORIS ====================
    ws3 = wb.create_sheet(title="Data Mentah Historis")
    ws3.views.sheetView[0].showGridLines = True

    ws3.cell(row=1, column=1, value=f"MATRIKS DATA DEBIT HISTORIS 1/2 BULANAN - {bendung_name} (L/s)").font = font_title
    for c_idx, col_name in enumerate(matrix_df.columns):
        c_cell = ws3.cell(row=3, column=c_idx + 1, value=col_name)
        c_cell.font = font_header
        c_cell.fill = fill_header_navy
        c_cell.alignment = align_center
        c_cell.border = thin_border

    r_mat = 4
    for _, row in matrix_df.iterrows():
        for c_idx, col_name in enumerate(matrix_df.columns):
            val = row[col_name]
            cell = ws3.cell(row=r_mat, column=c_idx + 1, value=val if pd.notna(val) else "-")
            cell.font = font_regular
            cell.border = thin_border
            cell.alignment = align_right if isinstance(val, (int, float)) else align_center
            if r_mat % 2 == 1:
                cell.fill = fill_zebra
        r_mat += 1

    for col in ws3.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws3.column_dimensions[col_letter].width = max(max_len + 2, 11)

    wb.save(output)
    output.seek(0)
    return output


DEBIT_LOG_FILE = "manual_debit_log.csv"


def save_bendung_dataset(df: pd.DataFrame):
    """Menyimpan dataframe debit bendung ke parquet dan excel."""
    df.to_parquet(BENDUNG_PARQUET, index=False)
    df.to_excel(BENDUNG_EXCEL, index=False)


def log_debit_manual_entry(bendung: str, tahun: str, action: str, details: str = ""):
    """Mencatat aktivitas penambahan/pembaruan data debit bendung ke audit log CSV."""
    row = {
        "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Bendung": bendung,
        "Tahun_Hidrologi": tahun,
        "Aksi": action,
        "Keterangan": details
    }
    log_df = pd.DataFrame([row])
    if os.path.exists(DEBIT_LOG_FILE):
        log_df.to_csv(DEBIT_LOG_FILE, mode="a", header=False, index=False)
    else:
        log_df.to_csv(DEBIT_LOG_FILE, mode="w", header=True, index=False)


def get_debit_manual_log() -> pd.DataFrame:
    """Memuat seluruh log pencatatan manual debit bendung."""
    if os.path.exists(DEBIT_LOG_FILE):
        try:
            return pd.read_csv(DEBIT_LOG_FILE)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def add_or_update_bendung_record(bendung: str, tahun: str, period_values: dict, daerah_irigasi: str = "") -> Tuple[bool, str]:
    """Menambah atau memperbarui baris data debit bendung untuk satu tahun hidrologi."""
    df = load_bendung_dataset()
    if df.empty:
        return False, "Database debit bendung kosong."

    mask = (df["Bendung"] == bendung) & (df["Tahun_Hidrologi"] == tahun)
    if mask.any():
        for col, val in period_values.items():
            if col in df.columns:
                df.loc[mask, col] = val
        action = "UPDATE"
        msg = f"Data debit {bendung} tahun {tahun} berhasil diperbarui!"
    else:
        new_row = {"Bendung": bendung, "Tahun_Hidrologi": tahun}
        if not daerah_irigasi:
            di_series = df.loc[df["Bendung"] == bendung, "Daerah_Irigasi"]
            daerah_irigasi = di_series.iloc[0] if not di_series.empty else bendung
        new_row["Daerah_Irigasi"] = daerah_irigasi
        for col in SEMI_MONTHLY_COLS:
            new_row[col] = period_values.get(col, np.nan)
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        action = "INSERT"
        msg = f"Data debit baru {bendung} tahun {tahun} berhasil ditambahkan!"

    save_bendung_dataset(df)
    log_debit_manual_entry(bendung, tahun, action, f"{len(period_values)} nilai periode disimpan.")
    return True, msg


def render_data_debit_view():
    """Merender tab Data Debit Bendung (Tabel Matriks 1/2 Bulanan 2004/2005 - 2024/2025)."""
    df_bendung = load_bendung_dataset()
    if df_bendung.empty:
        st.error("Data debit bendung tidak ditemukan. Pastikan data_debit_bendung.parquet tersedia.")
        return

    with st.container(border=True):
        st.subheader("📋 Matriks Data Debit 1/2 Bulanan Bendung Kabupaten Tegal")
        st.caption(
            "Data historis pengamatan debit bendung tersusun dalam format 24 periode 1/2 bulanan (Oktober I s/d September II) "
            "dalam satuan **Liter/detik (L/s)** untuk 4 bendung di Kabupaten Tegal."
        )

    # Metric Badges
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Bendung", "4 Bendung", "Rajabawah, Pondoh, Kemaron, Lengkong")
    c2.metric("Tahun Pengamatan", f"{len(df_bendung['Tahun_Hidrologi'].unique())} Tahun", "2004/2005 - 2024/2025")
    c3.metric("Total Record Data", f"{len(df_bendung)} Baris", "24 Periode per Tahun")
    c4.metric("Satuan Pengukuran", "Liter / Detik (L/s)", "Laju Aliran Debit")

    # Filter Container
    with st.container(border=True):
        st.markdown("##### 🔍 Filter Tampilan Data Debit")
        col_fb, col_fy = st.columns([1.5, 2])
        with col_fb:
            b_list = ["Semua Bendung"] + get_bendungs_list()
            sel_b = st.selectbox("Pilih Bendung:", b_list, index=0, key="data_debit_sel_b")
        with col_fy:
            y_list = sorted(list(df_bendung["Tahun_Hidrologi"].unique()))
            sel_years = st.multiselect("Pilih Tahun Hidrologi:", y_list, default=y_list, key="data_debit_sel_y")

    # Apply Filter
    view_df = df_bendung.copy()
    if sel_b != "Semua Bendung":
        view_df = view_df[view_df["Bendung"] == sel_b]
    if sel_years:
        view_df = view_df[view_df["Tahun_Hidrologi"].isin(sel_years)]

    # Display Table
    st.markdown(f"##### 📑 Tabel Data Debit 1/2 Bulanan ({sel_b} — {len(view_df)} Record)")
    
    display_df = view_df.copy()
    fmt_dict = {col: "{:.1f}" for col in SEMI_MONTHLY_COLS}
    
    st.dataframe(
        display_df.style.format(fmt_dict, na_rep="-"),
        use_container_width=True,
        hide_index=True
    )

    # Statistical Summary Box per Periode if single bendung
    if sel_b != "Semua Bendung" and not view_df.empty:
        with st.expander("📊 Lihat Statistik Ringkasan per Periode 1/2 Bulanan (Rata-rata, Min, Max)", expanded=True):
            stat_rows = []
            for col in SEMI_MONTHLY_COLS:
                s = view_df[col].dropna()
                stat_rows.append({
                    "Periode": col,
                    "Rata-rata (L/s)": round(s.mean(), 2) if len(s) > 0 else 0.0,
                    "Min (L/s)": round(s.min(), 2) if len(s) > 0 else 0.0,
                    "Max (L/s)": round(s.max(), 2) if len(s) > 0 else 0.0,
                    "Jumlah Observasi (N)": len(s)
                })
            stat_df = pd.DataFrame(stat_rows)
            st.dataframe(stat_df.style.format({
                "Rata-rata (L/s)": "{:.2f}",
                "Min (L/s)": "{:.2f}",
                "Max (L/s)": "{:.2f}"
            }), use_container_width=True, hide_index=True)

    # Download Buttons
    st.markdown("---")
    st.markdown("##### 📥 Unduh Data Debit Bendung")
    col_dl1, col_dl2 = st.columns([2, 2])
    clean_name = sel_b.replace(" ", "_")
    with col_dl1:
        excel_buf = io.BytesIO()
        with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
            view_df.to_excel(writer, index=False, sheet_name="Data Debit Bendung")
        excel_buf.seek(0)
        st.download_button(
            label="📥 Download Data Debit (Excel .xlsx)",
            data=excel_buf.getvalue(),
            file_name=f"Data_Debit_{clean_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    with col_dl2:
        csv_bytes = view_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📄 Download Data Debit (CSV .csv)",
            data=csv_bytes,
            file_name=f"Data_Debit_{clean_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )


def render_input_debit_manual():
    """Merender tab Input Debit Manual untuk menambah atau mengupdate data debit bendung."""
    df_bendung = load_bendung_dataset()
    if df_bendung.empty:
        st.error("Data debit bendung tidak ditemukan.")
        return

    with st.container(border=True):
        st.subheader("✍️ Input & Pembaruan Data Debit Bendung Manual")
        st.caption(
            "Tambahkan data observasi debit tahun hidrologi baru atau perbarui nilai debit 1/2 bulanan "
            "untuk bendung di Kabupaten Tegal. Seluruh perubahan langsung tersimpan permanen ke database sistem."
        )

    tab_form, tab_grid = st.tabs([
        "📝 Formulir Input / Edit 1 Tahun Penuh",
        "📊 Editor Tabel Langsung (Spreadsheet Grid)"
    ])

    with tab_form:
        col_in_b, col_in_y = st.columns(2)
        with col_in_b:
            bendungs = get_bendungs_list()
            sel_b_in = st.selectbox("Pilih Bendung:", bendungs, key="in_bendung_choice")
        with col_in_y:
            existing_years = sorted(list(df_bendung.loc[df_bendung["Bendung"] == sel_b_in, "Tahun_Hidrologi"].unique()), reverse=True)
            y_mode = st.radio("Pilihan Tahun:", ["Pilih Tahun Yang Sudah Ada (Edit)", "Tambah Tahun Hidrologi Baru"], horizontal=True, key="in_yr_mode")
            if y_mode == "Pilih Tahun Yang Sudah Ada (Edit)":
                sel_y_in = st.selectbox("Pilih Tahun Hidrologi:", existing_years, key="in_sel_existing_yr")
            else:
                sel_y_in = st.text_input("Ketik Tahun Hidrologi Baru (Format: TTTT/TTTT, contoh: 2025/2026):", value="2025/2026", key="in_new_yr")

        # Load existing row if available
        existing_row = df_bendung[(df_bendung["Bendung"] == sel_b_in) & (df_bendung["Tahun_Hidrologi"] == sel_y_in)]
        current_vals = {}
        if not existing_row.empty:
            for col in SEMI_MONTHLY_COLS:
                val = existing_row[col].iloc[0]
                current_vals[col] = float(val) if pd.notna(val) else 0.0

        st.markdown(f"##### 💧 Nilai Debit 1/2 Bulanan — {sel_b_in} (Tahun: {sel_y_in})")
        st.caption("Masukkan nilai debit dalam satuan **Liter/detik (L/s)** untuk setiap periode 1/2 bulanan:")

        form_values = {}
        seasons = [
            ("Musim Hujan Bagian 1 (Oktober - Desember)", ["OKTOBER", "NOVEMBER", "DESEMBER"]),
            ("Musim Hujan Bagian 2 (Januari - Maret)", ["JANUARI", "FEBRUARI", "MARET"]),
            ("Musim Kemarau Bagian 1 (April - Juni)", ["APRIL", "MEI", "JUNI"]),
            ("Musim Kemarau Bagian 2 (Juli - September)", ["JULI", "AGUSTUS", "SEPTEMBER"])
        ]

        with st.form(key=f"debit_input_form_{sel_b_in}_{sel_y_in}"):
            for season_title, season_months in seasons:
                st.markdown(f"**{season_title}**")
                cols_season = st.columns(3)
                for m_idx, m_name in enumerate(season_months):
                    with cols_season[m_idx]:
                        st.markdown(f"**Bulan {m_name.capitalize()}**")
                        c1 = f"{m_name} I"
                        c2 = f"{m_name} II"
                        val1 = current_vals.get(c1, 0.0)
                        val2 = current_vals.get(c2, 0.0)
                        form_values[c1] = st.number_input(
                            f"{m_name} I (L/s)",
                            min_value=0.0,
                            max_value=100000.0,
                            value=float(val1),
                            step=1.0,
                            format="%.2f",
                            key=f"input_{sel_b_in}_{sel_y_in}_{c1}"
                        )
                        form_values[c2] = st.number_input(
                            f"{m_name} II (L/s)",
                            min_value=0.0,
                            max_value=100000.0,
                            value=float(val2),
                            step=1.0,
                            format="%.2f",
                            key=f"input_{sel_b_in}_{sel_y_in}_{c2}"
                        )
                st.markdown("<hr style='margin: 8px 0;'>", unsafe_allow_html=True)

            btn_submit = st.form_submit_button("💾 Simpan Data Debit Bendung", type="primary", use_container_width=True)

            if btn_submit:
                if not sel_y_in or "/" not in sel_y_in:
                    st.error("Format tahun hidrologi harus berupa 'TTTT/TTTT' (contoh: 2025/2026).")
                else:
                    ok, msg = add_or_update_bendung_record(sel_b_in, sel_y_in, form_values)
                    if ok:
                        st.success(f"✅ {msg}")
                        st.balloons()
                    else:
                        st.error(f"❌ Gagal menyimpan: {msg}")

    with tab_grid:
        st.markdown(f"##### 📊 Spreadsheet Editor Data Debit — {sel_b_in}")
        st.caption("Edit nilai debit secara langsung di dalam grid tabel di bawah ini. Klik **Simpan Perubahan Tabel** setelah selesai.")
        
        df_grid = df_bendung[df_bendung["Bendung"] == sel_b_in].copy().reset_index(drop=True)
        edited_df = st.data_editor(
            df_grid,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            key=f"data_editor_debit_{sel_b_in}"
        )
        if st.button("💾 Simpan Perubahan Tabel Langsung", key=f"btn_save_grid_{sel_b_in}"):
            full_df = load_bendung_dataset()
            full_df = full_df[full_df["Bendung"] != sel_b_in]
            full_df = pd.concat([full_df, edited_df], ignore_index=True)
            save_bendung_dataset(full_df)
            log_debit_manual_entry(sel_b_in, "SEMUA", "BULK_UPDATE", f"{len(edited_df)} baris diperbarui via grid")
            st.success(f"✅ Seluruh data debit {sel_b_in} berhasil disimpan!")
            st.rerun()

    # Audit Trail
    with st.expander("🕒 Riwayat Audit Log Penginputan Manual Debit Bendung", expanded=False):
        log_df = get_debit_manual_log()
        if not log_df.empty:
            st.dataframe(log_df, use_container_width=True, hide_index=True)
        else:
            st.caption("Belum ada riwayat pencatatan manual.")


def render_tab_weibull_content():
    """Merender seluruh antarmuka Tab Debit Andalan Bendung (Metode Weibull Q80)."""
    df_bendung = load_bendung_dataset()
    if df_bendung.empty:
        st.error("Data debit bendung tidak ditemukan. Pastikan data_debit_bendung.parquet tersedia.")
        return

    with st.container(border=True):
        st.subheader("💧 Analisis Debit Andalan 4 Bendung Kabupaten Tegal (Metode Weibull Q80)")
        st.caption(
            "Perhitungan debit andalan menggunakan rumus probabilitas Weibull: **P = [m / (N + 1)] × 100%** "
            "khusus keandalan 80% (Q80) untuk perencanaan irigasi & ketersediaan air baku sesuai Standar Perencanaan Irigasi KP-01 Ditjen SDA PUPR."
        )

    with st.container(border=True):
        st.markdown("##### ⚙️ Pengaturan Parameter Debit Andalan")
        bendung_options = [
            "Bendung Rajabawah (D.I. Rajabawah)",
            "Bendung Pondoh (D.I. Pondoh)",
            "Bendung Kemaron (D.I. Gung, Kemaron)",
            "Bendung Lengkong (D.I. Lengkong)",
            "📊 Perbandingan 4 Bendung Sekaligus"
        ]

        col_b_sel, col_p_sel, col_y_sel = st.columns([1.5, 1.2, 1.3])
        with col_b_sel:
            sel_bendung_label = st.selectbox("Pilih Bendung Pengamatan:", bendung_options, key="bendung_choice")
        with col_p_sel:
            prob_options = {
                "80% (Standar Irigasi KP-01 / Q80)": 80.0,
                "50% (Kondisi Normal / Q50)": 50.0,
                "90% (Kondisi Sangat Kering / Q90)": 90.0,
                "95% (Kondisi Kering Ekstrem / Q95)": 95.0
            }
            sel_prob_label = st.selectbox("Probabilitas Keandalan (P%):", list(prob_options.keys()), index=0, key="bendung_prob")
            target_p = prob_options[sel_prob_label]
            target_p_int = int(target_p)
        with col_y_sel:
            all_years = sorted(list(df_bendung["Tahun_Hidrologi"].unique()))
            yr_mode = st.radio("Rentang Tahun Hidrologi:", ["Semua Tahun (2004/2005 - 2024/2025)", "Pilih Tahun Tertentu"], horizontal=True, key="bendung_yr_mode")

    selected_years = None
    if yr_mode == "Pilih Tahun Tertentu":
        selected_years = st.multiselect("Pilih Tahun Pengamatan:", all_years, default=all_years, key="bendung_sel_years")
        if not selected_years:
            selected_years = all_years

    is_comparison = "Perbandingan 4 Bendung" in sel_bendung_label

    if is_comparison:
        st.markdown("---")
        st.markdown(f"#### 📊 Perbandingan Debit Andalan Q{target_p_int} Empat Bendung Kabupaten Tegal")
        st.caption("Perbandingan ketersediaan debit andalan 1/2 bulanan dan bulanan (satuan Liter/detik) antara Bendung Rajabawah, Pondoh, Kemaron, dan Lengkong.")

        semi_comp, m_comp = compare_all_bendungs(target_p, df_bendung)

        # Multi-line Hydrograph Plotly Chart
        fig_comp = go.Figure()
        colors = {
            "RAJABAWAH": "#2563EB", # Blue
            "PONDOH": "#DC2626",    # Red
            "KEMARON": "#059669",   # Emerald
            "LENGKONG": "#7C3AED"   # Purple
        }
        for b_name in get_bendungs_list():
            col_name = f"{b_name} (L/s)"
            if col_name in semi_comp.columns:
                fig_comp.add_trace(go.Scatter(
                    x=semi_comp["Periode"],
                    y=semi_comp[col_name],
                    mode="lines+markers",
                    name=f"Bendung {b_name.capitalize()}",
                    line=dict(color=colors.get(b_name, "#1E3A8A"), width=3),
                    marker=dict(size=6),
                    hovertemplate="<b>%{x}</b><br>Debit: %{y:.2f} L/s<extra></extra>"
                ))

        fig_comp.update_layout(
            title=f"Hidrograf Komparasi Debit Andalan Q{target_p_int} 1/2 Bulanan (Liter/detik)",
            xaxis_title="Periode 1/2 Bulanan (Oktober I - September II)",
            yaxis_title="Debit Andalan (Liter/detik)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified",
            margin=dict(l=40, r=40, t=60, b=40),
            height=480
        )
        st.plotly_chart(fig_comp, use_container_width=True)

        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.markdown(f"##### 📋 Tabel Komparasi 1/2 Bulanan (Q{target_p_int} L/s)")
            st.dataframe(semi_comp.style.format({c: "{:.2f}" for c in semi_comp.columns if "(L/s)" in c}), use_container_width=True, hide_index=True)
        with col_t2:
            st.markdown(f"##### 📅 Tabel Komparasi Bulanan (Q{target_p_int} L/s)")
            st.dataframe(m_comp.style.format({c: "{:.2f}" for c in m_comp.columns if "(L/s)" in c}), use_container_width=True, hide_index=True)

        # Bar chart bulanan
        fig_bar = go.Figure()
        for b_name in get_bendungs_list():
            col_name = f"{b_name} (L/s)"
            if col_name in m_comp.columns:
                fig_bar.add_trace(go.Bar(
                    x=m_comp["Bulan"],
                    y=m_comp[col_name],
                    name=f"Bendung {b_name.capitalize()}",
                    marker_color=colors.get(b_name, "#1E3A8A")
                ))
        fig_bar.update_layout(
            barmode="group",
            title=f"Diagram Batang Komparasi Debit Bulanan Q{target_p_int} (Liter/detik)",
            xaxis_title="Bulan (Tahun Hidrologi)",
            yaxis_title="Debit Bulanan (Liter/detik)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=40, r=40, t=60, b=40),
            height=420
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    else:
        # Single Bendung Analysis
        if "RAJABAWAH" in sel_bendung_label.upper():
            b_key = "RAJABAWAH"
        elif "PONDOH" in sel_bendung_label.upper():
            b_key = "PONDOH"
        elif "KEMARON" in sel_bendung_label.upper():
            b_key = "KEMARON"
        elif "LENGKONG" in sel_bendung_label.upper():
            b_key = "LENGKONG"
        else:
            b_key = "RAJABAWAH"

        res = analyze_bendung_debit(df_bendung, b_key, target_p, selected_years)
        if not res:
            st.warning("Data bendung tidak tersedia.")
            return

        kpi = res["kpi"]
        semi_df = res["semi_monthly_df"]
        monthly_df = res["monthly_df"]

        st.markdown("---")
        # KPI Badges
        c_kpi1, c_kpi2, c_kpi3, c_kpi4 = st.columns(4)
        c_kpi1.metric(
            label=f"Rata-rata Tahunan Q{target_p_int}",
            value=f"{kpi['avg_annual_q']:.1f} L/s",
            help=f"Rata-rata debit andalan Q{target_p_int} sepanjang 24 periode 1/2 bulanan."
        )
        c_kpi2.metric(
            label=f"Musim Hujan (Rendeng)",
            value=f"{kpi['wet_season_q']:.1f} L/s",
            help="Rata-rata debit andalan periode Oktober s/d Maret (musim tanam rendeng)."
        )
        c_kpi3.metric(
            label=f"Musim Kemarau (Gadu)",
            value=f"{kpi['dry_season_q']:.1f} L/s",
            help="Rata-rata debit andalan periode April s/d September (musim tanam gadu)."
        )
        c_kpi4.metric(
            label=f"Rentang Q{target_p_int} (Min - Max)",
            value=f"{kpi['min_q']:.1f} - {kpi['max_q']:.1f} L/s",
            help=f"Min: {kpi['min_q']:.1f} L/s ({kpi['min_period']}), Max: {kpi['max_q']:.1f} L/s ({kpi['max_period']})"
        )

        sub_tab1, sub_tab2, sub_tab3 = st.tabs([
            "📋 Rekapitulasi 1/2 Bulanan & Bulanan",
            "📈 Grafik & Kurva Hidrologi",
            "📑 Data Historis & Peringkat Weibull"
        ])

        with sub_tab1:
            st.markdown(f"##### 1. Rekapitulasi Debit Andalan 1/2 Bulanan — {kpi['bendung']} ({kpi['di']})")
            st.caption(f"Data tersusun dalam format 24 periode 1/2 bulanan dalam satuan Liter/detik (L/s) dengan probabilitas Weibull {target_p_int}%.")
            
            format_dict_semi = {
                f"Q{target_p_int} Andalan (L/s)": "{:.2f}",
                "Q50 Normal (L/s)": "{:.2f}",
                "Q90 Kering (L/s)": "{:.2f}",
                "Rata-rata Historis (L/s)": "{:.2f}",
                "Min (L/s)": "{:.2f}",
                "Max (L/s)": "{:.2f}"
            }
            st.dataframe(semi_df.style.format(format_dict_semi), use_container_width=True, hide_index=True)

            st.markdown(f"##### 2. Rekapitulasi Debit Bulanan — {kpi['bendung']} ({kpi['di']})")
            st.caption("Hasil rekapitulasi per bulan dalam satuan Liter/detik (L/s), menampilkan debit Periode I, Periode II, Rata-rata 1/2 Bulanan, dan Debit Andalan Bulanan.")
            
            format_dict_month = {
                f"Q{target_p_int} Periode I (L/s)": "{:.2f}",
                f"Q{target_p_int} Periode II (L/s)": "{:.2f}",
                f"Rata-rata Q{target_p_int} 1/2 Bulanan (L/s)": "{:.2f}",
                f"Q{target_p_int} Debit Bulanan (L/s)": "{:.2f}",
                "Rata-rata Historis (L/s)": "{:.2f}",
                "Min (L/s)": "{:.2f}",
                "Max (L/s)": "{:.2f}"
            }
            st.dataframe(monthly_df.style.format(format_dict_month), use_container_width=True, hide_index=True)

        with sub_tab2:
            st.markdown(f"##### 🌊 Hidrograf Debit Andalan 1/2 Bulanan (Q{target_p_int})")
            fig_hydro = go.Figure()

            # Shaded area Max-Min
            fig_hydro.add_trace(go.Scatter(
                x=semi_df["Periode"],
                y=semi_df["Max (L/s)"],
                mode="lines",
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip"
            ))
            fig_hydro.add_trace(go.Scatter(
                x=semi_df["Periode"],
                y=semi_df["Min (L/s)"],
                mode="lines",
                line=dict(width=0),
                fill="tonexty",
                fillcolor="rgba(148, 163, 184, 0.25)",
                name="Rentang Historis (Min - Max)",
                hoverinfo="skip"
            ))

            # Rata-rata historis
            fig_hydro.add_trace(go.Scatter(
                x=semi_df["Periode"],
                y=semi_df["Rata-rata Historis (L/s)"],
                mode="lines+markers",
                name="Rata-rata Historis",
                line=dict(color="#F59E0B", width=2, dash="dash"),
                marker=dict(size=5),
                hovertemplate="<b>%{x}</b><br>Rata-rata Historis: %{y:.2f} L/s<extra></extra>"
            ))

            # Q80 Andalan
            fig_hydro.add_trace(go.Scatter(
                x=semi_df["Periode"],
                y=semi_df[f"Q{target_p_int} Andalan (L/s)"],
                mode="lines+markers",
                name=f"Debit Andalan Q{target_p_int}",
                line=dict(color="#1E3A8A", width=3.5),
                marker=dict(size=7, color="#1E3A8A"),
                hovertemplate="<b>%{x}</b><br>Debit Andalan Q" + str(target_p_int) + ": <b>%{y:.2f} L/s</b><extra></extra>"
            ))

            # Q50 Normal
            fig_hydro.add_trace(go.Scatter(
                x=semi_df["Periode"],
                y=semi_df["Q50 Normal (L/s)"],
                mode="lines",
                name="Q50 (Kondisi Normal)",
                line=dict(color="#10B981", width=1.5, dash="dot"),
                hovertemplate="<b>%{x}</b><br>Q50 Normal: %{y:.2f} L/s<extra></extra>"
            ))

            fig_hydro.update_layout(
                title=f"Hidrograf Debit Andalan 1/2 Bulanan — {kpi['bendung']} ({kpi['di']})",
                xaxis_title="Periode 1/2 Bulanan (Tahun Hidrologi: Okt I s/d Sep II)",
                yaxis_title="Debit (Liter/detik)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                hovermode="x unified",
                margin=dict(l=40, r=40, t=60, b=40),
                height=460
            )
            st.plotly_chart(fig_hydro, use_container_width=True)

            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.markdown(f"##### 📊 Perbandingan Debit 1/2 Bulanan per Bulan (L/s)")
                fig_m_bar = go.Figure()
                fig_m_bar.add_trace(go.Bar(
                    x=monthly_df["Bulan"],
                    y=monthly_df[f"Q{target_p_int} Periode I (L/s)"],
                    name=f"Q{target_p_int} Periode I",
                    marker_color="#3B82F6"
                ))
                fig_m_bar.add_trace(go.Bar(
                    x=monthly_df["Bulan"],
                    y=monthly_df[f"Q{target_p_int} Periode II (L/s)"],
                    name=f"Q{target_p_int} Periode II",
                    marker_color="#0D9488"
                ))
                fig_m_bar.add_trace(go.Scatter(
                    x=monthly_df["Bulan"],
                    y=monthly_df[f"Rata-rata Q{target_p_int} 1/2 Bulanan (L/s)"],
                    mode="lines+markers",
                    name="Rata-rata Bulanan",
                    line=dict(color="#EF4444", width=3),
                    marker=dict(size=6)
                ))
                fig_m_bar.update_layout(
                    barmode="group",
                    title="Debit Periode I vs Periode II (L/s)",
                    xaxis_title="Bulan",
                    yaxis_title="Debit (L/s)",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    height=400,
                    margin=dict(l=30, r=30, t=50, b=30)
                )
                st.plotly_chart(fig_m_bar, use_container_width=True)

            with col_g2:
                st.markdown(f"##### 📉 Kurva Durasi Debit Rata-rata Bulanan (Flow Duration Curve)")
                m_series_all = res["matrix_df"][SEMI_MONTHLY_COLS].values.flatten()
                m_valid = pd.Series(m_series_all).dropna()
                rank_fdc = calculate_weibull_ranking(m_valid)
                if not rank_fdc.empty:
                    fig_fdc = go.Figure()
                    fig_fdc.add_trace(go.Scatter(
                        x=rank_fdc["P (%)"],
                        y=rank_fdc["Debit (L/s)"],
                        mode="lines",
                        name="Kurva Durasi Debit",
                        line=dict(color="#1E3A8A", width=2.5),
                        hovertemplate="P: %{x:.1f}%<br>Debit: %{y:.2f} L/s<extra></extra>"
                    ))
                    q_val_fdc = interpolate_weibull_quantile(rank_fdc, target_p)
                    fig_fdc.add_vline(
                        x=target_p, line_width=2, line_dash="dash", line_color="#EF4444",
                        annotation_text=f"P = {target_p_int}% ({q_val_fdc:.1f} L/s)",
                        annotation_position="top right"
                    )
                    fig_fdc.update_layout(
                        title=f"Kurva Durasi Debit Keseluruhan ({b_key})",
                        xaxis_title="Probabilitas Terlampaui P (%)",
                        yaxis_title="Debit (L/s)",
                        height=400,
                        margin=dict(l=30, r=30, t=50, b=30)
                    )
                    st.plotly_chart(fig_fdc, use_container_width=True)

        with sub_tab3:
            with st.expander(f"📋 Matriks Data Mentah Debit Historis 1/2 Bulanan — {kpi['bendung']} (2004/2005 - 2024/2025)", expanded=False):
                st.caption("Nilai debit historis 1/2 bulanan yang diobservasi langsung pada bendung (satuan Liter/detik):")
                st.dataframe(res["matrix_df"], use_container_width=True, hide_index=True)

            with st.expander(f"🔍 Rincian Perhitungan Rumus Peringkat Weibull P = [m / (N + 1)] × 100%", expanded=False):
                st.caption("Pilih periode 1/2 bulanan atau bulanan untuk memeriksa urutan ranking debit terurut:")
                all_rank_keys = list(res["rankings_semi"].keys()) + list(res["rankings_monthly"].keys())
                sel_rank_period = st.selectbox("Pilih Periode Pengamatan untuk Diinspeksi:", all_rank_keys, key="sel_rank_inspect")
                
                if sel_rank_period in res["rankings_semi"]:
                    df_r_show = res["rankings_semi"][sel_rank_period]
                else:
                    df_r_show = res["rankings_monthly"][sel_rank_period]

                if not df_r_show.empty:
                    col_r1, col_r2 = st.columns([2, 1])
                    with col_r1:
                        st.dataframe(df_r_show, use_container_width=True, hide_index=True)
                    with col_r2:
                        n_tot = len(df_r_show)
                        m_tgt = (target_p / 100.0) * (n_tot + 1)
                        q_tgt_val = interpolate_weibull_quantile(df_r_show, target_p)
                        st.info(f"""
                        **Parameter Rumus Weibull:**
                        - Jumlah Sampel ($N$): **{n_tot} Tahun**
                        - Keandalan Target ($P$): **{target_p_int}%**
                        - Peringkat Target ($m$): **{m_tgt:.2f}**
                        - **Debit Andalan Q{target_p_int}**: **{q_tgt_val:.2f} L/s**
                        """)

        # Tombol Download Excel Laporan Bendung
        st.markdown("---")
        st.markdown(f"##### 📥 Unduh Laporan Lengkap Debit Andalan Bendung {kpi['bendung']} (Excel .xlsx)")
        st.caption("Laporan Excel mencakup: Ringkasan KPI, Tabel 1/2 Bulanan, Tabel Bulanan, Komparasi 4 Bendung, dan Matriks Data Mentah.")
        
        col_dl_b1, col_dl_b2 = st.columns([2, 3])
        with col_dl_b1:
            comps_all = compare_all_bendungs(target_p, df_bendung)
            excel_bendung_bytes = export_bendung_debit_to_excel(b_key, res, comps_all)
            clean_b_name = b_key.capitalize()
            st.download_button(
                label=f"📥 Download Laporan {clean_b_name} (Excel .xlsx)",
                data=excel_bendung_bytes.getvalue(),
                file_name=f"Laporan_Debit_Andalan_{b_key}_Q{target_p_int}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

