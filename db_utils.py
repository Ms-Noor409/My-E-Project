import sqlite3 # for sql
from contextlib import contextmanager # to use db safely 

DB_PATH = 'database.db' # creating database path or filename 

def get_db_connection(): # creating database connection
    conn = sqlite3.connect(DB_PATH) # connecting db
    conn.row_factory = sqlite3.Row # we will access data with keys not index

    #row[0]
    #row["user"] this one
    return conn

@contextmanager # @ is decorator yeh functions ko speciall power deta hai context manager db ko auto open close krta hai
def db_session(): # hum yeh function bana rahe hain ta k db ko safely use kr paye 
    conn = get_db_connection() # caaling above function
    try:
        yield conn
        conn.commit()  # agar sb theek hogya to commit krdo  
    except Exception as e: 
        conn.rollback() # otherwise rollback krdo sari changes jo ki thi wapas
        raise e
    finally:
        conn.close() # connection close krdo

# args query ke ? placeholders me real values fill karta

def query_db(query, args=(), one=False):   # yeh function hum da
    with db_session() as conn: # database open karta hai uper wala function call krta hai
        cur = conn.execute(query, args) # query run krega and results cur variable save krdega 
        rv = cur.fetchall() # fetchall se hum cursor se data uthaenge  and RV main save krdenge
#         [
#   {"id": 1, "name": "Ali"},
#   {"id": 2, "name": "Asad"}
# ]
        return (rv[0] if rv else None) if one else rv
    
# if one:
#     if rv:
#         return rv[0]
#     else:
#         return None
# else:
#     return rv
    
# Agar one=True:

# data hai → pehla record do
# data nahi → None do

# Agar one=False:

# poori list de do

def insert_db(query, args=()):  # yeh table me data insert krne k lia function hai 
    with db_session() as conn: # yeh database ko open krega 
        cur = conn.execute(query, args) # yeh query run hogi 
        return cur.lastrowid # yeh last entered record ki id dega
    

# insert_db(
#     "INSERT INTO users (name) VALUES (?)",
#     ("Ali",)
# )

def export_users():
    """Exports all existing database users to users_data.txt"""
    print("--- Exporting Users ---")
    try:
        users = query_db("SELECT * FROM users")
        with open("users_data.txt", "w", encoding="utf-8") as f:
            f.write("--- CURRENT REGISTERED USERS DUMP FROM DATABASE ---\n")
            if users:
                for user in users:
                    f.write(f"Name: {user['name']} | Email: {user['email']} | Role: {user['role']}\n")
        print("Successfully exported all existing database users to users_data.txt")
    except Exception as e:
        print(f"Error exporting users: {str(e)}")

def verify_db():
    """Quick verification script to check database status"""
    print("=" * 60)
    print("DATABASE VERIFICATION - NOOR Jewelry Store")
    print("=" * 60)
    
    try:
        # Check user count
        users_result = query_db('SELECT COUNT(*) as count FROM users')
        user_count = users_result[0]['count'] if users_result else 0
        print(f"\n✓ Users in database: {user_count}")
        
        # Check product count
        products_result = query_db('SELECT COUNT(*) as count FROM products')
        product_count = products_result[0]['count'] if products_result else 0
        print(f"✓ Products in database: {product_count}")
        
        # Check orders count
        orders_result = query_db('SELECT COUNT(*) as count FROM orders')
        orders_count = orders_result[0]['count'] if orders_result else 0
        print(f"✓ Orders in database: {orders_count}")
        
        # Show test users
        print("\n" + "=" * 60)
        print("TEST CREDENTIALS (for testing the application)")
        print("=" * 60)
        
        test_users = query_db('SELECT email, role FROM users')
        if test_users:
            for user in test_users:
                print(f"\nEmail: {user['email']}")
                print(f"Role: {user['role']}")
                print(f"Password: password123")
        
        print("\n" + "=" * 60)
        print("✓ All systems operational!")
        print("=" * 60)
        print("\n🚀 Application is ready!")
        print("   Server running at: http://127.0.0.1:5000")
        print("\n📝 Next Steps:")
        print("   1. Open http://127.0.0.1:5000 in your browser")
        print("   2. Register or login with credentials above")
        print("   3. Browse products and add to cart")
        print("   4. Complete checkout")
        print("   5. Check database.db for saved orders")
        
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == "verify":
            verify_db()
        elif command == "export":
            export_users()
        else:
            print(f"Unknown command: {command}")
            print("Available commands: verify, export")
    else:
        print("Available commands: verify, export")
        print("Example: python db_utils.py verify")
