import re
import pandas as pd
import numpy as np

# Standard Normal Quantiles (Z) for Return Periods T = 2, 5, 10, 25, 50, 100
Z_LOOKUP = {
    2: 0.0,
    5: 0.8416,
    10: 1.2816,
    25: 1.7507,
    50: 2.0537,
    100: 2.3263
}

# Standard Gumbel Reduced Mean (Yn) & Reduced Standard Deviation (Sn) lookup for n=10..30
GUMBEL_TABLE = {
    10: (0.4952, 0.9496),
    11: (0.5035, 0.9676),
    12: (0.5094, 0.9833),
    13: (0.5147, 0.9971),
    14: (0.5193, 1.0095),
    15: (0.5236, 1.0206),
    16: (0.5274, 1.0316),
    17: (0.5309, 1.0411),
    18: (0.5341, 1.0493),
    19: (0.5371, 1.0565),
    20: (0.5399, 1.0628),
    25: (0.5521, 1.0915),
    30: (0.5600, 1.1124),
}

def get_yn_sn(n: int):
    """Mendapatkan nilai Yn dan Sn berdasarkan ukuran sampel n."""
    if n in GUMBEL_TABLE:
        return GUMBEL_TABLE[n]
    if n < 10:
        return 0.4952, 0.9496
    # Interpolasi atau asimtotik
    return 0.5772, 1.2825

