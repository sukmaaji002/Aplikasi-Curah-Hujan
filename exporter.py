import io
import datetime
import re
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

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
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
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


def export_to_excel(
    df: pd.DataFrame,
    summary_df: pd.DataFrame,
    matrix_df: pd.DataFrame = None,
    filter_info: dict = None,
    all_matrices_dict: dict = None,
    cross_station_monthly: pd.DataFrame = None,
    pmax_matrix: pd.DataFrame = None
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
            ch_val = r["Curah_Hujan"] if pd.notna(r["Curah_Hujan"]) else "-"
            
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
                if c_idx in (1, 2, 3, 5, 6, 8):
                    cell.alignment = align_center
                elif c_idx == 7 and isinstance(val, (int, float)):
                    cell.alignment = align_right
                    cell.number_format = "0.0"
                else:
                    cell.alignment = align_left
            row_curr += 1

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
            vals = [
                i,
                str(r["Stasiun"]),
                float(r["Total Curah Hujan (mm)"]),
                float(r["Rata-rata Harian (mm)"]),
                float(r["Curah Hujan Maks (mm)"]),
                str(r["Tgl Hujan Maks"]),
                int(r["Hari Hujan (>0 mm)"]),
                int(r["Hari Kering (0 mm)"]),
                int(r["Sensor Rusak"]),
                int(r["Total Data Hari"])
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

        for col in ws_sum.columns:
            col_letter = get_column_letter(col[0].column)
            max_len = max(len(str(cell.value or '')) for cell in col)
            ws_sum.column_dimensions[col_letter].width = max(max_len + 3, 12)

    # ==================== SHEET 3: MATRIKS HIDROLOGI LENGKAP ====================
    # Mendukung seluruh stasiun dan seluruh tahun yang dipilih
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
        # Contoh urutan: 22a 2016, 22a 2017, 22b 2016, 22b 2017, 23 2016, 23 2017
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
            block_cell = ws_mat.cell(row=curr_r, column=1, value=f"STASIUN : {stn_name}   |   TAHUN : {yr_val}")
            block_cell.font = font_block_title
            block_cell.fill = fill_block_header
            block_cell.alignment = align_left
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
                    if pd.isna(val) or str(val).strip() in ("-", "RUSAK"):
                        # Data sensor rusak atau tanggal tidak valid ditulis strip (-)
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
                            # Sesuai permintaan: data bernilai 0 ditulis angka 0, JANGAN diubah jadi strip (-)
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

            curr_r += 2 # Spasi 2 baris kosong antar blok matriks

        for col in ws_mat.columns:
            col_letter = get_column_letter(col[0].column)
            ws_mat.column_dimensions[col_letter].width = 9

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

        for col in ws_cross.columns:
            col_letter = get_column_letter(col[0].column)
            ws_cross.column_dimensions[col_letter].width = 11

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
                if pd.isna(val):
                    cell.value = "-"
                    cell.alignment = align_center
                else:
                    cell.value = float(val)
                    cell.alignment = align_right
                    cell.number_format = "0.0"
                cell.font = font_regular
                cell.border = thin_border
            r_curr += 1

        for col in ws_pmax.columns:
            col_letter = get_column_letter(col[0].column)
            ws_pmax.column_dimensions[col_letter].width = 12

    wb.save(output)
    output.seek(0)
    return output


def export_to_pdf(
    df: pd.DataFrame,
    summary_df: pd.DataFrame,
    filter_info: dict = None,
    max_table_rows: int = 400
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

        for i, (_, r) in enumerate(display_df.iterrows(), 1):
            tgl_str = pd.to_datetime(r["Tanggal"]).strftime("%d-%m-%Y") if pd.notna(r["Tanggal"]) else "-"
            ch_str = f"{r['Curah_Hujan']:.1f}" if pd.notna(r["Curah_Hujan"]) else "-"
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

        dt_table = Table(dt_table_data, colWidths=[35, 60, 48, 70, 40, 75, 95, 65, 260], repeatRows=1)
        dt_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        story.append(dt_table)

    doc.build(story, canvasmaker=NumberedCanvas)
    output.seek(0)
    return output

