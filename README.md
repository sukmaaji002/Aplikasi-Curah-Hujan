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

### 2. Panel Filter Multi-Parameter (Sidebar)
- **Filter Waktu**:
  - *Rentang Tanggal Bebas*: Pilih tanggal mulai dan tanggal akhir.
  - *Pilih Tahun & Bulan Cepat*: Pilih kombinasi tahun (2015–2026) dan bulan (Januari–Desember) dengan tombol pintas *Pilih Semua*.
  - *Pilihan Musim Cepat*: Musim Hujan (Oktober - April) atau Musim Kemarau (Mei - September).
- **Filter Stasiun Pengamatan**:
  - Pilihan multi-select 34 stasiun dengan tombol pintas *Pilih Semua* dan *Reset Pilihan*.
- **Filter Intensitas Curah Hujan & Kategori BMKG**:
  - Opsi *Hanya Hari Hujan (> 0 mm)* atau *Hari Tanpa Hujan (0 mm)*.
  - 7 Kategori BMKG: Berawan/Tanpa Hujan ($0\text{ mm}$), Hujan Sangat Ringan ($0.1–5\text{ mm}$), Ringan ($5–20\text{ mm}$), Sedang ($20–50\text{ mm}$), Lebat ($50–100\text{ mm}$), Sangat Lebat ($100–150\text{ mm}$), dan Ekstrem ($> 150\text{ mm}$).
  - Slider batas nilai curah hujan harian ($0.0\text{ mm}$ s/d batas maksimum).
  - Opsi sertakan atau sembunyikan status data sensor rusak.

### 3. Tampilan & Analisis Data (5 Tab Utama)
- 📋 **Tab 1: Data Detail Harian**:
  - Tampilan 3 tingkat kategorisasi: *Detail Harian (dengan pemilih tahun cepat)*, *Rekapitulasi Bulanan*, dan *Rekapitulasi Tahunan*.
  - Urutan kolom kategorisasi: `No` $\rightarrow$ `Stasiun` $\rightarrow$ `Tahun` $\rightarrow$ `Bulan` $\rightarrow$ `Hari` $\rightarrow$ `Tanggal` $\rightarrow$ `Curah Hujan` $\rightarrow$ `Kategori BMKG` $\rightarrow$ `Status`.
- 📅 **Tab 2: Matriks Hidrologi Bulanan (Lengkap untuk Semua Stasiun & Tahun)**:
  - **Seluruh Matriks**: Menampilkan seluruh tabel matriks standar PU (Tanggal 1–31 vs Bulan Jan–Des + baris *JUMLAH*, *RATA-RATA*, *MAKSIMUM*, *HARI HUJAN*) untuk **semua stasiun yang dipilih** dan **semua tahun terpilih**.
  - **Matriks Rekap Bulanan Antar Stasiun**: Tabel perbandingan seluruh stasiun vs 12 bulan.
  - **Matriks Pmax Tahunan**: Matriks nilai curah hujan harian maksimum per stasiun untuk setiap tahun pengamatan.
  - **Fokus 1 Matriks**: Opsi cepat melihat 1 stasiun dan 1 tahun spesifik.
- 📈 **Tab 3: Grafik Visualisasi & Tren**:
  - Grafik tren fluktuasi harian (zoomable dengan range slider).
  - Grafik batang akumulasi bulanan.
  - Donut chart proporsi intensitas BMKG.
  - Ranking stasiun terbasah.
- 📊 **Tab 4: Ringkasan Statistik Per Stasiun**:
  - Tabel statistik komprehensif (Total, Rata-rata, Nilai Maksimum, Hari Hujan, Hari Kering, Sensor Rusak).
- 🌊 **Tab 5: Analisis Frekuensi & Curah Hujan Rancangan (Kala Ulang)**:
  - Perhitungan parameter statistik hidrologi: $\bar{X}$, $S$, $C_v$, $C_s$, $C_k$.
  - Perhitungan Curah Hujan Rancangan Kala Ulang $T = 2, 5, 10, 25, 50, 100$ Tahun menggunakan metode **Gumbel** dan **Log Pearson Tipe III** (Standar SNI Perencanaan Bangunan Air/Drainase).
  - Kurva pertumbuhan probabilitas curah hujan rancangan.
- ✍️ **Tab 6: Input Data Curah Hujan Manual**:
  - **Form Input Tunggal (Cepat)**: Menambah atau mengupdate data satu hari tertentu untuk stasiun yang ada atau stasiun baru. Mendukung status `Normal` (nilai hujan 0.0 s/d 500.0 mm) atau `RUSAK` (alat tidak berfungsi).
  - **Input Grid 1 Bulan Penuh (Bulk Editor)**: Mengedit atau mengisi seluruh 1 s/d 31 hari dalam satu bulan sekaligus melalui tabel interaktif (`st.data_editor`).
  - **Penyimpanan Permanen & Riwayat**: Seluruh data yang ditambahkan otomatis disimpan ke database Parquet lokal dan dicatat di riwayat audit trail (`manual_records_log.csv`).

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
