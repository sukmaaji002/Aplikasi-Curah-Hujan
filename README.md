# 🌧️ Aplikasi Filter & Analisis Data Curah Hujan

Aplikasi desktop berbasis web interaktif untuk memfilter, menganalisis, dan mengekspor data curah hujan harian dari berbagai stasiun pengamatan hidrologi.

---

## 🚀 Cara Menjalankan Aplikasi (Sangat Mudah)

Telah disiapkan file peluncur praktis langsung di **Desktop** Anda:

### 🌟 Pilihan 1 (Paling Praktis - Langsung Membuka Browser):
- Buka **Desktop** Anda.
- **Double-click** file: **`Buka Aplikasi Curah Hujan.vbs`**
- Browser Anda (Chrome / Edge) akan otomatis terbuka dan menampilkan aplikasi tanpa menampilkan jendela command prompt hitam!

### 🌟 Pilihan 2 (File Batch Standar):
- **Double-click** file: **`Aplikasi Curah Hujan.bat`** di Desktop Anda (atau `JALANKAN_APLIKASI.bat` di folder kerja).
- Aplikasi akan otomatis membersihkan koneksi lama dan membuka browser di alamat:
  **`http://localhost:8501`**

---

## 🌟 Fitur Utama

### 1. Sumber Data Fleksibel
- **Data Bawaan (Otomatis)**: Langsung memuat data lengkap 10+ tahun (2015 - 2026) dari 34 stasiun pengamatan (total 149.022 baris data) dalam hitungan milidetik.
- **Unggah File Excel**: Mendukung file `.xlsx` dan `.xls`.
- **Unggah File CSV**: Mendukung file format `.csv`.
- **Tempel Teks CSV Langsung**: Memungkinkan Anda menempelkan potongan teks data tabel CSV secara langsung.

### 2. Panel Sidebar Dua Kategori (CURAH HUJAN & DATA DEBIT)
- **🌧️ Kategori CURAH HUJAN**:
  - Filter Sumber Data (Data bawaan 2015-2026, upload Excel/CSV, tempel CSV).
  - Filter Rentang Tanggal, Tahun & Bulan, serta Musim Hujan/Kemarau.
  - Filter 34 Stasiun Pengamatan dengan tombol cepat.
  - Filter Intensitas Curah Hujan & Kategori BMKG.
  - Ekspor Laporan Curah Hujan (Excel & PDF).
- **💧 Kategori DATA DEBIT**:
  - Ringkasan Basis Data 4 Bendung (Rajabawah, Pondoh, Kemaron, Lengkong).
  - Unduh Database Debit Lengkap (.xlsx dan .csv).
  - Status Cloud Sync GitHub.

### 3. Tampilan & Analisis Data per Kategori

#### A. Modul CURAH HUJAN:
- 📋 **Tab 1: Data Detail Harian**:
  - Tampilan 3 tingkat kategorisasi: *Detail Harian (dengan pemilih tahun cepat)*, *Rekapitulasi Bulanan*, dan *Rekapitulasi Tahunan*.
  - Urutan kolom: `No` $\rightarrow$ `Stasiun` $\rightarrow$ `Tahun` $\rightarrow$ `Bulan` $\rightarrow$ `Hari` $\rightarrow$ `Tanggal` $\rightarrow$ `Curah Hujan` $\rightarrow$ `Kategori BMKG` $\rightarrow$ `Status`.
- ✍️ **Tab 2: Input Manual Curah Hujan**:
  - Form input tunggal cepat & Grid bulk editor 1 bulan penuh dengan audit log.
- 📅 **Tab 3: Matriks Hidrologi Bulanan**:
  - Matriks standar PU (Tanggal 1–31 vs Bulan Jan–Des), matriks rekap antar stasiun, dan matriks Pmax tahunan.
- 🌊 **Tab 4: Analisis Frekuensi & Curah Hujan Rancangan (Kala Ulang)**:
  - Perhitungan statistik ($\bar{X}$, $S$, $C_v$, $C_s$, $C_k$) dan Kala Ulang $T = 2, 5, 10, 25, 50, 100$ Tahun metode Gumbel & Log Pearson Tipe III.
