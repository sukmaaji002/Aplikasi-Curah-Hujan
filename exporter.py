import io
import datetime
import re
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image as OpenpyxlImage

def natural_station_key(stn_str):
    """Sortir alami untuk kode stasiun agar 22a, 22b mendahului 23."""
    match = re.match(r"^(\d+)([a-zA-Z]*)$", str(stn_str).strip())
    if match:
        num, letter = match.groups()
        return (int(num), letter.lower())
    return (9999, str(stn_str).lower())

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Image as ReportlabImage
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Canvas khusus untuk menghitung total halaman dan mencetak footer 'Halaman X dari Y'."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#4B5563"))
        
        # Garis footer
        page_width, page_height = self._pagesize
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(36, 36, page_width - 36, 36)
        
        # Teks footer kiri dan kanan
        footer_left = "Sistem Analisis & Filter Data Curah Hujan"
        footer_right = f"Halaman {self._pageNumber} dari {page_count}"
        self.drawString(36, 24, footer_left)
        self.drawRightString(page_width - 36, 24, footer_right)
        self.restoreState()


def generate_weibull_bar_chart(weibull_summary: pd.DataFrame, crop_name: str = "Padi") -> bytes:
    """Menghasilkan gambar grafik batang perbandingan R80 vs Q80 bulanan (PNG bytes)."""
    if weibull_summary is None or weibull_summary.empty:
        return b""
    try:
        sub_months = weibull_summary[weibull_summary["Bulan / Periode"] != "TOTAL TAHUNAN"].copy()
        if sub_months.empty:
            return b""

        months = sub_months["Bulan / Periode"].tolist()
        r80 = [float(v) for v in sub_months["R80 Curah Hujan (mm)"]]
        q80 = [float(v) for v in sub_months["Q80 Andalan Irigasi (mm)"]]

        fig, ax = plt.subplots(figsize=(7.2, 3.4), dpi=150)
        x = list(range(len(months)))
        width = 0.38

        rects1 = ax.bar([i - width/2 for i in x], r80, width, label='R80 Curah Hujan (mm)', color='#2563EB', edgecolor='none')
        rects2 = ax.bar([i + width/2 for i in x], q80, width, label=f'Q80 Irigasi {crop_name} (mm)', color='#0F766E', edgecolor='none')

        ax.set_ylabel('Curah Hujan & Debit (mm)', fontsize=9, fontweight='bold', color='#1E293B')
        ax.set_title(f'Perbandingan Curah Hujan R80 vs Q80 Irigasi Bulanan ({crop_name})', fontsize=11, fontweight='bold', color='#1E3A8A', pad=10)
        ax.set_xticks(list(x))
        ax.set_xticklabels([m[:3] for m in months], fontsize=8, fontweight='bold')
        ax.legend(loc='upper right', frameon=True, facecolor='#F8FAFC', edgecolor='#CBD5E1', fontsize=8)
        ax.grid(axis='y', linestyle='--', alpha=0.5)
        ax.set_axisbelow(True)

        for rect in rects1:
            h = rect.get_height()
            if h > 0:
                ax.annotate(f'{h:.0f}', xy=(rect.get_x() + rect.get_width()/2, h), xytext=(0, 2),
                            textcoords="offset points", ha='center', va='bottom', fontsize=6.5, color='#1E3A8A')
        for rect in rects2:
            h = rect.get_height()
            if h > 0:
                ax.annotate(f'{h:.0f}', xy=(rect.get_x() + rect.get_width()/2, h), xytext=(0, 2),
                            textcoords="offset points", ha='center', va='bottom', fontsize=6.5, color='#0F766E')

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150)
        plt.close(fig)
        return buf.getvalue()
    except Exception:
        return b""


def generate_weibull_curve_chart(annual_ranking: pd.DataFrame) -> bytes:
    """Menghasilkan gambar kurva durasi curah hujan tahunan metode Weibull (PNG bytes)."""
    if annual_ranking is None or annual_ranking.empty:
        return b""
    try:
        p_vals = [float(v) for v in annual_ranking["Probabilitas P (%)"]]
        ch_vals = [float(v) for v in annual_ranking["Nilai"]]
        years = [str(v) for v in annual_ranking["Tahun"]]

        fig, ax = plt.subplots(figsize=(7.2, 3.4), dpi=150)
        ax.plot(p_vals, ch_vals, marker='o', markersize=5, color='#1E3A8A', linewidth=2.0, label='Curah Hujan Tahunan')
        ax.axvline(x=80, color='#DC2626', linestyle='--', linewidth=1.6, label='P = 80% (Standar Irigasi KP-01)')

        for px, py, yr in zip(p_vals, ch_vals, years):
            ax.annotate(f"{yr}", (px, py), textcoords="offset points", xytext=(0, 5), ha='center', fontsize=7, color='#334155')

        ax.set_xlabel('Probabilitas Terlampaui P (%) = [m / (N + 1)] x 100', fontsize=9, fontweight='bold', color='#1E293B')
        ax.set_ylabel('Curah Hujan Tahunan (mm)', fontsize=9, fontweight='bold', color='#1E293B')
        ax.set_title('Kurva Durasi Curah Hujan Tahunan (Weibull Duration Curve)', fontsize=11, fontweight='bold', color='#1E3A8A', pad=10)
        ax.set_xlim(0, 100)
        ax.legend(loc='lower left', frameon=True, facecolor='#F8FAFC', edgecolor='#CBD5E1', fontsize=8)
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.set_axisbelow(True)

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150)
        plt.close(fig)
        return buf.getvalue()
    except Exception:
        return b""


