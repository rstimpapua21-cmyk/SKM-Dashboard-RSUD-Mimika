# SKM Dashboard RSUD Mimika

Dashboard interaktif untuk **Survey Kepuasan Masyarakat (SKM)** RSUD Mimika — tersinkron otomatis dari Google Sheets.

## Fitur

- **Real-time Sync** — Data tersinkron otomatis dari Google Sheets setiap 5 menit
- **IKM Calculation** — Indeks Kepuasan Masyarakat dengan grade mutu (A/B/C/D)
- **9 Unsur Pelayanan** — NPU per unsur dengan color-coded visualization
- **31 Unit Filter** — Filter per Poli/Bangsal/ICU/HD/etc.
- **6 Interactive Charts** — Bar, Radar, Stacked Distribution, Doughnut, Trend, Unit Comparison
- **Dark Elegant Theme** — Responsive design untuk semua device

## Cara Menjalankan

1. Double-click **`Start Dashboard.bat`**
2. Dashboard akan otomatis terbuka di browser (`http://localhost:8000/`)
3. Python server akan fetch data dari Google Sheets dan serve locally

### Prerequisites

- Python 3.11+ (terinstall di system)
- Browser modern (Chrome, Edge, Firefox)

## SKM Rating Conversion

Data SKM menggunakan letter-coded responses yang dikonversi otomatis:

| Response | Value |
|---|---|
| a. Tidak/Buruk | 1 |
| b. Kurang | 2 |
| c. Sesuai/Baik | 3 |
| d. Sangat Baik | 4 |

## SKM Quality Scale

| Grade | IKM Range | Label |
|---|---|---|
| A | 3.51 - 4.00 | Sangat Baik |
| B | 3.01 - 3.50 | Baik |
| C | 2.51 - 3.00 | Cukup |
| D | 2.00 - 2.50 | Kurang |

## Data Source

Google Sheets (published): SKM RSUD MIMIKA (Jawaban) : Form Responses 1

## Tech Stack

- **Backend**: Python (HTTP server + Google Sheets proxy + SKM analysis)
- **Frontend**: HTML/CSS/JS + Chart.js
- **Data Pipeline**: Google Sheets CSV → Python parser → JSON API → Dashboard
