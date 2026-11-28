import openpyxl
import pandas as pd
import numpy as np
import datetime
import calendar
import os
import shutil
import csv
import io
from typing import Tuple, Dict, Any

MONTH_NAMES_ID = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember"
}

MONTH_SHORT_TO_NUM = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "mei": 5,
    "jun": 6, "jul": 7, "aug": 8, "agt": 8, "agu": 8,
    "sep": 9, "oct": 10, "okt": 10, "nov": 11, "dec": 12, "des": 12
}

def is_cell_black_fill(cell) -> bool:
    """Mendeteksi apakah sebuah sel di Excel memiliki arsir atau background hitam (menandakan alat rusak)."""
    try:
        fill = getattr(cell, 'fill', None)
        if not fill or not getattr(fill, 'fill_type', None):
            return False
        ftype = str(fill.fill_type).lower()
        if ftype not in ('solid', 'gray125', 'darkgray', 'darkgrid', 'lightdown', 'lightup'):
            return False
        fg = getattr(fill, 'fgColor', None)
        if fg:
            if getattr(fg, 'type', None) == 'theme':
                if fg.theme in (0, 1) and getattr(fg, 'tint', 0.0) <= 0.0:
                    return True
            if getattr(fg, 'type', None) == 'rgb' and fg.rgb:
                rgb_s = str(fg.rgb).upper()
                if rgb_s in ('000000', 'FF000000', '00000000', '1E293B', '0F172A', '333333'):
                    return True
            if getattr(fg, 'type', None) == 'indexed' and fg.indexed in (0, 64):
                return True
    except Exception:
        pass
    return False

def classify_bmkg(val: float, status: str) -> str:
    """Klasifikasi curah hujan harian menurut standar BMKG."""
    if status == "RUSAK":
        return "Sensor Rusak"
    if status in ("Belum Ada Data", "Kosong") or val is None or pd.isna(val):
        return "Belum Ada Data"
    if val <= 0:
        return "Berawan / Tanpa Hujan (0 mm)"
    elif val <= 5.0:
        return "Hujan Sangat Ringan (0.1 - 5 mm)"
    elif val <= 20.0:
        return "Hujan Ringan (5 - 20 mm)"
    elif val <= 50.0:
        return "Hujan Sedang (20 - 50 mm)"
    elif val <= 100.0:
        return "Hujan Lebat (50 - 100 mm)"
    elif val <= 150.0:
        return "Hujan Sangat Lebat (100 - 150 mm)"
    else:
        return "Hujan Ekstrem (> 150 mm)"