def export_to_excel(
    df: pd.DataFrame,
    summary_df: pd.DataFrame,
    matrix_df: pd.DataFrame = None,
    filter_info: dict = None,
    all_matrices_dict: dict = None,
    cross_station_monthly: pd.DataFrame = None,
    pmax_matrix: pd.DataFrame = None,
    weibull_data: dict = None
) -> io.BytesIO:
    """Mengekspor data terfilter, ringkasan, dan seluruh matriks hidrologi ke format Excel (.xlsx)."""
    output = io.BytesIO()
    wb = Workbook()
    
    # Style definitions
    font_title = Font(name="Calibri", size=14, bold=True, color="1E3A8A")
    font_block_title = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    font_subtitle = Font(name="Calibri", size=10, italic=True, color="4B5563")
    font_header = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    font_bold = Font(name="Calibri", size=10, bold=True)
    font_regular = Font(name="Calibri", size=10)
    
    fill_header_navy = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    fill_header_teal = PatternFill(start_color="0F766E", end_color="0F766E", fill_type="solid")
    fill_block_header = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    fill_subtotal = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    fill_black = PatternFill(start_color="000000", end_color="000000", fill_type="solid")
    font_note = Font(name="Calibri", size=9, italic=True, color="4B5563")
    
    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1")
    )
    
    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")

    # ==================== DATA HARIAN TERFILTER DIPISAHKAN PER TAHUN ====================
    unique_years = sorted(list(df["Tahun"].unique()))
    headers_data = ["No", "Stasiun", "Tahun", "Bulan", "Hari", "Tanggal", "Curah Hujan (mm)", "Status", "Kategori BMKG"]

    info_parts = []
    if filter_info:
        if "periode" in filter_info:
            info_parts.append(f"Periode: {filter_info['periode']}")
        if "stasiun" in filter_info:
            info_parts.append(f"Stasiun: {filter_info['stasiun']}")
        if "kategori" in filter_info:
            info_parts.append(f"Filter: {filter_info['kategori']}")
    subtitle_text = " | ".join(info_parts) if info_parts else f"Diekspor pada: {datetime.datetime.now().strftime('%d-%m-%Y %H:%M')}"

    start_row = 4
    for idx_yr, yr in enumerate(unique_years):
        sheet_title = f"Data Harian {yr}"
        if idx_yr == 0:
            ws_yr = wb.active
            ws_yr.title = sheet_title
        else:
            ws_yr = wb.create_sheet(title=sheet_title)
        
        ws_yr.views.sheetView[0].showGridLines = True

        # Judul per sheet tahun
        ws_yr["A1"] = f"DATA CURAH HUJAN HARIAN TERFILTER - TAHUN {yr}"
        ws_yr["A1"].font = font_title
        ws_yr["A2"] = subtitle_text
        ws_yr["A2"].font = font_subtitle

        # Headers
        for col_idx, h in enumerate(headers_data, 1):
            cell = ws_yr.cell(row=start_row, column=col_idx, value=h)
            cell.font = font_header
            cell.fill = fill_header_navy
            cell.alignment = align_center
            cell.border = thin_border

        # Filter data hanya untuk tahun ini
        df_yr = df[df["Tahun"] == yr]
        row_curr = start_row + 1
        for i, (_, r) in enumerate(df_yr.iterrows(), 1):
            tgl_str = pd.to_datetime(r["Tanggal"]).strftime("%Y-%m-%d") if pd.notna(r["Tanggal"]) else "-"
            is_rusak = (str(r["Status"]) == "RUSAK")
            ch_val = None if is_rusak else (r["Curah_Hujan"] if pd.notna(r["Curah_Hujan"]) else "-")
            
            row_vals = [
                i,
                str(r["Stasiun"]),
                int(r["Tahun"]),
                r["Nama_Bulan"],
                int(r["Hari"]),
                tgl_str,
                ch_val,
                str(r["Status"]),
                str(r["Kategori_BMKG"])
            ]
            
            for c_idx, val in enumerate(row_vals, 1):
                cell = ws_yr.cell(row=row_curr, column=c_idx, value=val)
                cell.font = font_regular
                cell.border = thin_border
                if c_idx == 7 and is_rusak:
                    cell.value = None
                    cell.fill = fill_black
                elif c_idx in (1, 2, 3, 5, 6, 8):
                    cell.alignment = align_center
                elif c_idx == 7 and isinstance(val, (int, float)):
                    cell.alignment = align_right
                    cell.number_format = "0.0"
                else:
                    cell.alignment = align_left
            row_curr += 1

        # Tambahkan catatan alat rusak di bagian bawah tabel data harian
        ws_yr.cell(row=row_curr + 1, column=1, value="* Catatan: Sel Curah Hujan dengan arsir hitam (kosong tanpa angka) menandakan alat pengukur hujan (sensor) dalam kondisi RUSAK.")
        ws_yr.cell(row=row_curr + 1, column=1).font = font_note

        # Auto-adjust column widths
        for col in ws_yr.columns:
            col_letter = get_column_letter(col[0].column)
            max_len = max(len(str(cell.value or '')) for cell in col)
            ws_yr.column_dimensions[col_letter].width = max(max_len + 3, 10)

    # ==================== SHEET 2: RINGKASAN STASIUN ====================
    if not summary_df.empty:
        ws_sum = wb.create_sheet(title="Ringkasan Per Stasiun")
        ws_sum.views.sheetView[0].showGridLines = True

        ws_sum["A1"] = "RINGKASAN STATISTIK CURAH HUJAN PER STASIUN"
        ws_sum["A1"].font = font_title
        ws_sum["A2"] = subtitle_text
        ws_sum["A2"].font = font_subtitle

        sum_headers = [
            "No", "Stasiun", "Total CH (mm)", "Rata-rata (mm)",
            "CH Maks (mm)", "Tgl Hujan Maks", "Hari Hujan (>0mm)",
            "Hari Kering (0mm)", "Sensor Rusak", "Total Data Hari"
        ]
        for col_idx, h in enumerate(sum_headers, 1):
            cell = ws_sum.cell(row=start_row, column=col_idx, value=h)
            cell.font = font_header
            cell.fill = fill_header_teal
            cell.alignment = align_center
            cell.border = thin_border

        row_curr = start_row + 1
        for i, (_, r) in enumerate(summary_df.iterrows(), 1):
            def safe_flt(val, default=0.0):
                try:
                    return float(val) if pd.notna(val) else default
                except (ValueError, TypeError):
                    return default

            def safe_int(val, default=0):
                try:
                    return int(val) if pd.notna(val) else default
                except (ValueError, TypeError):
                    return default

            vals = [
                i,
                str(r["Stasiun"]),
                safe_flt(r.get("Total Curah Hujan (mm)")),
                safe_flt(r.get("Rata-rata Harian (mm)")),
                safe_flt(r.get("Curah Hujan Maks (mm)")),
                str(r.get("Tgl Hujan Maks", "-")),
                safe_int(r.get("Hari Hujan (>0 mm)")),
                safe_int(r.get("Hari Kering (0 mm)")),
                safe_int(r.get("Sensor Rusak")),
                safe_int(r.get("Total Data Hari"))
            ]
            for c_idx, val in enumerate(vals, 1):
                cell = ws_sum.cell(row=row_curr, column=c_idx, value=val)
                cell.font = font_regular
                cell.border = thin_border
                if c_idx in (1, 2, 6):
                    cell.alignment = align_center
                elif c_idx in (3, 4, 5):
                    cell.alignment = align_right
                    cell.number_format = "0.0"
                else:
                    cell.alignment = align_right
                    cell.number_format = "#,##0"
            row_curr += 1

        # Tambahkan Baris Total / Rata-rata jika stasiun lebih dari 1
        if len(summary_df) > 1:
            tot_ch = summary_df["Total Curah Hujan (mm)"].sum()
            avg_ch = summary_df["Rata-rata Harian (mm)"].mean()
            max_ch = summary_df["Curah Hujan Maks (mm)"].max()
            tot_hh = summary_df["Hari Hujan (>0 mm)"].sum()
            tot_hk = summary_df["Hari Kering (0 mm)"].sum()
            tot_sr = summary_df["Sensor Rusak"].sum()
            tot_th = summary_df["Total Data Hari"].sum()

            sum_vals = [
                "", "RATA-RATA / TOTAL", round(tot_ch, 1), round(avg_ch, 2),
                round(max_ch, 1), "-", int(tot_hh), int(tot_hk), int(tot_sr), int(tot_th)
            ]
            for c_idx, val in enumerate(sum_vals, 1):
                cell = ws_sum.cell(row=row_curr, column=c_idx, value=val)
                cell.font = font_bold
                cell.fill = fill_subtotal
                cell.border = thin_border
                if c_idx in (1, 2, 6):
                    cell.alignment = align_center
                elif c_idx in (3, 4, 5):
                    cell.alignment = align_right
                    cell.number_format = "0.0"
                else:
                    cell.alignment = align_right
                    cell.number_format = "#,##0"
            row_curr += 1

        for col in ws_sum.columns:
            col_letter = get_column_letter(col[0].column)
            max_len = max(len(str(cell.value or '')) for cell in col)
            ws_sum.column_dimensions[col_letter].width = max(max_len + 3, 13)

    # ==================== SHEET 3: MATRIKS HIDROLOGI LENGKAP ====================
    # Mendukung seluruh stasiun dan seluruh tahun yang dipilih
    if all_matrices_dict is None and filter_info and "all_matrices" in filter_info:
        all_matrices_dict = filter_info["all_matrices"]
    dict_to_export = all_matrices_dict if (all_matrices_dict and len(all_matrices_dict) > 0) else None
    if dict_to_export is None and (matrix_df is not None and not matrix_df.empty):
        stn_single = filter_info.get("stasiun_matriks", "Stasiun") if filter_info else "Stasiun"
        yr_single = filter_info.get("tahun_matriks", 2020) if filter_info else 2020
        dict_to_export = {(stn_single, yr_single): matrix_df}

    if dict_to_export:
        ws_mat = wb.create_sheet(title="Matriks Hidrologi Lengkap")
        ws_mat.views.sheetView[0].showGridLines = True
        
        ws_mat["A1"] = "MATRIKS DATA CURAH HUJAN BULANAN (FORMAT STANDAR HIDROLOGI)"
        ws_mat["A1"].font = font_title
        ws_mat["A2"] = f"Total {len(dict_to_export)} Matriks Pengamatan Terpilih | Diekspor: {datetime.datetime.now().strftime('%d-%m-%Y %H:%M')}"
        ws_mat["A2"].font = font_subtitle

        curr_r = 4
        # Sortir stasiun dan tahun: Nama stasiun dahulu, kemudian tahun-tahunnya berurutan!
        sorted_keys = sorted(
            list(dict_to_export.keys()),
            key=lambda k: (natural_station_key(k[0]), int(k[1]))
        )

        for (stn_name, yr_val) in sorted_keys:
            mat_data = dict_to_export[(stn_name, yr_val)]
            if mat_data.empty:
                continue

            num_cols = len(mat_data.columns) + 1  # 1 kolom 'Tgl' + jumlah kolom bulan terpilih

            # Block Header: STASIUN & TAHUN
            ws_mat.merge_cells(start_row=curr_r, start_column=1, end_row=curr_r, end_column=num_cols)
            for c_c in range(1, num_cols + 1):
                cell_box = ws_mat.cell(row=curr_r, column=c_c)
                cell_box.fill = fill_block_header
                cell_box.border = thin_border
                if c_c == 1:
                    cell_box.value = f"STASIUN : {stn_name}   |   TAHUN : {yr_val}"
                    cell_box.font = font_block_title
                    cell_box.alignment = align_left
            curr_r += 1

            # Headers: Tgl, Jan..Des
            mat_headers = ["Tgl"] + list(mat_data.columns)
            for col_idx, h in enumerate(mat_headers, 1):
                cell = ws_mat.cell(row=curr_r, column=col_idx, value=h)
                cell.font = font_header
                cell.fill = fill_header_navy
                cell.alignment = align_center
                cell.border = thin_border
            curr_r += 1

            # Table rows: 1..31 + JUMLAH, RATA-RATA, MAKSIMUM, HARI HUJAN
            for idx_label, row_vals in mat_data.iterrows():
                is_summary_row = str(idx_label) in ("JUMLAH", "RATA-RATA", "MAKSIMUM", "HARI HUJAN")
                cell_idx = ws_mat.cell(row=curr_r, column=1, value=str(idx_label))
                cell_idx.font = font_bold if is_summary_row else font_regular
                cell_idx.alignment = align_center
                cell_idx.border = thin_border
                if is_summary_row:
                    cell_idx.fill = fill_subtotal

                for c_idx, val in enumerate(row_vals, 2):
                    cell = ws_mat.cell(row=curr_r, column=c_idx)
                    val_str = str(val).strip().upper() if pd.notna(val) else ""
                    if val_str == "RUSAK":
                        cell.value = None
                        cell.fill = fill_black
                    elif pd.isna(val) or val_str in ("-", ""):
                        cell.value = "-"
                        cell.alignment = align_center
                    else:
                        num = float(val)
                        if is_summary_row and str(idx_label) == "HARI HUJAN":
                            cell.value = int(round(num))
                            cell.alignment = align_right
                            cell.number_format = "#,##0"
                        elif is_summary_row and str(idx_label) in ("JUMLAH", "RATA-RATA"):
                            cell.value = round(num, 1)
                            cell.alignment = align_right
                            cell.number_format = "0.0"
                        elif is_summary_row and str(idx_label) == "MAKSIMUM":
                            if num.is_integer():
                                cell.value = int(num)
                                cell.alignment = align_right
                                cell.number_format = "#,##0"
                            else:
                                cell.value = round(num, 1)
                                cell.alignment = align_right
                                cell.number_format = "0.0"
                        elif num == 0:
                            cell.value = 0
                            cell.alignment = align_right
                            cell.number_format = "0"
                        elif num.is_integer():
                            cell.value = int(num)
                            cell.alignment = align_right
                            cell.number_format = "#,##0"
                        else:
                            cell.value = round(num, 1)
                            cell.alignment = align_right
                            cell.number_format = "0.0"

                    cell.font = font_bold if is_summary_row else font_regular
                    cell.border = thin_border
                    if is_summary_row:
                        cell.fill = fill_subtotal
                curr_r += 1

            # Tambahkan catatan di bawah tabel matriks
            ws_mat.cell(row=curr_r, column=1, value="* Catatan: Sel dengan arsir hitam (kosong tanpa angka) menandakan alat pengukur hujan (sensor) dalam kondisi RUSAK.")
            ws_mat.cell(row=curr_r, column=1).font = font_note
            curr_r += 2 # Spasi 2 baris kosong antar blok matriks

        for col in ws_mat.columns:
            col_letter = get_column_letter(col[0].column)
            if col_letter == "A":
                ws_mat.column_dimensions[col_letter].width = 16
            else:
                ws_mat.column_dimensions[col_letter].width = 10

    # ==================== SHEET 4: REKAP BULANAN SEMUA STASIUN ====================
    if cross_station_monthly is not None and not cross_station_monthly.empty:
        ws_cross = wb.create_sheet(title="Rekap Bulanan Antar Stasiun")
        ws_cross.views.sheetView[0].showGridLines = True
        
        ws_cross["A1"] = "REKAPITULASI TOTAL CURAH HUJAN BULANAN SELURUH STASIUN"
        ws_cross["A1"].font = font_title
        ws_cross["A2"] = "Akumulasi bulanan per stasiun pengamatan"
        ws_cross["A2"].font = font_subtitle

        cross_headers = ["Stasiun"] + list(cross_station_monthly.columns)
        for col_idx, h in enumerate(cross_headers, 1):
            cell = ws_cross.cell(row=4, column=col_idx, value=h)
            cell.font = font_header
            cell.fill = fill_header_teal
            cell.alignment = align_center
            cell.border = thin_border

        r_curr = 5
        for stn_idx, row_data in cross_station_monthly.iterrows():
            cell_stn = ws_cross.cell(row=r_curr, column=1, value=str(stn_idx))
            cell_stn.font = font_bold
            cell_stn.alignment = align_center
            cell_stn.border = thin_border
            
            for c_idx, val in enumerate(row_data, 2):
                cell = ws_cross.cell(row=r_curr, column=c_idx)
                if pd.isna(val):
                    cell.value = 0.0
                else:
                    cell.value = float(val)
                cell.font = font_regular
                cell.alignment = align_right
                cell.number_format = "0.0"
                cell.border = thin_border
            r_curr += 1

        # Tambahkan Baris RATA-RATA & TOTAL antar stasiun
        if len(cross_station_monthly) > 1:
            r_avg = ws_cross.cell(row=r_curr, column=1, value="RATA-RATA (mm)")
            r_avg.font = font_bold
            r_avg.fill = fill_subtotal
            r_avg.alignment = align_center
            r_avg.border = thin_border
            for c_idx, col_name in enumerate(cross_station_monthly.columns, 2):
                col_vals = pd.to_numeric(cross_station_monthly[col_name], errors='coerce').dropna()
                avg_val = round(col_vals.mean(), 1) if not col_vals.empty else 0.0
                cell = ws_cross.cell(row=r_curr, column=c_idx, value=avg_val)
                cell.font = font_bold
                cell.fill = fill_subtotal
                cell.alignment = align_right
                cell.number_format = "0.0"
                cell.border = thin_border
            r_curr += 1

            r_tot = ws_cross.cell(row=r_curr, column=1, value="TOTAL (mm)")
            r_tot.font = font_bold
            r_tot.fill = fill_subtotal
            r_tot.alignment = align_center
            r_tot.border = thin_border
            for c_idx, col_name in enumerate(cross_station_monthly.columns, 2):
                col_vals = pd.to_numeric(cross_station_monthly[col_name], errors='coerce').dropna()
                tot_val = round(col_vals.sum(), 1) if not col_vals.empty else 0.0
                cell = ws_cross.cell(row=r_curr, column=c_idx, value=tot_val)
                cell.font = font_bold
                cell.fill = fill_subtotal
                cell.alignment = align_right
                cell.number_format = "0.0"
                cell.border = thin_border
            r_curr += 1

        for col in ws_cross.columns:
            col_letter = get_column_letter(col[0].column)
            if col_letter == "A":
                ws_cross.column_dimensions[col_letter].width = 16
            else:
                ws_cross.column_dimensions[col_letter].width = 12

    # ==================== SHEET 5: PMAX TAHUNAN (ANALISIS HIDROLOGI) ====================
    if pmax_matrix is not None and not pmax_matrix.empty:
        ws_pmax = wb.create_sheet(title="Pmax Tahunan Stasiun")
        ws_pmax.views.sheetView[0].showGridLines = True
        
        ws_pmax["A1"] = "CURAH HUJAN HARIAN MAKSIMUM TAHUNAN (PMAX) SELURUH STASIUN"
        ws_pmax["A1"].font = font_title
        ws_pmax["A2"] = "Data dasar analisis frekuensi kala ulang (Gumbel & Log Pearson III)"
        ws_pmax["A2"].font = font_subtitle

        pmax_headers = ["Stasiun"] + list(pmax_matrix.columns)
        for col_idx, h in enumerate(pmax_headers, 1):
            cell = ws_pmax.cell(row=4, column=col_idx, value=h)
            cell.font = font_header
            cell.fill = fill_header_navy
            cell.alignment = align_center
            cell.border = thin_border

        r_curr = 5
        for stn_idx, row_data in pmax_matrix.iterrows():
            cell_stn = ws_pmax.cell(row=r_curr, column=1, value=str(stn_idx))
            cell_stn.font = font_bold
            cell_stn.alignment = align_center
            cell_stn.border = thin_border
            
            for c_idx, val in enumerate(row_data, 2):
                cell = ws_pmax.cell(row=r_curr, column=c_idx)
                if pd.isna(val) or str(val).strip() in ("-", ""):
                    cell.value = "-"
                    cell.alignment = align_center
                else:
                    cell.value = float(val)
                    cell.alignment = align_right
                    cell.number_format = "0.0"
                cell.font = font_regular
                cell.border = thin_border
            r_curr += 1

        # Tambahkan Baris RATA-RATA & PMAX TERTINGGI antar stasiun
        if len(pmax_matrix) > 1:
            r_avg = ws_pmax.cell(row=r_curr, column=1, value="RATA-RATA PMAX (mm)")
            r_avg.font = font_bold
            r_avg.fill = fill_subtotal
            r_avg.alignment = align_center
            r_avg.border = thin_border
            for c_idx, col_name in enumerate(pmax_matrix.columns, 2):
                col_vals = pd.to_numeric(pmax_matrix[col_name], errors='coerce').dropna()
                avg_val = round(col_vals.mean(), 1) if not col_vals.empty else 0.0
                cell = ws_pmax.cell(row=r_curr, column=c_idx, value=avg_val)
                cell.font = font_bold
                cell.fill = fill_subtotal
                cell.alignment = align_right
                cell.number_format = "0.0"
                cell.border = thin_border
            r_curr += 1

            r_max = ws_pmax.cell(row=r_curr, column=1, value="PMAX TERTINGGI (mm)")
            r_max.font = font_bold
            r_max.fill = fill_subtotal
            r_max.alignment = align_center
            r_max.border = thin_border
            for c_idx, col_name in enumerate(pmax_matrix.columns, 2):
                col_vals = pd.to_numeric(pmax_matrix[col_name], errors='coerce').dropna()
                max_val = round(col_vals.max(), 1) if not col_vals.empty else 0.0
                cell = ws_pmax.cell(row=r_curr, column=c_idx, value=max_val)
                cell.font = font_bold
                cell.fill = fill_subtotal
                cell.alignment = align_right
                cell.number_format = "0.0"
                cell.border = thin_border
            r_curr += 1

        for col in ws_pmax.columns:
            col_letter = get_column_letter(col[0].column)
            if col_letter == "A":
                ws_pmax.column_dimensions[col_letter].width = 20
            else:
                ws_pmax.column_dimensions[col_letter].width = 14

    # ==================== SHEET 6: DEBIT & CURAH HUJAN ANDALAN (METODE WEIBULL) ====================
    if weibull_data and "summary" in weibull_data and not weibull_data["summary"].empty:
        ws_wb = wb.create_sheet(title="Debit Andalan (Weibull)")
        ws_wb.views.sheetView[0].showGridLines = True
        
        ws_wb["A1"] = "ANALISIS CURAH HUJAN & DEBIT ANDALAN IRIGASI (METODE WEIBULL Q80)"
        ws_wb["A1"].font = font_title
        ws_wb["A2"] = "Rumus Probabilitas Terlampaui: P = [m / (N + 1)] x 100% | Standar Irigasi KP-01 Ditjen Pengairan PUPR"
        ws_wb["A2"].font = font_subtitle

        wb_sum = weibull_data["summary"]
        wb_headers = list(wb_sum.columns)
        
        for col_idx, h in enumerate(wb_headers, 1):
            cell = ws_wb.cell(row=4, column=col_idx, value=h)
            cell.font = font_header
            cell.fill = fill_header_teal
            cell.alignment = align_center
            cell.border = thin_border

        r_wb = 5
        for _, r_data in wb_sum.iterrows():
            is_annual = "TOTAL" in str(r_data.get("Bulan / Periode", ""))
            for c_idx, h in enumerate(wb_headers, 1):
                val = r_data[h]
                cell = ws_wb.cell(row=r_wb, column=c_idx)
                cell.border = thin_border
                if is_annual:
                    cell.font = font_bold
                    cell.fill = fill_subtotal
                else:
                    cell.font = font_regular

                if isinstance(val, (int, float)):
                    cell.value = float(val) if not isinstance(val, int) else int(val)
                    cell.alignment = align_right
                    if h == "No" or h == "Hari":
                        cell.number_format = "#,##0"
                    elif "L/detik" in h or "L/s" in h:
                        cell.number_format = "0.000"
                    elif "Koefisien" in h or "(C)" in h or "mm/hari" in h:
                        cell.number_format = "0.00"
                    elif "mm" in h:
                        cell.number_format = "0.0"
                else:
                    cell.value = str(val)
                    if h == "Bulan / Periode":
                        cell.alignment = align_left
                    else:
                        cell.alignment = align_center
            r_wb += 1

        # Tabel Ranking Tahunan
        if "annual_ranking" in weibull_data and not weibull_data["annual_ranking"].empty:
            r_wb += 2
            ws_wb.cell(row=r_wb, column=1, value="TABEL PERINGKAT & PROBABILITAS WEIBULL (DATA TAHUNAN)").font = font_bold
            r_wb += 1
            ann_rank = weibull_data["annual_ranking"]
            rank_headers = list(ann_rank.columns)
            for c_idx, h in enumerate(rank_headers, 1):
                c_cell = ws_wb.cell(row=r_wb, column=c_idx, value=h)
                c_cell.font = font_header
                c_cell.fill = fill_header_navy
                c_cell.alignment = align_center
                c_cell.border = thin_border
            r_wb += 1
            for _, r_val in ann_rank.iterrows():
                for c_idx, h in enumerate(rank_headers, 1):
                    val = r_val[h]
                    c_cell = ws_wb.cell(row=r_wb, column=c_idx)
                    c_cell.font = font_regular
                    c_cell.border = thin_border
                    if isinstance(val, (int, float)):
                        c_cell.value = float(val) if not isinstance(val, int) else int(val)
                        c_cell.alignment = align_right
                        if "P (" in h or "Nilai" in h:
                            c_cell.number_format = "0.00"
                        else:
                            c_cell.number_format = "#,##0"
                    else:
                        c_cell.value = str(val)
                        c_cell.alignment = align_center
                r_wb += 1

        # Embed Visual Charts ke Sheet 6
        try:
            crop_label = weibull_data.get("crop_type", "Padi")
            bar_img_bytes = generate_weibull_bar_chart(wb_sum, crop_label)
            if bar_img_bytes:
                img1 = OpenpyxlImage(io.BytesIO(bar_img_bytes))
                img1.width = 520
                img1.height = 250
                ws_wb.add_image(img1, "J4")

            curve_img_bytes = generate_weibull_curve_chart(weibull_data.get("annual_ranking", pd.DataFrame()))
            if curve_img_bytes:
                img2 = OpenpyxlImage(io.BytesIO(curve_img_bytes))
                img2.width = 520
                img2.height = 250
                ws_wb.add_image(img2, "J18")
        except Exception:
            pass

        for col in ws_wb.columns:
            col_letter = get_column_letter(col[0].column)
            max_len = max(len(str(cell.value or '')) for cell in col)
            ws_wb.column_dimensions[col_letter].width = max(max_len + 3, 13)

        # ==================== SHEET 7: PERINGKAT WEIBULL 12 BULAN LENGKAP ====================
        rankings_all = weibull_data.get("rankings", {})
        if rankings_all:
            ws_rk = wb.create_sheet(title="Peringkat Bulanan (Weibull)")
            ws_rk.views.sheetView[0].showGridLines = True
            ws_rk["A1"] = "TABEL PERINGKAT & PROBABILITAS METODE WEIBULL (12 BULAN LENGKAP)"
            ws_rk["A1"].font = font_title
            ws_rk["A2"] = "Rumus Probabilitas Terlampaui: P = [m / (N + 1)] x 100% | Diurutkan dari nilai terbesar ke terkecil"
            ws_rk["A2"].font = font_subtitle

            month_names_list = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
            row_cursor = 4
            max_m_rows = 12

            for bln_idx, m_name in enumerate(month_names_list):
                if bln_idx % 3 == 0 and bln_idx > 0:
                    row_cursor += max_m_rows + 3
                    max_m_rows = 0

                col_offset = (bln_idx % 3) * 5 + 1
                m_df = rankings_all.get(m_name, pd.DataFrame())
                if not m_df.empty:
                    max_m_rows = max(max_m_rows, len(m_df))

                # Header bulan
                cell_m_title = ws_rk.cell(row=row_cursor, column=col_offset, value=f"BULAN: {m_name.upper()}")
                cell_m_title.font = font_bold
                cell_m_title.fill = fill_header_navy
                cell_m_title.alignment = align_center

                sub_hdrs = ["Tahun", "CH (mm)", "m", "P (%)"]
                for h_idx, sh in enumerate(sub_hdrs):
                    c = ws_rk.cell(row=row_cursor+1, column=col_offset+h_idx, value=sh)
                    c.font = font_header
                    c.fill = fill_header_teal
                    c.alignment = align_center
                    c.border = thin_border

                if not m_df.empty:
                    for r_idx, (_, r_data) in enumerate(m_df.iterrows(), row_cursor+2):
                        c1 = ws_rk.cell(row=r_idx, column=col_offset, value=str(r_data.get("Tahun", "")))
                        c1.alignment = align_center
                        c1.border = thin_border

                        c2 = ws_rk.cell(row=r_idx, column=col_offset+1, value=float(r_data.get("Nilai", 0)))
                        c2.number_format = "0.0"
                        c2.border = thin_border

                        c3 = ws_rk.cell(row=r_idx, column=col_offset+2, value=int(r_data.get("Peringkat (m)", 0)))
                        c3.alignment = align_center
                        c3.border = thin_border

                        c4 = ws_rk.cell(row=r_idx, column=col_offset+3, value=float(r_data.get("Probabilitas P (%)", 0)))
                        c4.number_format = "0.00"
                        c4.border = thin_border

            for col in ws_rk.columns:
                col_letter = get_column_letter(col[0].column)
                ws_rk.column_dimensions[col_letter].width = 13

    wb.save(output)
    output.seek(0)
    return output


