"""
ETL script: Load Battery Degradation Dataset ke SQLite.

Source: data/raw/Battery_dataset.csv (dari Kaggle)
Target: data/battery.db

Mapping kolom CSV → SQLite:
  battery_id   →  battery_id
  cycle        →  cycle
  chI          →  charge_current    (Ampere)
  chV          →  charge_voltage    (Volt)
  chT          →  charge_temperature (Celsius)
  disI         →  discharge_current  (Ampere)
  disV         →  discharge_voltage  (Volt)
  disT         →  discharge_temperature (Celsius)
  BCt          →  capacity           (Ah)
  SOH          →  soh                (%)
  RUL          →  rul                (cycles)

Usage: python load_battery_data.py
"""
import sqlite3
from pathlib import Path

import pandas as pd

# Paths
RAW_CSV = Path("data/raw/Battery_dataset.csv")
DB_PATH = Path("data/battery.db")

# Mapping CSV column → DB column (lebih self-describing)
COLUMN_MAPPING = {
    "battery_id": "battery_id",
    "cycle": "cycle",
    "chI": "charge_current",
    "chV": "charge_voltage",
    "chT": "charge_temperature",
    "disI": "discharge_current",
    "disV": "discharge_voltage",
    "disT": "discharge_temperature",
    "BCt": "capacity",
    "SOH": "soh",
    "RUL": "rul",
}


def main():
    print("=" * 60)
    print("🔋 BATTERY DATA ETL")
    print("=" * 60)

    # Verifikasi file source ada
    if not RAW_CSV.exists():
        print(f"❌ ERROR: {RAW_CSV} tidak ditemukan.")
        print("   Download dari Kaggle dan letakkan di data/raw/")
        return

    # Hapus DB lama kalau ada (fresh start)
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"🗑️  Database lama dihapus")

    DB_PATH.parent.mkdir(exist_ok=True)

    # ===========================================================
    # Step 1: Read CSV pakai pandas
    # ===========================================================
    print(f"\n📂 Reading {RAW_CSV.name}...")
    df = pd.read_csv(RAW_CSV)
    print(f"   ✅ Loaded {len(df):,} rows × {len(df.columns)} columns")

    # ===========================================================
    # Step 2: Verifikasi kolom yang diharapkan ada
    # ===========================================================
    expected_cols = set(COLUMN_MAPPING.keys())
    actual_cols = set(df.columns)
    missing = expected_cols - actual_cols
    if missing:
        print(f"❌ ERROR: Kolom hilang dari CSV: {missing}")
        print(f"   Kolom yang ada: {sorted(actual_cols)}")
        return

    # ===========================================================
    # Step 3: Rename kolom ke nama yang self-describing
    # ===========================================================
    df = df.rename(columns=COLUMN_MAPPING)
    # Pilih hanya kolom yang kita pakai (urutan tetap)
    df = df[list(COLUMN_MAPPING.values())]
    print(f"   ✅ Renamed columns to self-describing names")

    # ===========================================================
    # Step 4: Data quality checks
    # ===========================================================
    print(f"\n🔍 Data quality checks:")
    print(f"   • Batteries: {sorted(df['battery_id'].unique().tolist())}")
    print(f"   • Cycles range: {df['cycle'].min()} – {df['cycle'].max()}")
    print(f"   • SOH range: {df['soh'].min():.2f}% – {df['soh'].max():.2f}%")
    print(f"   • RUL range: {df['rul'].min()} – {df['rul'].max()} cycles")
    print(f"   • Null values: {df.isnull().sum().sum()}")

    # Cek duplikat (battery_id, cycle) — harus unique
    dup_count = df.duplicated(subset=["battery_id", "cycle"]).sum()
    if dup_count > 0:
        print(f"   ⚠️  WARNING: {dup_count} duplicate (battery_id, cycle) pairs")
    else:
        print(f"   ✅ No duplicates on (battery_id, cycle)")

    # ===========================================================
    # Step 5: Create table & insert data
    # ===========================================================
    print(f"\n💾 Writing to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE battery_cycles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            battery_id TEXT NOT NULL,
            cycle INTEGER NOT NULL,
            charge_current REAL,
            charge_voltage REAL,
            charge_temperature REAL,
            discharge_current REAL,
            discharge_voltage REAL,
            discharge_temperature REAL,
            capacity REAL,
            soh REAL,
            rul INTEGER,
            UNIQUE(battery_id, cycle)
        );

        CREATE INDEX idx_battery_cycle ON battery_cycles(battery_id, cycle);
        CREATE INDEX idx_soh ON battery_cycles(soh);
        CREATE INDEX idx_cycle ON battery_cycles(cycle);
    """)

    # Insert via pandas to_sql (efficient batch insert)
    df.to_sql(
        "battery_cycles",
        conn,
        if_exists="append",
        index=False,
    )

    conn.commit()
    print(f"   ✅ Inserted {len(df):,} rows")

    # ===========================================================
    # Step 6: Verification queries
    # ===========================================================
    print(f"\n✨ Verification:")

    cursor.execute("SELECT COUNT(*) FROM battery_cycles")
    total = cursor.fetchone()[0]
    print(f"   Total rows: {total:,}")

    cursor.execute("""
        SELECT battery_id,
               COUNT(*) as cycles,
               MIN(soh) as min_soh,
               MAX(soh) as max_soh,
               ROUND(AVG(charge_temperature), 1) as avg_temp
        FROM battery_cycles
        GROUP BY battery_id
    """)
    print(f"   Per-battery summary:")
    for row in cursor.fetchall():
        bid, cycles, min_soh, max_soh, avg_temp = row
        print(f"     {bid}: {cycles} cycles, SOH {min_soh:.2f}% → {max_soh:.2f}%, "
              f"avg charge temp {avg_temp}°C")

    conn.close()
    print(f"\n✅ ETL complete! Database: {DB_PATH.absolute()}")


if __name__ == "__main__":
    main()