def parse_rainfall_csv(file_or_text) -> pd.DataFrame:
    """
    Membaca dan mem-parsing data curah hujan format CSV atau teks string CSV.
    Mendukung file path, BytesIO, StringIO, atau raw string.
    """
    if isinstance(file_or_text, str):
        if os.path.exists(file_or_text):
            with open(file_or_text, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        else:
            content = file_or_text
    elif hasattr(file_or_text, 'read'):
        raw = file_or_text.read()
        if isinstance(raw, bytes):
            content = raw.decode('utf-8', errors='ignore')
        else:
            content = raw
    else:
        content = str(file_or_text)

    reader = csv.reader(io.StringIO(content))
    rows = [r for r in reader if any(field.strip() for field in r)]
    records = []

    i = 0
    total_rows = len(rows)
    while i < total_rows:
        row = rows[i]
        row_str = " ".join(row).lower()
        if "stasiun" in row_str:
            # Cari tahun
            year = 2020 # default
            stn_code = "Unknown"
            
            # Cek nilai di row
            for c_idx, val in enumerate(row):
                val_clean = str(val).strip()
                if val_clean.lower() == "tahun" and c_idx + 1 < len(row):
                    try:
                        year = int(row[c_idx + 1].strip())
                    except ValueError:
                        pass
                if "stasiun" in val_clean.lower():
                    # Ambil cell berikutnya yang berisi kode
                    for next_idx in range(c_idx + 1, min(c_idx + 4, len(row))):
                        if row[next_idx].strip():
                            stn_code = row[next_idx].strip()
                            break

            # Cari baris hari 1..31 di baris-baris berikutnya
            day_start_idx = i + 1
            while day_start_idx < min(i + 6, total_rows):
                first_cell = rows[day_start_idx][0].strip() if len(rows[day_start_idx]) > 0 else ""
                if first_cell == "1":
                    break
                day_start_idx += 1

            if day_start_idx < total_rows and rows[day_start_idx][0].strip() == "1":
                # Baca baris 1 s/d 31
                curr_d_idx = day_start_idx
                while curr_d_idx < total_rows:
                    d_row = rows[curr_d_idx]
                    if not d_row:
                        break
                    day_str = d_row[0].strip()
                    try:
                        day_num = int(day_str)
                    except ValueError:
                        break
                    if day_num < 1 or day_num > 31:
                        break

                    for m in range(1, 13):
                        max_days = calendar.monthrange(year, m)[1]
                        if day_num > max_days:
                            continue

                        val_cell = d_row[m].strip() if m < len(d_row) else ""
                        status = "Normal"
                        rain_val = None

                        if not val_cell or val_cell == "-":
                            status = "Belum Ada Data"
                            rain_val = None
                        elif "RUSAK" in val_cell.upper():
                            status = "RUSAK"
                            rain_val = None
                        else:
                            try:
                                s_clean = val_cell.replace(",", ".").strip()
                                rain_val = float(s_clean)
                                status = "Normal"
                            except ValueError:
                                status = "Error"
                                rain_val = None

                        date_obj = datetime.date(year, m, day_num)
                        cat = classify_bmkg(rain_val, status)

                        records.append({
                            "Tanggal": date_obj,
                            "Tahun": year,
                            "Bulan": m,
                            "Nama_Bulan": MONTH_NAMES_ID[m],
                            "Hari": day_num,
                            "Stasiun": stn_code,
                            "Curah_Hujan": rain_val,
                            "Status": status,
                            "Kategori_BMKG": cat
                        })

                    curr_d_idx += 1
                i = curr_d_idx
            else:
                i += 1
        else:
            i += 1

    df = pd.DataFrame(records)
    if not df.empty:
        df["Tanggal"] = pd.to_datetime(df["Tanggal"])
        df.sort_values(by=["Tanggal", "Stasiun"], inplace=True)
        df.reset_index(drop=True, inplace=True)
    return df

def parse_rainfall_workbook(file_path_or_bytes) -> pd.DataFrame:
    """
    Membaca dan mem-parsing seluruh sheet dari file Excel curah hujan.
    Mendukung file path atau file-like object (BytesIO).
    """
    wb = openpyxl.load_workbook(file_path_or_bytes, data_only=True)
    records = []

    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        max_r = sheet.max_row
        
        # Cari semua blok tabel stasiun di sheet ini
        r = 1
        while r <= max_r:
            c3_val = str(sheet.cell(r, 3).value or "").strip().lower()
            if "stasiun" in c3_val:
                # Dapatkan tahun dari kolom 2 atau dari nama sheet
                raw_year = sheet.cell(r, 2).value
                year = None
                try:
                    year = int(raw_year)
                except (ValueError, TypeError):
                    # Coba ambil dari sheet_name jika ada angka tahun (misal 'CH 2020')
                    for part in sheet_name.split():
                        if part.isdigit() and len(part) == 4:
                            year = int(part)
                            break
                if not year:
                    year = 2020 # fallback

                # Dapatkan nomor stasiun
                stn_val = sheet.cell(r, 5).value or sheet.cell(r, 4).value
                station_code = str(stn_val).strip() if stn_val is not None else "Unknown"

                # Cari baris data hari 1..31
                # Format standar: r adalah baris 'Tahun', r+1 'Tgl', r+2 baris kode, r+3 adalah Hari 1
                base_day_row = r + 3
                # Verifikasi apakah cell(base_day_row, 1) bernilai 1
                if sheet.cell(base_day_row, 1).value != 1:
                    # Scan beberapa baris ke bawah untuk mencari hari 1
                    found_day1 = False
                    for offset in range(1, 6):
                        if sheet.cell(r + offset, 1).value == 1:
                            base_day_row = r + offset
                            found_day1 = True
                            break
                    if not found_day1:
                        # Lewati jika tidak ada baris hari
                        r += 1
                        continue

                # Baca 31 hari
                for day_offset in range(31):
                    curr_row = base_day_row + day_offset
                    day_num = sheet.cell(curr_row, 1).value
                    if day_num is None:
                        continue
                    try:
                        day_num = int(day_num)
                    except (ValueError, TypeError):
                        continue
                    
                    if day_num < 1 or day_num > 31:
                        continue

                    # Baca bulan 1 sampai 12 (kolom 2 s/d 13)
                    for m in range(1, 13):
                        # Cek apakah tanggal valid dalam kalender masehi
                        max_days = calendar.monthrange(year, m)[1]
                        if day_num > max_days:
                            # Hari tidak ada di kalender (misal 30 Feb, 31 Apr)
                            continue

                        cell_obj = sheet.cell(curr_row, m + 1)
                        cell_val = cell_obj.value
                        status = "Normal"
                        rain_val = None

                        # Deteksi apakah alat rusak (dari arsir/background hitam atau teks 'RUSAK')
                        is_rusak = is_cell_black_fill(cell_obj)
                        if cell_val is not None and "RUSAK" in str(cell_val).upper():
                            is_rusak = True

                        if is_rusak:
                            status = "RUSAK"
                            rain_val = None
                        elif cell_val is None:
                            status = "Belum Ada Data"
                            rain_val = None
                        elif isinstance(cell_val, (int, float)):
                            rain_val = float(cell_val)
                            status = "Normal"
                        else:
                            s = str(cell_val).strip().upper()
                            if s == "" or s == "-":
                                status = "Belum Ada Data"
                                rain_val = None
                            else:
                                # Parsing angka desimal dengan koma (format Indonesia: 3,5 -> 3.5)
                                try:
                                    s_clean = s.replace(",", ".")
                                    rain_val = float(s_clean)
                                    status = "Normal"
                                except ValueError:
                                    status = "Error"
                                    rain_val = None

                        date_obj = datetime.date(year, m, day_num)
                        cat = classify_bmkg(rain_val, status)

                        records.append({
                            "Tanggal": date_obj,
                            "Tahun": year,
                            "Bulan": m,
                            "Nama_Bulan": MONTH_NAMES_ID[m],
                            "Hari": day_num,
                            "Stasiun": station_code,
                            "Curah_Hujan": rain_val,
                            "Status": status,
                            "Kategori_BMKG": cat
                        })

                # Loncat ke baris berikutnya setelah tabel stasiun ini (~36 baris)
                r = base_day_row + 31
            else:
                r += 1

    df = pd.DataFrame(records)
    if not df.empty:
        df["Tanggal"] = pd.to_datetime(df["Tanggal"])
        df.sort_values(by=["Tanggal", "Stasiun"], inplace=True)
        df.reset_index(drop=True, inplace=True)
    return df

def get_station_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Menghasilkan ringkasan statistik per stasiun berdasarkan data yang difilter."""
    if df.empty:
        return pd.DataFrame()

    summary_list = []
    grouped = df.groupby("Stasiun")

    for stn, group in grouped:
        valid_ch = group["Curah_Hujan"].dropna()
        total_ch = valid_ch.sum()
        mean_ch = valid_ch.mean() if len(valid_ch) > 0 else 0.0
        max_ch = valid_ch.max() if len(valid_ch) > 0 else 0.0
        
        # Tanggal max hujan
        if max_ch > 0:
            max_rows = group[group["Curah_Hujan"] == max_ch]
            tgl_max = max_rows["Tanggal"].iloc[0].strftime("%d-%m-%Y") if not max_rows.empty else "-"
        else:
            tgl_max = "-"

        hari_hujan = (valid_ch > 0).sum()
        hari_kering = (valid_ch == 0).sum()
        hari_rusak = (group["Status"] == "RUSAK").sum()
        total_hari = len(group)

        summary_list.append({
            "Stasiun": stn,
            "Total Curah Hujan (mm)": round(total_ch, 1),
            "Rata-rata Harian (mm)": round(mean_ch, 2),
            "Curah Hujan Maks (mm)": round(max_ch, 1),
            "Tgl Hujan Maks": tgl_max,
            "Hari Hujan (>0 mm)": int(hari_hujan),
            "Hari Kering (0 mm)": int(hari_kering),
            "Sensor Rusak": int(hari_rusak),
            "Total Data Hari": int(total_hari)
        })

    sum_df = pd.DataFrame(summary_list)
    sum_df.sort_values(by="Total Curah Hujan (mm)", ascending=False, inplace=True)
    sum_df.reset_index(drop=True, inplace=True)
    return sum_df

def get_monthly_matrix(df: pd.DataFrame, station: str, year: int, months: list = None) -> pd.DataFrame:
    """
    Mengubah data satu stasiun dan tahun tertentu ke format matriks hidrologi
    (Baris: Tanggal 1 s/d 31, Kolom: Bulan terpilih atau Jan s/d Des).
    Dioptimalkan menggunakan pivot berkecepatan tinggi.
    """
    subset = df[(df["Stasiun"] == station) & (df["Tahun"] == year)]
    if subset.empty:
        return pd.DataFrame()

    if months is not None and len(months) > 0:
        target_months = sorted(list(months))
        subset = subset[subset["Bulan"].isin(target_months)]
    else:
        avail_m = subset["Bulan"].dropna().unique()
        target_months = sorted(list(avail_m)) if len(avail_m) > 0 else list(range(1, 13))

    if subset.empty or not target_months:
        return pd.DataFrame()

    piv = subset.pivot(index="Hari", columns="Bulan", values="Curah_Hujan")
    piv = piv.reindex(index=range(1, 32), columns=target_months)
    piv.columns = [MONTH_NAMES_ID[m][:3] for m in target_months]
    piv.index.name = "Tgl"

    # Tambahkan baris statistik hidrologi di bawah (sebelum menandai sel rusak)
    numeric_piv = piv.apply(pd.to_numeric, errors='coerce')
    has_valid_data = numeric_piv.notna().any()
    total_row = numeric_piv.sum(skipna=True, min_count=1)
    mean_row = numeric_piv.mean(skipna=True).round(1)
    max_row = numeric_piv.max(skipna=True)
    rain_days = (numeric_piv > 0).sum(skipna=True).astype(float)
    rain_days[~has_valid_data] = np.nan

    summary_rows = pd.DataFrame([total_row, mean_row, max_row, rain_days],
                                index=["JUMLAH", "RATA-RATA", "MAKSIMUM", "HARI HUJAN"])

    # Ubah piv ke dtype object agar dapat menampung string penanda "RUSAK"
    piv = piv.astype(object)

    # Tandai tanggal di mana alat pengukur rusak dengan nilai "RUSAK"
    rusak_subset = subset[subset["Status"] == "RUSAK"]
    for _, r_rk in rusak_subset.iterrows():
        try:
            d_val = int(r_rk["Hari"])
            m_val = int(r_rk["Bulan"])
            if m_val in target_months and d_val in piv.index:
                m_col = MONTH_NAMES_ID[m_val][:3]
                piv.loc[d_val, m_col] = "RUSAK"
        except Exception:
            pass

    # Tandai tanggal di mana data belum ada / belum diisi dengan "-"
    kosong_subset = subset[subset["Status"].isin(["Belum Ada Data", "Kosong"])]
    for _, r_ks in kosong_subset.iterrows():
        try:
            d_val = int(r_ks["Hari"])
            m_val = int(r_ks["Bulan"])
            if m_val in target_months and d_val in piv.index:
                m_col = MONTH_NAMES_ID[m_val][:3]
                piv.loc[d_val, m_col] = "-"
        except Exception:
            pass

    full_table = pd.concat([piv, summary_rows])
    return full_table

def get_cross_station_monthly_matrix(df: pd.DataFrame, year: int = None, months: list = None) -> pd.DataFrame:
    """
    Menghasilkan matriks rekapitulasi seluruh stasiun (Baris: Stasiun, Kolom: Bulan terpilih + Total).
    Jika year diberikan, memfilter tahun tertentu. Jika None, menjumlahkan seluruh tahun.
    """
    sub = df if year is None else df[df["Tahun"] == year]
    if sub.empty:
        return pd.DataFrame()

    if months is not None and len(months) > 0:
        target_months = sorted(list(months))
        sub = sub[sub["Bulan"].isin(target_months)]
    else:
        avail_m = sub["Bulan"].dropna().unique()
        target_months = sorted(list(avail_m)) if len(avail_m) > 0 else list(range(1, 13))

    if sub.empty or not target_months:
        return pd.DataFrame()

    piv = sub.groupby(["Stasiun", "Bulan"])["Curah_Hujan"].sum(min_count=1).unstack(level="Bulan")
    piv = piv.reindex(columns=target_months)
    piv.columns = [MONTH_NAMES_ID[m][:3] for m in target_months]
    piv["TOTAL (mm)"] = piv.sum(axis=1, min_count=1).round(1)
    return piv.round(1)

def get_pmax_cross_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """
    Menghasilkan matriks Pmax harian (Curah Hujan Maksimum Tahunan)
    seluruh stasiun untuk setiap tahun (Baris: Stasiun, Kolom: 2015..2026 + Rata-rata + Maks).
    """
    valid = df[df["Curah_Hujan"].notna()]
    if valid.empty:
        return pd.DataFrame()

    pmax = valid.groupby(["Stasiun", "Tahun"])["Curah_Hujan"].max().unstack(level="Tahun")
    pmax.columns = [str(col) for col in pmax.columns]
    pmax["RATA-RATA (mm)"] = pmax.mean(axis=1).round(1)
    pmax["MAKS TERTINGGI (mm)"] = pmax.max(axis=1).round(1)
    return pmax.round(1)


# ==============================================================================
# FUNGSI MANIPULASI DATA MANUAL (TAMBAH / UPDATE / HAPUS)
# ==============================================================================

def add_or_update_rainfall_record(
    df_main: pd.DataFrame,
    station: str,
    date_val: datetime.date,
    rain_val: float = None,
    status: str = "Normal"
) -> pd.DataFrame:
    """
    Menambah record curah hujan baru atau memperbarui data yang sudah ada
    berdasarkan stasiun dan tanggal.
    """
    df_copy = df_main.copy()
    dt = pd.to_datetime(date_val)
    stn_clean = str(station).strip()
    
    # Normalisasi nilai hujan & status
    if status == "RUSAK":
        val_final = None
        status_final = "RUSAK"
    else:
        status_final = "Normal"
        if rain_val is None or pd.isna(rain_val):
            raise ValueError("Isi curah hujan terukur, atau tandai alat RUSAK.")
        val_final = float(rain_val)

    cat = classify_bmkg(val_final, status_final)

    # Cek apakah record sudah ada
    mask = (
        (df_copy["Stasiun"].astype(str).str.strip().str.lower() == stn_clean.lower()) & 
        (pd.to_datetime(df_copy["Tanggal"]).dt.date == dt.date())
    )

    new_row = pd.DataFrame([{
        "Tanggal": dt,
        "Tahun": int(dt.year),
        "Bulan": int(dt.month),
        "Nama_Bulan": MONTH_NAMES_ID[dt.month],
        "Hari": int(dt.day),
        "Stasiun": stn_clean,
        "Curah_Hujan": val_final,
        "Status": status_final,
        "Kategori_BMKG": cat
    }]).astype({"Curah_Hujan": "float64"})

    if mask.any():
        df_copy = df_copy[~mask]

    df_updated = pd.concat([df_copy, new_row], ignore_index=True)
    df_updated.sort_values(by=["Tanggal", "Stasiun"], inplace=True)
    df_updated.reset_index(drop=True, inplace=True)

    # Catat ke log manual_records.csv
    log_manual_entry(stn_clean, dt.date(), val_final, status_final, cat, "UPDATE" if mask.any() else "INSERT")

    return df_updated


def rainfall_entry(value, status):
    """Normalize the three entry states without turning missing data into a zero."""
    if status == "RUSAK":
        return None, "RUSAK"
    if value is None or pd.isna(value):
        return None, "Belum Ada Data"
    return float(value), "Normal"


def save_bulk_monthly_records(
    df_main: pd.DataFrame,
    station: str,
    year: int,
    month: int,
    daily_items: list
) -> pd.DataFrame:
    """Update only changed station-days; return the original frame for a no-op."""
    stn_clean = str(station).strip()
    station_matches = df_main["Stasiun"].astype(str).str.strip().str.lower() == stn_clean.lower()
    dates = pd.to_datetime(df_main["Tanggal"]).dt.normalize()
    month_matches = station_matches & (dates.dt.year == year) & (dates.dt.month == month)
    # Retain the stored spelling of an existing station.
    known_stations = df_main.loc[station_matches, "Stasiun"]
    if not known_stations.empty:
        stn_clean = known_stations.iloc[0]
    existing = {
        date.day: rainfall_entry(row.Curah_Hujan, row.Status)
        for date, row in zip(dates[month_matches], df_main.loc[month_matches].itertuples())
    }

    updates = {}
    for item in daily_items:
        day = int(item["Hari"])
        try:
            date = pd.Timestamp(datetime.date(year, month, day))
        except ValueError:
            continue
        value, status = rainfall_entry(item.get("Curah_Hujan"), item.get("Status"))
        if (value, status) == existing.get(day, (None, "Belum Ada Data")):
            updates.pop(date, None)
            continue
        updates[date] = {
            "Tanggal": date,
            "Tahun": year,
            "Bulan": month,
            "Nama_Bulan": MONTH_NAMES_ID[month],
            "Hari": day,
            "Stasiun": stn_clean,
            "Curah_Hujan": value,
            "Status": status,
            "Kategori_BMKG": classify_bmkg(value, status),
        }

    if not updates:
        return df_main

    replace = station_matches & dates.isin(updates)
    changed = pd.DataFrame(updates.values()).astype({"Curah_Hujan": "float64"})
    result = pd.concat([df_main.loc[~replace], changed], ignore_index=True)
    result.sort_values(by=["Tanggal", "Stasiun"], inplace=True, ignore_index=True)
    log_manual_entry(stn_clean, f"{year}-{month:02d}", f"{len(updates)} hari", "BULK", "-", "BULK_UPDATE")
    return result


def delete_rainfall_record(
    df_main: pd.DataFrame,
    station: str,
    date_val: datetime.date
) -> pd.DataFrame:
    """Menghapus record curah hujan untuk stasiun dan tanggal tertentu."""
    df_copy = df_main.copy()
    stn_clean = str(station).strip()
    dt = pd.to_datetime(date_val)

    mask = (
        (df_copy["Stasiun"].astype(str).str.strip().str.lower() == stn_clean.lower()) &
        (pd.to_datetime(df_copy["Tanggal"]).dt.date == dt.date())
    )

    if mask.any():
        df_copy = df_copy[~mask]
        df_copy.sort_values(by=["Tanggal", "Stasiun"], inplace=True)
        df_copy.reset_index(drop=True, inplace=True)
        log_manual_entry(stn_clean, dt.date(), None, "DELETED", "-", "DELETE")

    return df_copy


def log_manual_entry(stn, date_or_period, val, status, cat, action):
    """Menyimpan catatan riwayat penambahan data ke file CSV audit trail."""
    log_file = "manual_records_log.csv"
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = not os.path.exists(log_file)
    row_df = pd.DataFrame([{
        "Waktu_Input": timestamp,
        "Aksi": action,
        "Stasiun": stn,
        "Tanggal_Periode": str(date_or_period),
        "Curah_Hujan": str(val),
        "Status": status,
        "Kategori": cat
    }])
    row_df.to_csv(log_file, mode="a", header=header, index=False)


def persist_dataframe(df: pd.DataFrame, parquet_path: str = "data_curah_hujan.parquet") -> bool:
    """Menyimpan dataframe secara permanen ke file Parquet di disk dengan backup otomatis."""
    try:
        # Otomatis buat cadangan (backup) jika file lama sudah ada
        if os.path.exists(parquet_path):
            backup_path = parquet_path.replace(".parquet", "_backup.parquet")
            try:
                shutil.copy2(parquet_path, backup_path)
            except Exception:
                pass
        df.to_parquet(parquet_path, index=False)
        return True
    except Exception as e:
        print(f"Error menyimpan file parquet: {e}")
        return False