def export_to_pdf(
    df: pd.DataFrame,
    summary_df: pd.DataFrame,
    filter_info: dict = None,
    max_table_rows: int = 400,
    weibull_data: dict = None
) -> io.BytesIO:
    """Mengekspor laporan data curah hujan ke format PDF profesional (A4 Landscape)."""
    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=45
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#1E3A8A"),
        spaceAfter=3
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#4B5563"),
        spaceAfter=12
    )
    section_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#0F766E"),
        spaceBefore=8,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        "BodySmall",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10
    )
    body_bold = ParagraphStyle(
        "BodySmallBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10
    )
    meta_style = ParagraphStyle(
        "MetaText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1E293B")
    )

    story = []

    # Kop / Header Instansi jika diatur oleh user
    if filter_info and filter_info.get("instansi"):
        instansi_style = ParagraphStyle(
            "InstansiHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#0F172A"),
            spaceAfter=2
        )
        sub_instansi_style = ParagraphStyle(
            "SubInstansiHeader",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#334155"),
            spaceAfter=8
        )
        story.append(Paragraph(filter_info["instansi"].upper(), instansi_style))
        if filter_info.get("proyek"):
            story.append(Paragraph(f"Kegiatan / Lokasi: {filter_info['proyek']}", sub_instansi_style))
        story.append(Spacer(1, 4))

    # Title & Subtitle
    story.append(Paragraph("LAPORAN REKAPITULASI & ANALISIS DATA CURAH HUJAN", title_style))
    author_str = f" • Disusun Oleh: {filter_info['penyusun']}" if (filter_info and filter_info.get("penyusun")) else ""
    story.append(Paragraph(f"Dihasilkan oleh Sistem Informasi Curah Hujan{author_str} • Waktu Cetak: {datetime.datetime.now().strftime('%d %B %Y %H:%M')}", subtitle_style))

    # Filter info box
    meta_data = []
    if filter_info:
        row1 = [
            Paragraph(f"<b>Periode Waktu:</b> {filter_info.get('periode', 'Semua Data')}", meta_style),
            Paragraph(f"<b>Stasiun Terpilih:</b> {filter_info.get('stasiun', 'Semua Stasiun')}", meta_style)
        ]
        row2 = [
            Paragraph(f"<b>Kategori / Filter Nilai:</b> {filter_info.get('kategori', 'Semua Nilai')}", meta_style),
            Paragraph(f"<b>Total Baris Terfilter:</b> {len(df):,} baris data", meta_style)
        ]
        meta_data.append(row1)
        meta_data.append(row2)
    else:
        meta_data.append([
            Paragraph(f"<b>Total Data:</b> {len(df):,} baris data", meta_style),
            Paragraph(f"<b>Tanggal Ekspor:</b> {datetime.datetime.now().strftime('%d-%m-%Y')}", meta_style)
        ])

    meta_table = Table(meta_data, colWidths=[380, 380])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#F1F5F9")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # ==================== RINGKASAN STASIUN ====================
    if not summary_df.empty:
        story.append(Paragraph("1. Ringkasan Statistik Per Stasiun", section_style))
        
        sum_cols = ["Stasiun", "Total (mm)", "Rata-rata (mm)", "Maks (mm)", "Tgl Maks", "Hari Hujan", "Hari Kering", "Sensor Rusak"]
        sum_table_data = [[Paragraph(f"<b>{col}</b>", body_bold) for col in sum_cols]]
        
        for _, r in summary_df.iterrows():
            row = [
                Paragraph(str(r["Stasiun"]), body_style),
                Paragraph(f"{r['Total Curah Hujan (mm)']:,.1f}", body_style),
                Paragraph(f"{r['Rata-rata Harian (mm)']:,.2f}", body_style),
                Paragraph(f"{r['Curah Hujan Maks (mm)']:,.1f}", body_style),
                Paragraph(str(r["Tgl Hujan Maks"]), body_style),
                Paragraph(f"{r['Hari Hujan (>0 mm)']:,}", body_style),
                Paragraph(f"{r['Hari Kering (0 mm)']:,}", body_style),
                Paragraph(str(r["Sensor Rusak"]), body_style),
            ]
            sum_table_data.append(row)

        sum_table = Table(sum_table_data, colWidths=[90, 95, 95, 95, 100, 95, 95, 95])
        sum_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F766E")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ]))
        story.append(sum_table)
        story.append(Spacer(1, 12))

    # ==================== DATA DETAIL HARIAN ====================
    if not df.empty:
        story.append(Paragraph("2. Data Curah Hujan Harian Terfilter", section_style))
        
        display_df = df.head(max_table_rows)
        note_text = ""
        if len(df) > max_table_rows:
            note_text = f" <i>(Menampilkan {max_table_rows} dari total {len(df):,} baris. Gunakan ekspor Excel untuk data lengkap tanpa batas baris.)</i>"
            story.append(Paragraph(note_text, subtitle_style))

        dt_cols = ["No", "Stasiun", "Tahun", "Bulan", "Hari", "Tanggal", "Curah Hujan (mm)", "Status", "Kategori BMKG"]
        dt_table_data = [[Paragraph(f"<b>{col}</b>", body_bold) for col in dt_cols]]
        extra_pdf_styles = []

        for i, (_, r) in enumerate(display_df.iterrows(), 1):
            tgl_str = pd.to_datetime(r["Tanggal"]).strftime("%d-%m-%Y") if pd.notna(r["Tanggal"]) else "-"
            is_rusak = (str(r["Status"]) == "RUSAK")
            ch_str = "" if is_rusak else (f"{r['Curah_Hujan']:.1f}" if pd.notna(r["Curah_Hujan"]) else "-")
            row = [
                Paragraph(str(i), body_style),
                Paragraph(str(r["Stasiun"]), body_style),
                Paragraph(str(r["Tahun"]), body_style),
                Paragraph(str(r["Nama_Bulan"]), body_style),
                Paragraph(str(r["Hari"]), body_style),
                Paragraph(tgl_str, body_style),
                Paragraph(ch_str, body_style),
                Paragraph(str(r["Status"]), body_style),
                Paragraph(str(r["Kategori_BMKG"]), body_style),
            ]
            dt_table_data.append(row)
            if is_rusak:
                extra_pdf_styles.append(('BACKGROUND', (6, i), (6, i), colors.HexColor("#000000")))

        dt_table = Table(dt_table_data, colWidths=[35, 60, 48, 70, 40, 75, 95, 65, 260], repeatRows=1)
        base_styles = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]
        dt_table.setStyle(TableStyle(base_styles + extra_pdf_styles))
        story.append(dt_table)
        story.append(Spacer(1, 4))
        story.append(Paragraph("<i>* Catatan: Sel Curah Hujan dengan arsir hitam (kosong tanpa angka) menandakan alat pengukur hujan (sensor) dalam kondisi RUSAK.</i>", subtitle_style))

    # ==================== ANALISIS DEBIT ANDALAN WEIBULL (JIKA ADA) ====================
    if weibull_data and not weibull_data.get("summary", pd.DataFrame()).empty:
        wb_sum = weibull_data.get("summary")
        crop_label = weibull_data.get("crop_type", "Padi")
        crop_c = weibull_data.get("crop_coef", 0.70)
        stn_label = weibull_data.get("station", "Semua Stasiun (Rata-rata Kawasan)")
        basis_label = weibull_data.get("data_source_mode", "Seluruh Data Historis")

        story.append(PageBreak())
        story.append(Paragraph("3. Analisis Debit Andalan Irigasi (Metode Weibull Q80)", section_style))
        story.append(Paragraph(
            f"Perhitungan ketersediaan air andalan menggunakan rumus <b>Weibull: P = [m / (N + 1)] x 100%</b> sesuai standar Ditjen SDA Kementerian Pekerjaan Umum & Perumahan Rakyat (KP-01 Irigasi). "
            f"Ketersediaan air andalan dihitung dengan tingkat keandalan <b>P = 80% (Q80)</b> untuk komoditas <b>{crop_label}</b> (Koefisien C = {crop_c:.2f}) pada stasiun: <b>{stn_label}</b>.",
            subtitle_style
        ))

        # Tabel Ringkasan Bulanan
        wb_cols = ["No", "Bulan / Periode", "Hari", "R80 Hujan (mm)", "Koef (C)", "Q80 Irigasi (mm)", "Q80 (mm/hari)", "Q80 Debit (L/s/ha)"]
        wb_table_data = [[Paragraph(f"<b>{col}</b>", body_bold) for col in wb_cols]]

        for _, r in wb_sum.iterrows():
            is_tot = str(r["Bulan / Periode"]) == "TOTAL TAHUNAN"
            r_style = body_bold if is_tot else body_style
            no_str = "" if is_tot else str(int(r["No"])) if pd.notna(r["No"]) else ""
            row = [
                Paragraph(no_str, r_style),
                Paragraph(str(r["Bulan / Periode"]), r_style),
                Paragraph(str(int(r["Hari"])) if pd.notna(r["Hari"]) else "", r_style),
                Paragraph(f"{float(r['R80 Curah Hujan (mm)']):,.1f}", r_style),
                Paragraph(f"{float(r['Koefisien (C)']):,.2f}", r_style),
                Paragraph(f"{float(r['Q80 Andalan Irigasi (mm)']):,.1f}", r_style),
                Paragraph(f"{float(r['Q80 Rata-rata (mm/hari)']):,.2f}", r_style),
                Paragraph(f"{float(r['Q80 Debit Irigasi (L/detik/ha)']):,.3f}", r_style),
            ]
            wb_table_data.append(row)

        wb_pdf_table = Table(wb_table_data, colWidths=[35, 110, 50, 95, 65, 110, 105, 120])
        wb_pdf_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F766E")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor("#F8FAFC")]),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#FEF3C7")),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        story.append(wb_pdf_table)
        story.append(Spacer(1, 10))

        # Visual Charts Side-by-Side
        try:
            bar_img_bytes = generate_weibull_bar_chart(wb_sum, crop_label)
            curve_img_bytes = generate_weibull_curve_chart(weibull_data.get("annual_ranking", pd.DataFrame()))
            chart_cells = []
            if bar_img_bytes:
                chart_cells.append(ReportlabImage(io.BytesIO(bar_img_bytes), width=375, height=185))
            if curve_img_bytes:
                chart_cells.append(ReportlabImage(io.BytesIO(curve_img_bytes), width=375, height=185))

            if len(chart_cells) == 2:
                chart_table = Table([[chart_cells[0], chart_cells[1]]], colWidths=[380, 380])
                chart_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), 0),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                ]))
                story.append(chart_table)
            elif len(chart_cells) == 1:
                story.append(chart_cells[0])
        except Exception:
            pass

    doc.build(story, canvasmaker=NumberedCanvas)
    output.seek(0)
    return output


