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

def get_pmax_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """
    Menghasilkan tabel matriks curah hujan harian maksimum tahunan (Pmax)
    untuk setiap stasiun dan setiap tahun.
    """
    valid_df = df[df["Curah_Hujan"].notna()]
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

def get_design_rainfall_summary(df: pd.DataFrame, station: str) -> pd.DataFrame:
    """
    Menghasilkan tabel komparasi curah hujan rancangan (Gumbel & Log Pearson III)
    untuk satu stasiun pengamatan.
    """
    sub = df[(df["Stasiun"] == station) & (df["Curah_Hujan"].notna())]
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

