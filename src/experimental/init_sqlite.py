# init_sqlite.py — creates a finance-themed SQLite DB for reference
import sqlite3

# Create a SQLite database
conn = sqlite3.connect("finance_reference.db")
cursor = conn.cursor()

# Create a finance-themed table: transactions
cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INTEGER PRIMARY KEY,
    account_number TEXT,
    transaction_type TEXT,
    amount REAL,
    currency TEXT,
    transaction_date TEXT,
    description TEXT
)
""")

# Insert sample transactions
sample_data = [
    ("ACC123", "DEPOSIT", 1000.00, "USD", "2025-01-10", "Initial deposit"),
    ("ACC123", "WITHDRAWAL", 200.00, "USD", "2025-01-15", "ATM Withdrawal"),
    ("ACC456", "TRANSFER", 500.00, "USD", "2025-02-01", "Transfer to ACC789"),
    ("ACC789", "DEPOSIT", 300.00, "USD", "2025-02-05", "Online deposit"),
    ("ACC456", "WITHDRAWAL", 100.00, "USD", "2025-02-10", "Bill payment")
]

cursor.executemany("""
INSERT INTO transactions (account_number, transaction_type, amount, currency, transaction_date, description)
VALUES (?, ?, ?, ?, ?, ?)
""", sample_data)

conn.commit()
conn.close()

print("✅ finance_reference.db initialized with sample data.")
