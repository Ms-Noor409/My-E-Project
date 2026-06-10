import sqlite3
import json
import csv
from werkzeug.security import generate_password_hash
from db_utils import db_session


def init_db():
    print("Initializing Database...")
    with db_session() as conn:

        # USERS
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT UNIQUE,
                password_hash TEXT,
                role TEXT DEFAULT 'customer',
                preferences TEXT,
                status TEXT DEFAULT 'active'
            )
        ''')

        # PRODUCTS (UPDATED FOR YOUR DATASET)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                category TEXT,
                price REAL,
                quantity INTEGER,
                total_amount REAL,
                gender TEXT,
                material TEXT,
                stone TEXT,
                short_description TEXT,
                long_description TEXT,
                image TEXT
            )
        ''')

        # CART ITEMS
        conn.execute('''
            CREATE TABLE IF NOT EXISTS cart_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_id INTEGER,
                product_name TEXT,
                quantity INTEGER DEFAULT 1,
                added_date TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        ''')

        # ORDERS
        conn.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                customer_name TEXT,
                email TEXT,
                phone TEXT,
                address TEXT,
                city TEXT,
                postal_code TEXT,
                items TEXT,
                total REAL,
                status TEXT DEFAULT 'Processing',
                payment_method TEXT DEFAULT 'cash',
                created_date TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Add payment_method column if it doesn't exist
        try:
            conn.execute('ALTER TABLE orders ADD COLUMN payment_method TEXT DEFAULT "cash"')
        except:
            pass

# 4. Activity Logs
        conn.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TEXT NOT NULL
            )
        ''')

        # REVIEWS
        conn.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                user_id INTEGER,
                user_name TEXT,
                rating INTEGER,
                comment TEXT,
                date TEXT
            )
        ''')


def seed_db():
    print("Seeding Data...")

    with db_session() as conn:

        # USERS
        cur = conn.execute("SELECT COUNT(*) as count FROM users")
        if cur.fetchone()["count"] == 0:
          admin_hash = generate_password_hash('password123') 
          user_hash = generate_password_hash('password123')
            
          conn.execute('INSERT INTO users (name, email, password_hash, role, preferences) VALUES (?, ?, ?, ?, ?)',
             ("Admin Noor", "admin@noor.com", admin_hash, "admin", json.dumps([])))

          conn.execute('INSERT INTO users (name, email, password_hash, role, preferences)VALUES (?, ?, ?, ?, ?)',
            ("Ayesha Khan", "user@khan.com", user_hash, "customer", json.dumps(["gold", "diamond", "necklace"])))


        # PRODUCTS (FROM CSV)
        cur = conn.execute("SELECT COUNT(*) as count FROM products")
        if cur.fetchone()["count"] == 0:

    
         products = [

    # NECKLACE
       ("Diamond Heart Necklace", "necklace", 180, 1, 180, "f", "gold", "diamond",
       "Elegant heart necklace", "Beautiful diamond heart necklace for special occasions",
       "https://images.unsplash.com/photo-1601121141461-9d6647bca1ed"),

       ("Gold Minimal Necklace", "necklace", 120, 1, 120, "f", "gold", "none",
       "Minimal gold chain", "Simple and elegant gold necklace for daily wear",
       "https://images.unsplash.com/photo-1603974372039-adc49044b6bd"),

       ("Luxury Pearl Necklace", "necklace", 150, 1, 150, "f", "pearl", "pearl",
       "Classic pearl necklace", "Elegant pearl necklace for formal events",
       "https://images.unsplash.com/photo-1611652022419-a9419f74343d"),


    # RINGS
       ("Diamond Engagement Ring", "ring", 250, 1, 250, "f", "gold", "diamond",
       "Luxury engagement ring", "Premium diamond ring for engagements",
       "https://images.unsplash.com/photo-1605100804763-247f67b3557e"),

       ("Silver Fashion Ring", "ring", 90, 1, 90, "f", "silver", "none",
       "Stylish silver ring", "Modern silver ring for fashion lovers",
       "https://images.unsplash.com/photo-1605100804782-5c3b8f1c5b15"),

       ("Emerald Luxury Ring", "ring", 220, 1, 220, "f", "gold", "emerald",
       "Emerald stone ring", "Luxury emerald ring with golden finish",
       "https://images.unsplash.com/photo-1611591437281-460bfbe1220a"),


    # BRACELETS
       ("Gold Charm Bracelet", "bracelet", 110, 1, 110, "f", "gold", "none",
       "Charm bracelet", "Elegant gold charm bracelet",
       "https://images.unsplash.com/photo-1617038260897-41a1f14a8ca0"),

       ("Pearl Bracelet Classic", "bracelet", 95, 1, 95, "f", "pearl", "pearl",
       "Classic pearl bracelet", "Simple pearl bracelet for elegant look",
       "https://images.unsplash.com/photo-1611599537845-1c7c2b4b6d1c"),


    # EARRINGS
       ("Diamond Stud Earrings", "earrings", 130, 1, 130, "f", "gold", "diamond",
       "Diamond studs", "Classic diamond stud earrings",
       "https://images.unsplash.com/photo-1617038220319-1b8f5f5f5f5f"),

       ("Gold Hoop Earrings", "earrings", 80, 1, 80, "f", "gold", "none",
       "Hoop earrings", "Trendy gold hoop earrings for daily use",
       "https://images.unsplash.com/photo-1620891549027-942fdc95d3f5"),

       ("Pearl Drop Earrings", "earrings", 100, 1, 100, "f", "pearl", "pearl",
       "Elegant drop earrings", "Stylish pearl drop earrings for parties",
       "https://images.unsplash.com/photo-1617038260866-7f8c2b6a3a21"),


    # PENDANTS 
       ("Diamond Circle Pendant", "pendant", 140, 1, 140, "f", "gold", "diamond",
       "Elegant circle pendant", "Stylish diamond circle pendant for modern look",
       "https://images.unsplash.com/photo-1600721391689-2564bb8055de"),

       ("Gold Heart Pendant", "pendant", 110, 1, 110, "f", "gold", "none",
       "Heart pendant", "Simple gold heart pendant for daily wear",
       "https://images.unsplash.com/photo-1603974372039-adc49044b6bd"),

       ("Pearl Drop Pendant", "pendant", 125, 1, 125, "f", "pearl", "pearl",
       "Pearl pendant", "Elegant pearl drop pendant for special occasions",
       "https://images.unsplash.com/photo-1611652022419-a9419f74343d")
    ]

         conn.executemany('''
                INSERT INTO products (
                    name, category, price, quantity, total_amount,
                    gender, material, stone,
                    short_description, long_description, image
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', products)


if __name__ == "__main__":
    print("=" * 60)
    print("NOOR Jewelry Store - Database Initialization")
    print("=" * 60)
    
    try:
        # Create all tables
        init_db()
        print("✓ Database tables created successfully!")
        
        # Seed initial data
        seed_db()
        print("✓ Sample data inserted successfully!")
        
        print("\n" + "=" * 60)
        print("Database initialization completed!")
        print("=" * 60)
        print("\nYou can now run: python main.py")
        
    except Exception as e:
        print(f"\n✗ Error during initialization: {str(e)}")
        import traceback
        traceback.print_exc()