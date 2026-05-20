"""
Quick check script untuk explore dataset battery degradation.
Tujuan: lihat struktur dataset secara cepat sebelum design schema.

Usage: python quick_check.py
"""
import pandas as pd
from pathlib import Path

RAW_DIR = Path("data/raw")

print("=" * 60)
print("📂 FILES DI data/raw/")
print("=" * 60)

csv_files = sorted(RAW_DIR.glob("*.csv"))
if not csv_files:
    print("❌ Tidak ada file CSV di data/raw/")
    print("   Pastikan kamu sudah download & extract dataset Kaggle.")
    exit(1)

for f in csv_files:
    size_mb = f.stat().st_size / (1024 * 1024)
    print(f"  • {f.name} ({size_mb:.2f} MB)")

print()

# Loop tiap file, kasih informasi dasar
for csv_file in csv_files:
    print("=" * 60)
    print(f"📊 FILE: {csv_file.name}")
    print("=" * 60)

    try:
        # Coba baca dengan default encoding
        df = pd.read_csv(csv_file, nrows=1000)  # 1000 row dulu biar cepat
    except UnicodeDecodeError:
        # Coba fallback encoding
        print("  ⚠️ UTF-8 gagal, coba latin-1...")
        df = pd.read_csv(csv_file, nrows=1000, encoding='latin-1')

    # Info struktur
    print(f"\n  📐 Shape (sample 1000 rows): {df.shape}")
    print(f"\n  🏷️  Kolom ({len(df.columns)}):")
    for col in df.columns:
        dtype = df[col].dtype
        null_count = df[col].isnull().sum()
        unique_count = df[col].nunique()
        sample_val = df[col].dropna().iloc[0] if df[col].dropna().shape[0] > 0 else "N/A"
        print(f"     {col:30s} | {str(dtype):10s} | nulls: {null_count:4d} "
              f"| unique: {unique_count:6d} | sample: {sample_val}")

    # Sample 5 rows pertama
    print(f"\n  👀 Sample 5 rows:")
    print(df.head().to_string(max_cols=8))

    # Cek total row count (full file)
    print(f"\n  🔢 Counting total rows in full file...")
    total_rows = sum(1 for _ in open(csv_file, encoding='utf-8', errors='replace')) - 1
    print(f"     Total rows: {total_rows:,}")
    print()

print("=" * 60)
print("✅ Quick check selesai!")
print("=" * 60)
print()
print("📤 Copy-paste output ini ke chat kita supaya bisa lanjut design schema.")
print("   Khususnya bagian KOLOM dan SAMPLE ROWS.")
