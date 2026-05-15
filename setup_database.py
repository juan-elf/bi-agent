import sqlite3
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

DB_PATH = Path("data/ecommerce.db")
DB_PATH.parent.mkdir(exist_ok=True)

if DB_PATH.exists():
    DB_PATH.unlink()
    print(f"Removed old database: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("Creating tables...")

cursor.executescript("""
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    city TEXT NOT NULL,
    registered_at DATE NOT NULL
);

CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price INTEGER NOT NULL,
    stock INTEGER NOT NULL
);

CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    order_date DATE NOT NULL,
    status TEXT NOT NULL,
    total_amount INTEGER NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE order_items (
    item_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price INTEGER NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_date ON orders(order_date);
CREATE INDEX idx_items_order ON order_items(order_id);
""")

print("Seeding customers...")

first_names = ["Budi", "Siti", "Andi", "Dewi", "Rudi", "Maya", "Joko", "Rina",
               "Agus", "Lina", "Bayu", "Sari", "Eko", "Putri", "Hadi", "Wati",
               "Doni", "Tina", "Yusuf", "Indah", "Reza", "Mira", "Fahmi", "Ayu"]
last_names = ["Santoso", "Wijaya", "Pratama", "Lestari", "Hidayat", "Susanto",
              "Kusuma", "Permata", "Saputra", "Anggraini", "Setiawan", "Putra"]
cities = ["Jakarta", "Surabaya", "Bandung", "Medan", "Semarang",
          "Yogyakarta", "Makassar", "Denpasar", "Palembang", "Malang"]

# Weighted so Jakarta dominates and smaller cities are sparse — closer to real distribution
city_weights = [30, 18, 15, 8, 8, 7, 5, 4, 3, 2]

start_date = datetime(2024, 1, 1)
end_date = datetime(2026, 5, 1)

customers_data = []
emails_used = set()
for cid in range(1, 201):
    fn = random.choice(first_names)
    ln = random.choice(last_names)
    name = f"{fn} {ln}"

    while True:
        email = f"{fn.lower()}.{ln.lower()}{random.randint(1, 999)}@example.com"
        if email not in emails_used:
            emails_used.add(email)
            break

    city = random.choices(cities, weights=city_weights)[0]
    days_offset = random.randint(0, (end_date - start_date).days)
    registered = start_date + timedelta(days=days_offset)

    customers_data.append((cid, name, email, city, registered.date().isoformat()))

cursor.executemany(
    "INSERT INTO customers VALUES (?, ?, ?, ?, ?)",
    customers_data
)

print("Seeding products...")

products_seed = [
    ("Kaos Polos Cotton Combed", "Fashion", 75000, 250),
    ("Kemeja Flanel Pria", "Fashion", 150000, 80),
    ("Celana Jeans Slim Fit", "Fashion", 220000, 120),
    ("Sepatu Sneakers Putih", "Fashion", 350000, 60),
    ("Tas Ransel Laptop", "Fashion", 280000, 45),
    ("Hijab Pashmina Voal", "Fashion", 45000, 300),

    ("Smartphone Android 6GB", "Elektronik", 2800000, 30),
    ("Earphone Bluetooth TWS", "Elektronik", 180000, 150),
    ("Power Bank 20000mAh", "Elektronik", 220000, 90),
    ("Smart Watch Fitness", "Elektronik", 450000, 40),
    ("Kabel Charger Type-C", "Elektronik", 35000, 500),
    ("Mouse Wireless Ergonomis", "Elektronik", 120000, 100),
    ("Keyboard Mechanical", "Elektronik", 550000, 25),

    ("Kopi Arabica Gayo 250g", "Makanan", 85000, 200),
    ("Madu Hutan Murni 500ml", "Makanan", 120000, 80),
    ("Keripik Singkong Original", "Makanan", 25000, 400),
    ("Coklat Premium Dark 70%", "Makanan", 65000, 150),
    ("Teh Hijau Organic Bag", "Makanan", 45000, 220),

    ("Buku Self-Improvement", "Buku", 95000, 180),
    ("Novel Fiksi Bestseller", "Buku", 89000, 130),
    ("Buku Resep Masakan", "Buku", 78000, 90),
    ("Buku Anak Edukasi", "Buku", 55000, 200),

    ("Skincare Serum Vitamin C", "Kecantikan", 145000, 120),
    ("Masker Wajah Sheet Mask", "Kecantikan", 18000, 600),
    ("Parfum Unisex 50ml", "Kecantikan", 195000, 70),
    ("Sabun Cuci Muka Glow", "Kecantikan", 55000, 250),
    ("Sunscreen SPF 50", "Kecantikan", 89000, 180),

    ("Yoga Mat Anti Slip", "Olahraga", 175000, 50),
    ("Dumbbell Set 5kg", "Olahraga", 290000, 35),
    ("Botol Minum Olahraga", "Olahraga", 65000, 200),
]

products_data = [
    (i + 1, name, cat, price, stock)
    for i, (name, cat, price, stock) in enumerate(products_seed)
]
cursor.executemany(
    "INSERT INTO products VALUES (?, ?, ?, ?, ?)",
    products_data
)

print("Seeding orders & order items...")

statuses = ["completed", "completed", "completed", "completed",
            "shipped", "shipped", "pending", "cancelled"]

order_id_counter = 1
item_id_counter = 1
orders_data = []
items_data = []

for _ in range(1500):
    customer_id = random.randint(1, 200)

    # Order date must be >= customer's registration date
    cursor.execute(
        "SELECT registered_at FROM customers WHERE customer_id = ?",
        (customer_id,)
    )
    reg_date_str = cursor.fetchone()[0]
    reg_date = datetime.fromisoformat(reg_date_str)

    days_after_reg = random.randint(0, (end_date - reg_date).days)
    order_date = reg_date + timedelta(days=days_after_reg)

    status = random.choice(statuses)

    num_items = random.choices([1, 2, 3, 4, 5], weights=[40, 30, 15, 10, 5])[0]
    selected_products = random.sample(products_data, num_items)

    order_total = 0
    items_for_this_order = []
    for product in selected_products:
        pid, _, _, price, _ = product
        qty = random.choices([1, 2, 3], weights=[70, 20, 10])[0]
        line_total = qty * price
        order_total += line_total

        items_for_this_order.append(
            (item_id_counter, order_id_counter, pid, qty, price)
        )
        item_id_counter += 1

    orders_data.append(
        (order_id_counter, customer_id, order_date.date().isoformat(),
         status, order_total)
    )
    items_data.extend(items_for_this_order)
    order_id_counter += 1

cursor.executemany(
    "INSERT INTO orders VALUES (?, ?, ?, ?, ?)",
    orders_data
)
cursor.executemany(
    "INSERT INTO order_items VALUES (?, ?, ?, ?, ?)",
    items_data
)

conn.commit()

print("\n" + "=" * 50)
print("Database created successfully")
print("=" * 50)

for table in ["customers", "products", "orders", "order_items"]:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"  {table:15s}: {count:,} rows")

cursor.execute("SELECT SUM(total_amount) FROM orders WHERE status = 'completed'")
total_revenue = cursor.fetchone()[0]
print(f"\nTotal revenue (completed): Rp {total_revenue:,}")

cursor.execute("SELECT MIN(order_date), MAX(order_date) FROM orders")
min_date, max_date = cursor.fetchone()
print(f"Order period: {min_date} to {max_date}")

print(f"\nDatabase saved to: {DB_PATH.absolute()}")

conn.close()