def export_weibull_to_excel(weibull_data: dict, filter_info: dict = None) -> io.BytesIO:
    """Mengekspor laporan lengkap analisis debit andalan Weibull ke format Excel (.xlsx) dengan visual grafik dan 2 sheet."""
    output = io.BytesIO()
    wb = Workbook()

    font_title = Font(name="Calibri", size=15, bold=True, color="1E3A8A")
    font_subtitle = Font(name="Calibri", size=10, italic=True, color="475569")
    font_section = Font(name="Calibri", size=11, bold=True, color="0F766E")
    font_header = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    font_bold = Font(name="Calibri", size=10, bold=True, color="1E293B")
    font_regular = Font(name="Calibri", size=10, color="1E293B")
    font_kpi_num = Font(name="Calibri", size=13, bold=True, color="1E3A8A")
    font_kpi_lbl = Font(name="Calibri", size=9, bold=True, color="64748B")

    fill_header_navy = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    fill_header_teal = PatternFill(start_color="0F766E", end_color="0F766E", fill_type="solid")
    fill_zebra = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    fill_total = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
    fill_kpi = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")

    thin_side = Side(border_style="thin", color="CBD5E1")
    thin_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
    double_bottom = Border(bottom=Side(border_style="double", color="1E3A8A"), left=thin_side, right=thin_side, top=thin_side)

    stn_name = weibull_data.get("station", "Semua Stasiun (Rata-rata Kawasan)")
    crop_name = weibull_data.get("crop_type", "Padi")
    crop_coef = weibull_data.get("crop_coef", 0.70)
    basis_name = weibull_data.get("data_source_mode", "Seluruh Data Historis")
    wb_sum = weibull_data.get("summary", pd.DataFrame())
    ann_rank = weibull_data.get("annual_ranking", pd.DataFrame())
    rankings_all = weibull_data.get("rankings", {})

    # ==================== SHEET 1: RINGKASAN WEIBULL & GRAFIK ====================
    ws1 = wb.active
    ws1.title = "Ringkasan Weibull & Grafik"
    ws1.views.sheetView[0].showGridLines = True

    # Title & Subtitle
    ws1["A1"] = "LAPORAN ANALISIS DEBIT ANDALAN IRIGASI (METODE WEIBULL Q80)"
    ws1["A1"].font = font_title
    ws1["A2"] = "Standar Perencanaan Irigasi Ditjen SDA Kementerian Pekerjaan Umum & Perumahan Rakyat (KP-01 Irigasi)"
    ws1["A2"].font = font_subtitle

    # Info parameters block
    ws1["A4"] = "Stasiun Pengamatan:"
    ws1["B4"] = str(stn_name)
    ws1["A5"] = "Komoditas Pertanian:"
    ws1["B5"] = f"{crop_name} (Koefisien C = {crop_coef:.2f})"
    ws1["A6"] = "Tingkat Keandalan:"
    ws1["B6"] = "P = 80% (Q80 Irigasi) | Rumus Weibull: P = [m / (N + 1)] x 100%"
    ws1["A7"] = "Waktu Pembuatan:"
    ws1["B7"] = datetime.datetime.now().strftime("%d %B %Y %H:%M WIB")

    for r_p in range(4, 8):
        ws1[f"A{r_p}"].font = font_bold
        ws1[f"B{r_p}"].font = font_regular

    # KPI Summary Cards in row 9-10
    tot_row = wb_sum[wb_sum["Bulan / Periode"] == "TOTAL TAHUNAN"] if not wb_sum.empty else pd.DataFrame()
    r80_tot = float(tot_row["R80 Curah Hujan (mm)"].iloc[0]) if not tot_row.empty else 0.0
    q80_tot = float(tot_row["Q80 Andalan Irigasi (mm)"].iloc[0]) if not tot_row.empty else 0.0
    q80_avg_d = float(tot_row["Q80 Rata-rata (mm/hari)"].iloc[0]) if not tot_row.empty else 0.0
    q80_spec = float(tot_row["Q80 Debit Irigasi (L/detik/ha)"].iloc[0]) if not tot_row.empty else 0.0

    kpi_defs = [
        ("B", "C", "R80 TOTAL TAHUNAN", f"{r80_tot:,.1f} mm"),
        ("D", "E", f"Q80 ANDALAN IRIGASI ({crop_name.upper()})", f"{q80_tot:,.1f} mm"),
        ("F", "G", "RATA-RATA Q80 HARIAN", f"{q80_avg_d:,.2f} mm/hari"),
        ("H", "I", "DEBIT SPESIFIK RATA-RATA", f"{q80_spec:,.3f} L/s/ha"),
    ]
    for col_s, col_e, kpi_t, kpi_v in kpi_defs:
        ws1.merge_cells(f"{col_s}9:{col_e}9")
        ws1.merge_cells(f"{col_s}10:{col_e}10")
        ws1[f"{col_s}9"] = kpi_t
        ws1[f"{col_s}9"].font = font_kpi_lbl
        ws1[f"{col_s}9"].alignment = align_center
        ws1[f"{col_s}9"].fill = fill_kpi
        ws1[f"{col_s}10"] = kpi_v
        ws1[f"{col_s}10"].font = font_kpi_num
        ws1[f"{col_s}10"].alignment = align_center
        ws1[f"{col_s}10"].fill = fill_kpi
        for col_x in [col_s, col_e]:
            ws1[f"{col_x}9"].border = thin_border
            ws1[f"{col_x}10"].border = thin_border

    # Monthly Summary Table (Row 12 onward)
    ws1["A12"] = "1. Tabel Curah Hujan R80 & Debit Andalan Q80 Bulanan"
    ws1["A12"].font = font_section

    headers_wb = [
        "No", "Bulan / Periode", "Hari", "R80 Curah Hujan (mm)",
        "Koefisien (C)", "Q80 Andalan Irigasi (mm)", "Q80 Rata-rata (mm/hari)",
        "Q80 Debit Irigasi (L/detik/ha)"
    ]
    for col_idx, h in enumerate(headers_wb, 1):
        cell = ws1.cell(row=13, column=col_idx, value=h)
        cell.font = font_header
        cell.fill = fill_header_teal
        cell.alignment = align_center
        cell.border = thin_border

    cur_row = 14
    if not wb_sum.empty:
        for _, r_data in wb_sum.iterrows():
            is_tot = str(r_data["Bulan / Periode"]) == "TOTAL TAHUNAN"
            f_use = font_bold if is_tot else font_regular
            fill_use = fill_total if is_tot else (fill_zebra if cur_row % 2 == 0 else PatternFill(fill_type=None))
            border_use = double_bottom if is_tot else thin_border

            for c_idx, h in enumerate(headers_wb, 1):
                val = r_data.get(h, "")
                cell = ws1.cell(row=cur_row, column=c_idx)
                cell.font = f_use
                cell.fill = fill_use
                cell.border = border_use

                if h == "No":
                    cell.value = "" if is_tot else (int(val) if pd.notna(val) else "")
                    cell.alignment = align_center
                elif h == "Bulan / Periode":
                    cell.value = str(val)
                    cell.alignment = align_center if not is_tot else align_left
                elif h == "Hari":
                    cell.value = int(val) if pd.notna(val) else ""
                    cell.alignment = align_center
                elif h in ["R80 Curah Hujan (mm)", "Q80 Andalan Irigasi (mm)"]:
                    cell.value = float(val) if pd.notna(val) else 0.0
                    cell.number_format = "#,##0.0"
                    cell.alignment = align_right
                elif h == "Koefisien (C)":
                    cell.value = float(val) if pd.notna(val) else 0.0
                    cell.number_format = "0.00"
                    cell.alignment = align_center
                elif h == "Q80 Rata-rata (mm/hari)":
                    cell.value = float(val) if pd.notna(val) else 0.0
                    cell.number_format = "0.00"
                    cell.alignment = align_right
                elif h == "Q80 Debit Irigasi (L/detik/ha)":
                    cell.value = float(val) if pd.notna(val) else 0.0
                    cell.number_format = "0.000"
                    cell.alignment = align_right
            cur_row += 1

    # Annual Ranking Table under Monthly Summary Table
    cur_row += 2
    ws1.cell(row=cur_row, column=1, value="2. Peringkat Curah Hujan Tahunan (Data Kurva Durasi Weibull)").font = font_section
    cur_row += 1

    rank_headers = ["Tahun", "Nilai", "Peringkat (m)", "Probabilitas P (%)"]
    rank_labels = ["Tahun", "Curah Hujan Tahunan (mm)", "Peringkat (m)", "Probabilitas P (%) = [m/(N+1)]*100"]
    for c_idx, lbl in enumerate(rank_labels, 1):
        cell = ws1.cell(row=cur_row, column=c_idx, value=lbl)
        cell.font = font_header
        cell.fill = fill_header_navy
        cell.alignment = align_center
        cell.border = thin_border
    cur_row += 1

    if not ann_rank.empty:
        for _, r_val in ann_rank.iterrows():
            for c_idx, h in enumerate(rank_headers, 1):
                val = r_val.get(h, "")
                cell = ws1.cell(row=cur_row, column=c_idx)
                cell.font = font_regular
                cell.border = thin_border
                if c_idx == 1:
                    cell.value = str(val)
                    cell.alignment = align_center
                elif c_idx == 2:
                    cell.value = float(val) if pd.notna(val) else 0.0
                    cell.number_format = "#,##0.0"
                    cell.alignment = align_right
                elif c_idx == 3:
                    cell.value = int(val) if pd.notna(val) else 0
                    cell.alignment = align_center
                elif c_idx == 4:
                    cell.value = float(val) if pd.notna(val) else 0.0
                    cell.number_format = "0.00"
                    cell.alignment = align_right
            cur_row += 1

    # Embed Visual Charts in Sheet 1
    try:
        bar_bytes = generate_weibull_bar_chart(wb_sum, crop_name)
        if bar_bytes:
            img1 = OpenpyxlImage(io.BytesIO(bar_bytes))
            img1.width = 520
            img1.height = 250
            ws1.add_image(img1, "J4")

        curve_bytes = generate_weibull_curve_chart(ann_rank)
        if curve_bytes:
            img2 = OpenpyxlImage(io.BytesIO(curve_bytes))
            img2.width = 520
            img2.height = 250
            ws1.add_image(img2, "J18")
    except Exception:
        pass

    for col in ws1.columns:
        col_letter = get_column_letter(col[0].column)
        if col_letter <= 'I':
            max_len = max(len(str(cell.value or '')) for cell in col)
            ws1.column_dimensions[col_letter].width = max(max_len + 3, 13)

    # ==================== SHEET 2: PERINGKAT 12 BULAN LENGKAP ====================
    if rankings_all:
        ws2 = wb.create_sheet(title="Peringkat 12 Bulan Lengkap")
        ws2.views.sheetView[0].showGridLines = True
        ws2["A1"] = "TABEL PERINGKAT & PROBABILITAS METODE WEIBULL (12 BULAN LENGKAP)"
        ws2["A1"].font = font_title
        ws2["A2"] = "Rumus Probabilitas Terlampaui: P = [m / (N + 1)] x 100% | Diurutkan dari nilai terbesar ke terkecil"
        ws2["A2"].font = font_subtitle

        month_names_list = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
        row_cursor = 4
        max_m_rows = 12

        for bln_idx, m_name in enumerate(month_names_list):
            if bln_idx % 3 == 0 and bln_idx > 0:
                row_cursor += max_m_rows + 3
                max_m_rows = 0

            col_offset = (bln_idx % 3) * 5 + 1
            m_df = rankings_all.get(m_name, pd.DataFrame())
            if not m_df.empty:
                max_m_rows = max(max_m_rows, len(m_df))

            # Header bulan
            cell_m_title = ws2.cell(row=row_cursor, column=col_offset, value=f"BULAN: {m_name.upper()}")
            cell_m_title.font = font_bold
            cell_m_title.fill = fill_header_navy
            cell_m_title.alignment = align_center

            sub_hdrs = ["Tahun", "CH (mm)", "m", "P (%)"]
            for h_idx, sh in enumerate(sub_hdrs):
                c = ws2.cell(row=row_cursor+1, column=col_offset+h_idx, value=sh)
                c.font = font_header
                c.fill = fill_header_teal
                c.alignment = align_center
                c.border = thin_border

            if not m_df.empty:
                for r_idx, (_, r_data) in enumerate(m_df.iterrows(), row_cursor+2):
                    c1 = ws2.cell(row=r_idx, column=col_offset, value=str(r_data.get("Tahun", "")))
                    c1.alignment = align_center
                    c1.border = thin_border

                    c2 = ws2.cell(row=r_idx, column=col_offset+1, value=float(r_data.get("Nilai", 0)))
                    c2.number_format = "0.0"
                    c2.border = thin_border

                    c3 = ws2.cell(row=r_idx, column=col_offset+2, value=int(r_data.get("Peringkat (m)", 0)))
                    c3.alignment = align_center
                    c3.border = thin_border

                    c4 = ws2.cell(row=r_idx, column=col_offset+3, value=float(r_data.get("Probabilitas P (%)", 0)))
                    c4.number_format = "0.00"
                    c4.border = thin_border

        for col in ws2.columns:
            col_letter = get_column_letter(col[0].column)
            ws2.column_dimensions[col_letter].width = 13

    wb.save(output)
    output.seek(0)
    return output


