import sqlite3


def setup_halkarz_db(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS halkarz_ipos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bist_code TEXT,
        company_name TEXT,
        ipo_date TEXT,
        status TEXT,
        price TEXT,
        lot_size TEXT,
        distribution TEXT,
        broker TEXT,
        market TEXT,
        ipo_size TEXT,
        listing_date TEXT,
        discount TEXT,
        free_float TEXT,
        spk_bulletin TEXT,
        detail_url TEXT,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(company_name, ipo_date)
    )
    """)
    conn.commit()
    return conn


def update_halkarz_db(conn, ipo_data):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM halkarz_ipos WHERE company_name = ? AND ipo_date = ?",
                   (ipo_data.get("company_name", ""), ipo_data.get("ipo_date", "")))
    existing = cursor.fetchone()

    if existing:
        cursor.execute("""
        UPDATE halkarz_ipos
        SET bist_code = ?, status = ?, price = ?, lot_size = ?, distribution = ?, broker = ?,
            market = ?, ipo_size = ?, listing_date = ?, discount = ?, free_float = ?,
            spk_bulletin = ?, last_updated = CURRENT_TIMESTAMP
        WHERE id = ?
        """, (
            ipo_data.get("bist_code", ""),
            ipo_data.get("status", ""),
            ipo_data.get("price", ""),
            ipo_data.get("lot_size", ""),
            ipo_data.get("distribution", ""),
            ipo_data.get("broker", ""),
            ipo_data.get("market", ""),
            ipo_data.get("ipo_size", ""),
            ipo_data.get("listing_date", ""),
            ipo_data.get("discount", ""),
            ipo_data.get("free_float", ""),
            ipo_data.get("spk_bulletin", ""),
            existing[0],
        ))
        return False
    else:
        cursor.execute("""
        INSERT INTO halkarz_ipos (bist_code, company_name, ipo_date, status, price, lot_size,
            distribution, broker, market, ipo_size, listing_date, discount, free_float,
            spk_bulletin, detail_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ipo_data.get("bist_code", ""),
            ipo_data.get("company_name", ""),
            ipo_data.get("ipo_date", ""),
            ipo_data.get("status", ""),
            ipo_data.get("price", ""),
            ipo_data.get("lot_size", ""),
            ipo_data.get("distribution", ""),
            ipo_data.get("broker", ""),
            ipo_data.get("market", ""),
            ipo_data.get("ipo_size", ""),
            ipo_data.get("listing_date", ""),
            ipo_data.get("discount", ""),
            ipo_data.get("free_float", ""),
            ipo_data.get("spk_bulletin", ""),
            ipo_data.get("detail_url", ""),
        ))
        return True