- 📈 **Tab 5: Grafik Visualisasi & Tren**:
  - Fluktuasi harian, akumulasi bulanan, proporsi BMKG, dan ranking stasiun terbasah.
- 📊 **Tab 6: Ringkasan Statistik Per Stasiun**:
  - Metrik statistik komprehensif seluruh stasiun pengamatan.

#### B. Modul DATA DEBIT:
- 📋 **Tab 1: Data Debit Bendung**:
  - Matriks data debit observasi 1/2 bulanan (2004/2005 - 2024/2025) untuk 4 bendung dalam satuan **Liter/detik (L/s)**.
  - Filter tampilan bendung & tahun hidrologi serta ringkasan statistik per periode.
  - Unduh data terfilter ke Excel (.xlsx) dan CSV (.csv).
- ✍️ **Tab 2: Input Debit Manual**:
  - Form input/edit 1 tahun hidrologi penuh (24 periode 1/2 bulanan: Okt I s/d Sep II).
  - Spreadsheet editor langsung (`st.data_editor`) untuk pengeditan bulk multi-tahun.
  - Penyimpanan permanen dan riwayat audit trail (`manual_debit_log.csv`).
- 💧 **Tab 3: Debit Andalan Bendung (Weibull Q80)**:
  - Perhitungan debit andalan menggunakan rumus Weibull $P = \frac{m}{N + 1} \times 100\%$ pada keandalan $80\%$ ($Q_{80}$ / $R_{80}$) sesuai Standar Perencanaan Irigasi KP-01 Ditjen SDA PUPR.
  - Tabel rekapitulasi 1/2 bulanan (24 periode) dan bulanan (12 bulan) dalam satuan Liter/detik.
  - Hidrograf debit andalan, diagram batang bulanan, kurva durasi debit (FDC), dan komparasi 4 bendung.
  - Ekspor laporan resmi Excel (.xlsx).

### 4. Ekspor Data Lengkap (Excel & PDF)
- 📥 **Ekspor Excel (`.xlsx`)**:
  - **Sheet Data Harian Dipisahkan Berdasarkan Tahun**:
    Setiap tahun yang Anda filter otomatis dibuatkan sheet tersendiri (misal: `Data Harian 2015`, `Data Harian 2016`, s/d `Data Harian 2026`). Tidak lagi bercampur menjadi satu sheet besar!
  - Sheet `Ringkasan Per Stasiun`: Tabel rekap metrik statistik per stasiun.
  - Sheet `Matriks Hidrologi Lengkap`:
    - Mengikuti format standar dinas PU / BBWS: Tanggal 1 s/d 31 vs Bulan Terpilih.
    - **Nilai 0 ditulis angka `0`**: Hari tanpa hujan (kering) ditulis angka numerik 0, bukan tanda strip (`-`).
    - **Sensor Rusak ditulis strip (`-`)**: Hari di mana alat pengukur rusak ditandai tanda strip (`-`).
    - **Urutan Blok**: Dikelompokkan per nama stasiun terlebih dahulu, lalu tahun-tahunnya berurutan kronologis (`22a 2016`, `22a 2017`, `22b 2016`, `22b 2017`, dst.).
    - **Filter Bulan Dinamis**: Hanya bulan-bulan yang dipilih di filter yang akan ditampilkan sebagai kolom.
  - Sheet `Rekap Bulanan Antar Stasiun`: Matriks silang seluruh stasiun vs 12 bulan.
  - Sheet `Pmax Tahunan Stasiun`: Matriks nilai curah hujan harian maksimum per stasiun untuk setiap tahun pengamatan.
- 📄 **Ekspor PDF (`.pdf`)**:
  - Laporan resmi siap cetak format A4 Landscape lengkap dengan kop laporan, metadata filter, ringkasan statistik per stasiun, tabel data harian, dan penomoran halaman otomatis.