def export_weibull_to_pdf(weibull_data: dict, filter_info: dict = None) -> io.BytesIO:
    """Mengekspor laporan khusus analisis debit andalan Weibull ke format PDF profesional (A4 Landscape) lengkap dengan visual grafik."""
    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "WbTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        textColor=colors.HexColor("#1E3A8A"),
        spaceAfter=3
    )
    subtitle_style = ParagraphStyle(
        "WbSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#4B5563"),
        spaceAfter=10
    )
    section_style = ParagraphStyle(
        "WbSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#0F766E"),
        spaceBefore=8,
        spaceAfter=5
    )
    body_style = ParagraphStyle(
        "WbBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10
    )
    body_bold = ParagraphStyle(
        "WbBodyBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10
    )
    meta_style = ParagraphStyle(
        "WbMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1E293B")
    )
    meta_bold = ParagraphStyle(
        "WbMetaBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1E293B")
    )

    story = []

    stn_label = weibull_data.get("station", "Semua Stasiun (Rata-rata Kawasan)")
    crop_label = weibull_data.get("crop_type", "Padi")
    crop_c = weibull_data.get("crop_coef", 0.70)
    basis_label = weibull_data.get("data_source_mode", "Seluruh Data Historis")
    wb_sum = weibull_data.get("summary", pd.DataFrame())
    ann_rank = weibull_data.get("annual_ranking", pd.DataFrame())
    rankings_all = weibull_data.get("rankings", {})

    # Header / Title
    story.append(Paragraph("LAPORAN ANALISIS DEBIT ANDALAN IRIGASI (METODE WEIBULL Q80)", title_style))
    story.append(Paragraph(
        f"Standar Perencanaan Irigasi Ditjen SDA Kementerian Pekerjaan Umum & Perumahan Rakyat (KP-01 Irigasi) & SNI Hidrologi • Dicetak: {datetime.datetime.now().strftime('%d %B %Y %H:%M WIB')}",
        subtitle_style
    ))

    # Meta Info Table
    meta_cells = [
        [
            Paragraph(f"<b>Stasiun Pengamatan:</b> {stn_label}", meta_style),
            Paragraph(f"<b>Tingkat Keandalan:</b> P = 80% (Q80 Irigasi & Pertanian)", meta_style)
        ],
        [
            Paragraph(f"<b>Komoditas Tanaman:</b> {crop_label} (Koefisien C = {crop_c:.2f})", meta_style),
            Paragraph(f"<b>Metode & Rumus:</b> Weibull: P = [m / (N + 1)] x 100%", meta_style)
        ],
        [
            Paragraph(f"<b>Basis Data Waktu:</b> {basis_label}", meta_style),
            Paragraph(f"<b>Status Sistem:</b> Terverifikasi Standar KP-01 Ditjen SDA", meta_style)
        ]
    ]
    meta_t = Table(meta_cells, colWidths=[380, 380])
    meta_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(meta_t)
    story.append(Spacer(1, 8))

    # KPI Metric Cards
    tot_row = wb_sum[wb_sum["Bulan / Periode"] == "TOTAL TAHUNAN"] if not wb_sum.empty else pd.DataFrame()
    r80_tot = float(tot_row["R80 Curah Hujan (mm)"].iloc[0]) if not tot_row.empty else 0.0
    q80_tot = float(tot_row["Q80 Andalan Irigasi (mm)"].iloc[0]) if not tot_row.empty else 0.0
    q80_avg_d = float(tot_row["Q80 Rata-rata (mm/hari)"].iloc[0]) if not tot_row.empty else 0.0
    q80_spec = float(tot_row["Q80 Debit Irigasi (L/detik/ha)"].iloc[0]) if not tot_row.empty else 0.0

    kpi_card_data = [
        [
            Paragraph("<font size=7 color='#64748B'><b>CURAH HUJAN R80 TAHUNAN</b></font>", body_style),
            Paragraph(f"<font size=7 color='#64748B'><b>DEBIT ANDALAN Q80 ({crop_label.upper()})</b></font>", body_style),
            Paragraph("<font size=7 color='#64748B'><b>RATA-RATA Q80 BULANAN</b></font>", body_style),
            Paragraph("<font size=7 color='#64748B'><b>DEBIT SPESIFIK RATA-RATA</b></font>", body_style),
        ],
        [
            Paragraph(f"<font size=12 color='#1E3A8A'><b>{r80_tot:,.1f} mm</b></font>", body_style),
            Paragraph(f"<font size=12 color='#0F766E'><b>{q80_tot:,.1f} mm</b></font>", body_style),
            Paragraph(f"<font size=12 color='#1E3A8A'><b>{q80_avg_d:,.2f} mm/hari</b></font>", body_style),
            Paragraph(f"<font size=12 color='#0F766E'><b>{q80_spec:,.3f} L/s/ha</b></font>", body_style),
        ]
    ]
    kpi_table = Table(kpi_card_data, colWidths=[190, 190, 190, 190])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 8))

    # Section 1: Monthly Summary Table
    story.append(Paragraph("1. Tabel Curah Hujan R80 & Debit Andalan Q80 Bulanan", section_style))
    wb_cols = ["No", "Bulan / Periode", "Hari", "R80 Hujan (mm)", "Koef (C)", "Q80 Irigasi (mm)", "Q80 (mm/hari)", "Q80 Debit (L/s/ha)"]
    wb_table_data = [[Paragraph(f"<b>{col}</b>", body_bold) for col in wb_cols]]

    if not wb_sum.empty:
        for _, r in wb_sum.iterrows():
            is_tot = str(r["Bulan / Periode"]) == "TOTAL TAHUNAN"
            r_style = body_bold if is_tot else body_style
            no_str = "" if is_tot else str(int(r["No"])) if pd.notna(r["No"]) else ""
            row = [
                Paragraph(no_str, r_style),
                Paragraph(str(r["Bulan / Periode"]), r_style),
                Paragraph(str(int(r["Hari"])) if pd.notna(r["Hari"]) else "", r_style),
                Paragraph(f"{float(r['R80 Curah Hujan (mm)']):,.1f}", r_style),
                Paragraph(f"{float(r['Koefisien (C)']):,.2f}", r_style),
                Paragraph(f"{float(r['Q80 Andalan Irigasi (mm)']):,.1f}", r_style),
                Paragraph(f"{float(r['Q80 Rata-rata (mm/hari)']):,.2f}", r_style),
                Paragraph(f"{float(r['Q80 Debit Irigasi (L/detik/ha)']):,.3f}", r_style),
            ]
            wb_table_data.append(row)

    wb_pdf_table = Table(wb_table_data, colWidths=[35, 115, 50, 95, 65, 110, 105, 120])
    wb_pdf_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F766E")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor("#F8FAFC")]),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#FEF3C7")),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(wb_pdf_table)
    story.append(Spacer(1, 8))

    # Side-by-Side Visual Charts
    try:
        bar_img_bytes = generate_weibull_bar_chart(wb_sum, crop_label)
        curve_img_bytes = generate_weibull_curve_chart(ann_rank)
        chart_cells = []
        if bar_img_bytes:
            chart_cells.append(ReportlabImage(io.BytesIO(bar_img_bytes), width=375, height=175))
        if curve_img_bytes:
            chart_cells.append(ReportlabImage(io.BytesIO(curve_img_bytes), width=375, height=175))

        if len(chart_cells) == 2:
            chart_table = Table([[chart_cells[0], chart_cells[1]]], colWidths=[380, 380])
            chart_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            story.append(chart_table)
        elif len(chart_cells) == 1:
            story.append(chart_cells[0])
    except Exception:
        pass

    # ==================== PAGE 2: EVIDENCE PERHITUNGAN & PERINGKAT WEIBULL ====================
    if not ann_rank.empty or rankings_all:
        story.append(PageBreak())
        story.append(Paragraph("2. Rincian Peringkat Probabilitas Weibull (Evidence Perhitungan Lengkap)", section_style))
        story.append(Paragraph(
            "Rumus Probabilitas Terlampaui Weibull: <b>P = [m / (N + 1)] x 100%</b>. "
            "Data curah hujan tahunan dan bulanan diurutkan secara menurun dari nilai terbesar ke terkecil (m = ranking ke-m, N = jumlah tahun pengamatan). "
            "Titik keandalan <b>P = 80% (Q80)</b> diinterpolasi secara linear antar peringkat.",
            subtitle_style
        ))

        # A. Tabel Curah Hujan Tahunan
        if not ann_rank.empty:
            story.append(Paragraph("<b>A. Tabel Peringkat Curah Hujan Tahunan (Dasar Kurva Durasi Weibull)</b>", body_bold))
            story.append(Spacer(1, 3))
            
            ann_cols = ["Tahun", "Curah Hujan Tahunan (mm)", "Peringkat (m)", "Probabilitas Terlampaui P (%) = [m / (N + 1)] x 100%"]
            ann_table_data = [[Paragraph(f"<b>{col}</b>", body_bold) for col in ann_cols]]
            
            for _, r_a in ann_rank.iterrows():
                row_a = [
                    Paragraph(str(r_a["Tahun"]), body_style),
                    Paragraph(f"{float(r_a['Nilai']):,.1f}", body_style),
                    Paragraph(str(int(r_a["Peringkat (m)"])), body_style),
                    Paragraph(f"{float(r_a['Probabilitas P (%)']):,.2f} %", body_style),
                ]
                ann_table_data.append(row_a)

            ann_pdf_t = Table(ann_table_data, colWidths=[90, 180, 110, 380])
            ann_pdf_t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ('TOPPADDING', (0, 0), (-1, -1), 2.5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))
            story.append(ann_pdf_t)
            story.append(Spacer(1, 10))

        # B. Tabel Peringkat Bulanan (12 Bulan Lengkap dalam 4 Triwulan)
        if rankings_all:
            story.append(Paragraph("<b>B. Tabel Peringkat Curah Hujan Bulanan (12 Bulan Lengkap)</b>", body_bold))
            story.append(Spacer(1, 3))

            quarters = [
                ("TRIWULAN I (Januari - Maret)", ["Januari", "Februari", "Maret"]),
                ("TRIWULAN II (April - Juni)", ["April", "Mei", "Juni"]),
                ("TRIWULAN III (Juli - September)", ["Juli", "Agustus", "September"]),
                ("TRIWULAN IV (Oktober - Desember)", ["Oktober", "November", "Desember"]),
            ]

            for q_title, q_months in quarters:
                q_cells = []
                max_q_len = max([len(rankings_all.get(m, [])) for m in q_months] or [0])
                if max_q_len == 0:
                    continue

                # Header Triwulan
                h_top = []
                for m in q_months:
                    h_top.append(Paragraph(f"<b>{m.upper()}</b>", body_bold))
                    h_top.extend([Paragraph("", body_style)] * 3)

                sub_h = []
                for _ in q_months:
                    sub_h.extend([
                        Paragraph("<b>Thn</b>", body_bold),
                        Paragraph("<b>CH(mm)</b>", body_bold),
                        Paragraph("<b>m</b>", body_bold),
                        Paragraph("<b>P(%)</b>", body_bold)
                    ])

                q_table_data = [h_top, sub_h]

                for row_i in range(max_q_len):
                    data_row = []
                    for m in q_months:
                        m_df = rankings_all.get(m, pd.DataFrame())
                        if row_i < len(m_df):
                            item = m_df.iloc[row_i]
                            data_row.extend([
                                Paragraph(str(item.get("Tahun", "")), body_style),
                                Paragraph(f"{float(item.get('Nilai', 0)):.1f}", body_style),
                                Paragraph(str(int(item.get("Peringkat (m)", 0))), body_style),
                                Paragraph(f"{float(item.get('Probabilitas P (%)', 0)):.1f}", body_style),
                            ])
                        else:
                            data_row.extend([Paragraph("-", body_style)] * 4)
                    q_table_data.append(data_row)

                # Col widths: 12 cols, each ~63 pt = 756 pt
                c_widths = [55, 68, 55, 75] * 3
                q_table = Table(q_table_data, colWidths=c_widths)
                t_style = [
                    ('SPAN', (0, 0), (3, 0)),
                    ('SPAN', (4, 0), (7, 0)),
                    ('SPAN', (8, 0), (11, 0)),
                    ('BACKGROUND', (0, 0), (3, 0), colors.HexColor("#1E3A8A")),
                    ('BACKGROUND', (4, 0), (7, 0), colors.HexColor("#0F766E")),
                    ('BACKGROUND', (8, 0), (11, 0), colors.HexColor("#1E3A8A")),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#E2E8F0")),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ('ROWBACKGROUNDS', (0, 2), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('TOPPADDING', (0, 0), (-1, -1), 2),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ]
                q_table.setStyle(TableStyle(t_style))
                story.append(KeepTogether([Paragraph(f"<b>{q_title}</b>", body_style), Spacer(1, 2), q_table, Spacer(1, 8)]))

    doc.build(story, canvasmaker=NumberedCanvas)
    output.seek(0)
    return output