def infill_missing_rainfall(
    df: pd.DataFrame,
    method: str = "neighbor_mean"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Pengisian Data Hilang / Alat Rusak (Infilling Missing Data) sesuai Standar SNI 19-6738-2002, WMO, dan KP-01 Ditjen SDA PUPR.
    
    Metode:
    - 'neighbor_mean' (Standar SNI/WMO): Mengestimasi curah hujan berdasarkan rata-rata stasiun pemantau aktif lain di kawasan pada tanggal yang sama.
    - 'prorata' (Standar KP-01 PUPR): Normalisasi rata-rata harian operasional stasiun pada bulan bersangkutan.
    - 'none': Tanpa estimasi (data observasi murni apa adanya).
    
    Returns:
        (df_infilled, log_df)
    """
    if df.empty or method == "none":
        return df.copy(), pd.DataFrame()

    df_out = df.copy()
    damaged_mask = (df_out["Status"] == "RUSAK")
    damaged_idx = df_out[damaged_mask].index

    if len(damaged_idx) == 0:
        return df_out, pd.DataFrame()

    log_rows = []

    if method in ("neighbor_mean", "auto"):
        valid_obs = df_out[df_out["Curah_Hujan"].notna()]
        date_stats = valid_obs.groupby("Tanggal")["Curah_Hujan"].agg(["mean", "count"])
        stn_month_means = valid_obs.groupby(["Stasiun", "Tahun", "Bulan"])["Curah_Hujan"].mean()

        for idx in damaged_idx:
            row = df_out.loc[idx]
            tgl = row["Tanggal"]
            stn = row["Stasiun"]
            yr = row["Tahun"]
            mo = row["Bulan"]
            hari = row.get("Hari", getattr(tgl, "day", 1))

            est_val = None
            source = ""
            ref_count = 0

            if tgl in date_stats.index and date_stats.loc[tgl, "count"] > 0:
                est_val = round(float(date_stats.loc[tgl, "mean"]), 1)
                ref_count = int(date_stats.loc[tgl, "count"])
                source = f"Rata-rata {ref_count} Stasiun Sekitar (SNI/WMO)"
            elif (stn, yr, mo) in stn_month_means.index and not np.isnan(stn_month_means.loc[(stn, yr, mo)]):
                est_val = round(float(stn_month_means.loc[(stn, yr, mo)]), 1)
                source = "Prorata Rata-rata Bulanan Stasiun (KP-01)"
            else:
                est_val = 0.0
                source = "Asumsi Tanpa Hujan (0.0 mm)"

            df_out.at[idx, "Curah_Hujan"] = est_val
            df_out.at[idx, "Status"] = "ESTIMASI"

            tgl_str = tgl.strftime("%Y-%m-%d") if hasattr(tgl, "strftime") else str(tgl)
            log_rows.append({
                "Tanggal": tgl_str,
                "Stasiun": str(stn),
                "Tahun": int(yr),
                "Bulan": int(mo),
                "Hari": int(hari),
                "Curah Hujan Estimasi (mm)": est_val,
                "Metode Estimasi": source,
                "Stasiun Rujukan": ref_count
            })

    elif method == "prorata":
        valid_obs = df_out[df_out["Curah_Hujan"].notna()]
        stn_month_means = valid_obs.groupby(["Stasiun", "Tahun", "Bulan"])["Curah_Hujan"].mean()

        for idx in damaged_idx:
            row = df_out.loc[idx]
            tgl = row["Tanggal"]
            stn = row["Stasiun"]
            yr = row["Tahun"]
            mo = row["Bulan"]
            hari = row.get("Hari", getattr(tgl, "day", 1))

            if (stn, yr, mo) in stn_month_means.index and not np.isnan(stn_month_means.loc[(stn, yr, mo)]):
                est_val = round(float(stn_month_means.loc[(stn, yr, mo)]), 1)
                source = "Prorata Rata-rata Bulanan Stasiun (KP-01)"
            else:
                est_val = 0.0
                source = "Asumsi Tanpa Hujan (0.0 mm)"

            df_out.at[idx, "Curah_Hujan"] = est_val
            df_out.at[idx, "Status"] = "ESTIMASI"

            tgl_str = tgl.strftime("%Y-%m-%d") if hasattr(tgl, "strftime") else str(tgl)
            log_rows.append({
                "Tanggal": tgl_str,
                "Stasiun": str(stn),
                "Tahun": int(yr),
                "Bulan": int(mo),
                "Hari": int(hari),
                "Curah Hujan Estimasi (mm)": est_val,
                "Metode Estimasi": source,
                "Stasiun Rujukan": 0
            })

    log_df = pd.DataFrame(log_rows)
    return df_out, log_df

def get_pmax_matrix(df: pd.DataFrame, infill_method: str = "none") -> pd.DataFrame:
    """
    Menghasilkan tabel matriks curah hujan harian maksimum tahunan (Pmax)
    untuk setiap stasiun dan setiap tahun.
    """
    work_df = df
    if infill_method != "none":
        work_df, _ = infill_missing_rainfall(df, method=infill_method)
    valid_df = work_df[work_df["Curah_Hujan"].notna()]
    if valid_df.empty:
        return pd.DataFrame()
    
    pmax = valid_df.groupby(["Stasiun", "Tahun"])["Curah_Hujan"].max().reset_index()
    pmax_pivot = pmax.pivot(index="Stasiun", columns="Tahun", values="Curah_Hujan")
    pmax_pivot.columns = [str(c) for c in pmax_pivot.columns]
    return pmax_pivot

def calculate_statistical_parameters(series: pd.Series) -> dict:
    """Menghitung parameter statistik hidrologi (Rata-rata, S, Cv, Cs, Ck)."""
    clean_s = series.dropna().values
    n = len(clean_s)
    if n < 3:
        return {}

    mean = float(np.mean(clean_s))
    std = float(np.std(clean_s, ddof=1))
    cv = std / mean if mean != 0 else 0.0

    # Skewness (Cs)
    m3 = np.sum((clean_s - mean)**3)
    cs = (n * m3) / ((n - 1) * (n - 2) * (std**3)) if std > 0 and n > 2 else 0.0

    # Kurtosis (Ck)
    m4 = np.sum((clean_s - mean)**4)
    ck = (n**2 * m4) / ((n - 1) * (n - 2) * (n - 3) * (std**4)) if std > 0 and n > 3 else 0.0

    return {
        "n": n,
        "mean": round(mean, 2),
        "std": round(std, 2),
        "cv": round(cv, 4),
        "cs": round(cs, 4),
        "ck": round(ck, 4)
    }

def calculate_gumbel(series: pd.Series, return_periods=(2, 5, 10, 25, 50, 100)) -> dict:
    """Menghitung curah hujan rancangan metode Gumbel untuk berbagai kala ulang."""
    stats_p = calculate_statistical_parameters(series)
    if not stats_p:
        return {}

    n = stats_p["n"]
    mean = stats_p["mean"]
    std = stats_p["std"]
    yn, sn = get_yn_sn(n)

    results = {}
    for T in return_periods:
        yt = -np.log(-np.log((T - 1.0) / T))
        k = (yt - yn) / sn
        xt = mean + k * std
        results[f"T_{T}"] = round(float(xt), 1)

    return results

def calculate_log_pearson_3(series: pd.Series, return_periods=(2, 5, 10, 25, 50, 100)) -> dict:
    """Menghitung curah hujan rancangan metode Log Pearson Tipe III."""
    clean_s = series.dropna()
    clean_s = clean_s[clean_s > 0].values
    if len(clean_s) < 3:
        return {}

    log_x = np.log10(clean_s)
    n = len(log_x)
    mean_log = float(np.mean(log_x))
    std_log = float(np.std(log_x, ddof=1))

    # Skewness log
    m3 = np.sum((log_x - mean_log)**3)
    cs_log = (n * m3) / ((n - 1) * (n - 2) * (std_log**3)) if std_log > 0 and n > 2 else 0.0

    results = {}
    for T in return_periods:
        prob = 1.0 / T
        # Pendekatan faktor frekuensi Kz menggunakan scipy atau Wilson-Hilferty
        # Untuk Cs log, kita gunakan aproksimasi standar Kite / Wilson-Hilferty
        z = Z_LOOKUP.get(T, 1.2816)
        if abs(cs_log) > 0.001:
            k = (2.0 / cs_log) * (((z - cs_log / 6.0) * (cs_log / 6.0) + 1.0)**3 - 1.0)
        else:
            k = z
        log_xt = mean_log + k * std_log
        xt = 10.0**log_xt
        results[f"T_{T}"] = round(float(xt), 1)

    return results

def get_station_frequency_stats(df: pd.DataFrame, station: str, infill_method: str = "none") -> tuple:
    """Mengembalikan parameter statistik hidrologi dan log pengisian data hilang untuk suatu stasiun."""
    work_df = df
    stn_log = pd.DataFrame()
    if infill_method != "none":
        work_df, infill_log = infill_missing_rainfall(df, method=infill_method)
        if not infill_log.empty:
            stn_log = infill_log[infill_log["Stasiun"] == str(station).strip()]
            
    sub = work_df[(work_df["Stasiun"] == station) & (work_df["Curah_Hujan"].notna())]
    if sub.empty:
        return {}, stn_log
    pmax_series = sub.groupby("Tahun")["Curah_Hujan"].max()
    stats = calculate_statistical_parameters(pmax_series)
    return stats, stn_log

def get_design_rainfall_summary(df: pd.DataFrame, station: str, infill_method: str = "none") -> pd.DataFrame:
    """
    Menghasilkan tabel komparasi curah hujan rancangan (Gumbel & Log Pearson III)
    untuk satu stasiun pengamatan dengan dukungan pengisian data hilang (infilling).
    """
    work_df = df
    if infill_method != "none":
        work_df, _ = infill_missing_rainfall(df, method=infill_method)

    sub = work_df[(work_df["Stasiun"] == station) & (work_df["Curah_Hujan"].notna())]
    if sub.empty:
        return pd.DataFrame()

    pmax_by_year = sub.groupby("Tahun")["Curah_Hujan"].max()
    gumbel_res = calculate_gumbel(pmax_by_year)
    lp3_res = calculate_log_pearson_3(pmax_by_year)

    periods = [2, 5, 10, 25, 50, 100]
    rows = []
    for T in periods:
        g_val = gumbel_res.get(f"T_{T}", np.nan)
        l_val = lp3_res.get(f"T_{T}", np.nan)
        diff = round(abs(g_val - l_val), 1) if pd.notna(g_val) and pd.notna(l_val) else np.nan
        rows.append({
            "Kala Ulang (T)": f"{T} Tahun",
            "Gumbel (mm)": g_val,
            "Log Pearson III (mm)": l_val,
            "Selisih (mm)": diff
        })

    return pd.DataFrame(rows)


# ==============================================================================
# PERHITUNGAN CURAH HUJAN & DEBIT ANDALAN METODE WEIBULL (IRIGASI & PERTANIAN)
# ==============================================================================

MONTH_NAMES_INDONESIA = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember"
}

DAYS_PER_MONTH = {
    1: 31, 2: 28.25, 3: 31, 4: 30, 5: 31, 6: 30,
    7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31
}

# Koefisien Pengaliran / Curah Hujan Efektif Irigasi Standar KP-01 Ditjen Pengairan PUPR
CROP_IRRIGATION_CONFIG = {
    "Padi": {
        "coef": 0.70,
        "name": "Padi Sawah (C = 0.70)",
        "desc": "Standar Perencanaan Irigasi KP-01 Ditjen Pengairan PUPR (Curah Hujan Efektif Re = 70% x R80)"
    },
    "Palawija": {
        "coef": 0.50,
        "name": "Palawija / Jagung / Kedelai (C = 0.50)",
        "desc": "Standar Perencanaan Irigasi KP-01 Ditjen Pengairan PUPR (Curah Hujan Efektif Re = 50% x R80)"
    },
    "Hortikultura": {
        "coef": 0.60,
        "name": "Hortikultura / Buah & Sayur (C = 0.60)",
        "desc": "Standar Irigasi Tanaman Hortikultura / Sayuran Semusim (Curah Hujan Efektif Re = 60% x R80)"
    }
}

def calculate_weibull_ranking(series: pd.Series) -> pd.DataFrame:
    """
    Menyusun tabel peringkat data dan probabilitas metode Weibull.
    Rumus: P = (m / (N + 1)) * 100%
    Data diurutkan dari nilai terbesar ke terkecil (descending).
    """
    clean_s = series.dropna()
    clean_s = clean_s[clean_s >= 0]
    if clean_s.empty:
        return pd.DataFrame()

    sorted_df = pd.DataFrame({
        "Tahun": clean_s.index.astype(str),
        "Nilai": clean_s.values.astype(float)
    }).sort_values(by="Nilai", ascending=False).reset_index(drop=True)

    n = len(sorted_df)
    sorted_df["Peringkat (m)"] = list(range(1, n + 1))
    sorted_df["Probabilitas P (%)"] = ((sorted_df["Peringkat (m)"] / (n + 1)) * 100.0).round(2)
    return sorted_df

def interpolate_weibull_value(ranking_df: pd.DataFrame, target_p: float = 80.0) -> float:
    """
    Interpolasi linier untuk memperoleh nilai pada probabilitas target P (%) (Default: 80% untuk Irigasi).
    m_target = (P / 100) * (N + 1)
    """
    if ranking_df.empty:
        return 0.0

    n = len(ranking_df)
    m_target = (float(target_p) / 100.0) * (n + 1)

    if m_target <= 1:
        return float(ranking_df.iloc[0]["Nilai"])
    if m_target >= n:
        return float(ranking_df.iloc[-1]["Nilai"])

    m1 = int(np.floor(m_target))
    m2 = m1 + 1

    row1 = ranking_df[ranking_df["Peringkat (m)"] == m1]
    row2 = ranking_df[ranking_df["Peringkat (m)"] == m2]
    if row1.empty or row2.empty:
        return 0.0

    val1 = float(row1.iloc[0]["Nilai"])
    val2 = float(row2.iloc[0]["Nilai"])

    fraction = m_target - m1
    interpolated = val1 + fraction * (val2 - val1)
    return max(0.0, round(interpolated, 2))

def calculate_dependable_flow_and_rainfall(
    df: pd.DataFrame,
    station: str = None,
    *args,
    crop_type: str = "Padi",
    crop_c: float = None,
    infill_method: str = "none",
    **kwargs
) -> dict:
    """
    Menghitung Curah Hujan Andalan (R80) & Debit Andalan Irigasi (Q80) Metode Weibull (P = m / (N+1) * 100%).
    Murni berdasarkan parameter data curah hujan tanpa memerlukan luas DAS.
    
    Koefisien Pengaliran / Curah Hujan Efektif Irigasi Standar KP-01 Ditjen Pengairan:
    - Padi: C = 0.70
    - Palawija: C = 0.50
    - Hortikultura: C = 0.60
    
    Output Debit Irigasi:
    - R80 (mm/bulan): Curah Hujan Andalan Keandalan 80%
    - Q80 (mm/bulan): Curah Hujan Efektif / Debit Andalan Irigasi = C * R80
    - Q80 (mm/hari): Rata-rata harian = Q80_bulan / Hari
    - Q80 (L/detik): Ketersediaan debit andalan irigasi = Q80_hari * 0.11574
    """
    try:
        if args:
            for arg in args:
                if isinstance(arg, str) and arg in CROP_IRRIGATION_CONFIG:
                    crop_type = arg
                elif isinstance(arg, (int, float)) and 0.0 < arg <= 1.0:
                    crop_c = float(arg)

        infill_method = kwargs.get("infill_method", infill_method)
        infill_log_df = pd.DataFrame()
        if infill_method != "none":
            work_df, full_infill_log = infill_missing_rainfall(df, method=infill_method)
            infill_log_df = full_infill_log
        else:
            work_df = df

        sub = work_df[work_df["Curah_Hujan"].notna()].copy()
        if sub.empty:
            return {
                "summary": pd.DataFrame(), "rankings": {}, "annual_ranking": pd.DataFrame(),
                "crop_info": {}, "infill_count": 0, "infill_log": pd.DataFrame()
            }

        c_val = crop_c if crop_c is not None else CROP_IRRIGATION_CONFIG.get(crop_type, {}).get("coef", 0.70)

        # Pisahkan perhitungan jika 1 stasiun spesifik vs semua stasiun (rata-rata kawasan)
        is_area_avg = (station is None) or any(k in str(station) for k in ["Semua Stasiun", "Rata-rata Kawasan", "Kawasan"])
        if not is_area_avg:
            stn_filter_str = str(station).strip()
            sub = sub[sub["Stasiun"].astype(str) == stn_filter_str]
            if not infill_log_df.empty:
                infill_log_df = infill_log_df[infill_log_df["Stasiun"] == stn_filter_str]
            if sub.empty:
                return {
                    "summary": pd.DataFrame(), "rankings": {}, "annual_ranking": pd.DataFrame(),
                    "crop_info": {}, "infill_count": 0, "infill_log": pd.DataFrame()
                }
            monthly_matrix = sub.groupby(["Tahun", "Bulan"])["Curah_Hujan"].sum().unstack(level="Bulan")
            complete_years = monthly_matrix.dropna(subset=[m for m in range(1, 13) if m in monthly_matrix.columns], how='any').index
            annual_series = monthly_matrix.loc[complete_years].sum(axis=1) if len(complete_years) > 0 else sub.groupby("Tahun")["Curah_Hujan"].sum()
        else:
            # RATA-RATA KAWASAN (Rata-rata curah hujan antar stasiun, BUKAN dijumlahkan!)
            stn_m = sub.groupby(["Stasiun", "Tahun", "Bulan"])["Curah_Hujan"].sum().reset_index()
            monthly_matrix = stn_m.groupby(["Tahun", "Bulan"])["Curah_Hujan"].mean().unstack(level="Bulan")
            complete_years = monthly_matrix.dropna(subset=[m for m in range(1, 13) if m in monthly_matrix.columns], how='any').index
            annual_series = monthly_matrix.loc[complete_years].sum(axis=1) if len(complete_years) > 0 else stn_y.groupby("Tahun")["Curah_Hujan"].mean()

        def _natural_stn_sort(s):
            m = re.match(r"^(\d+)([a-zA-Z]*)$", str(s).strip())
            return (int(m.group(1)), m.group(2).lower()) if m else (9999, str(s).lower())

        stations_used = sorted([str(s) for s in sub["Stasiun"].dropna().unique()], key=_natural_stn_sort)
        years_used = sorted([int(y) for y in sub["Tahun"].dropna().unique()])

        summary_rows = []
        rankings_dict = {}

        for m in range(1, 13):
            m_name = MONTH_NAMES_INDONESIA[m]
            days = DAYS_PER_MONTH[m]

            if m in monthly_matrix.columns:
                series_m = monthly_matrix[m].dropna()
            else:
                series_m = pd.Series(dtype=float)

            rank_df = calculate_weibull_ranking(series_m)
            rankings_dict[m_name] = rank_df

            r80_val = interpolate_weibull_value(rank_df, 80.0)
            q80_bln = round(c_val * r80_val, 1)
            q80_hari = round(q80_bln / days, 2) if days > 0 else 0.0
            q80_lps_ha = round(q80_hari * 0.11574, 3)

            summary_rows.append({
                "No": m,
                "Bulan / Periode": m_name,
                "Hari": int(days),
                "R80 Curah Hujan (mm)": round(r80_val, 1),
                "Koefisien (C)": round(c_val, 2),
                "Q80 Andalan Irigasi (mm)": q80_bln,
                "Q80 Rata-rata (mm/hari)": q80_hari,
                "Q80 Debit Irigasi (L/detik)": q80_lps_ha
            })

        # Analisis Total Tahunan
        annual_rank = calculate_weibull_ranking(annual_series)
        rankings_dict["Tahunan"] = annual_rank

        r80_ann = interpolate_weibull_value(annual_rank, 80.0)
        q80_ann_bln = round(c_val * r80_ann, 1)
        q80_ann_hari = round(q80_ann_bln / 365.25, 2)
        q80_ann_lps = round(q80_ann_hari * 0.11574, 3)

        summary_rows.append({
            "No": 13,
            "Bulan / Periode": "TOTAL TAHUNAN",
            "Hari": 365,
            "R80 Curah Hujan (mm)": round(r80_ann, 1),
            "Koefisien (C)": round(c_val, 2),
            "Q80 Andalan Irigasi (mm)": q80_ann_bln,
            "Q80 Rata-rata (mm/hari)": q80_ann_hari,
            "Q80 Debit Irigasi (L/detik)": q80_ann_lps
        })

        return {
            "summary": pd.DataFrame(summary_rows),
            "rankings": rankings_dict,
            "annual_ranking": annual_rank,
            "crop_type": crop_type,
            "crop_coef": c_val,
            "stations_used": stations_used,
            "years_used": years_used,
            "n_years": len(years_used),
            "n_stations": len(stations_used),
            "infill_method": infill_method,
            "infill_count": len(infill_log_df),
            "infill_log": infill_log_df
        }
    except Exception as e:
        return {
            "summary": pd.DataFrame(),
            "rankings": {},
            "annual_ranking": pd.DataFrame(),
            "crop_type": crop_type,
            "crop_coef": 0.70,
            "error": str(e)
        }


