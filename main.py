from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from db_utils import query_db, insert_db, db_session
from datetime import datetime
import json
import os
import sqlite3
import uuid
import re
from collections import Counter


app = Flask(__name__)

import joblib
import pandas as pd

MODEL_DIR = os.path.abspath(os.path.dirname(__file__))
VECTORIZER_PATH = os.path.join(MODEL_DIR, "vectorizer.pkl")
COSINE_SIM_PATH = os.path.join(MODEL_DIR, "cosine_sim.pkl")
DATASET_PATH = os.path.join(MODEL_DIR, "dataset.pkl")

loaded_vectorizer = None
loaded_cosine_sim = None
loaded_df = None
product_name_to_index = {}
recommendation_model_available = False

try:
    loaded_vectorizer = joblib.load(VECTORIZER_PATH)
    loaded_cosine_sim = joblib.load(COSINE_SIM_PATH)
    loaded_df = joblib.load(DATASET_PATH)
    if hasattr(loaded_df, 'columns') and 'product_name' in loaded_df.columns:
        recommendation_model_available = True
        product_name_to_index = {
            str(name).strip().lower(): idx
            for idx, name in enumerate(loaded_df['product_name'])
        }
        print("Recommendation model loaded successfully ✔")
    else:
        print("Recommendation dataset does not contain expected columns.")
except Exception as e:
    print(f"Recommendation model could not be loaded: {e}")


@app.template_filter('image_src')
def image_src_filter(image_path):
    if not image_path:
        return ''
    if isinstance(image_path, str) and (image_path.startswith('http://') or image_path.startswith('https://')):
        return image_path
    return url_for('static', filename=image_path)


def product_text_vector(product):
    if not product:
        return Counter()

    text_parts = []
    for field in ("name", "category", "material", "stone", "short_description", "long_description"):
        value = product.get(field) if isinstance(product, dict) else (product[field] if field in product else None)
        if value:
            text_parts.append(str(value))

    tokens = re.findall(r"\w+", " ".join(text_parts).lower())
    return Counter(token for token in tokens if len(token) > 1)


def cosine_similarity(counter1, counter2):
    if not counter1 or not counter2:
        return 0.0

    intersection = sum(counter1[token] * counter2[token] for token in counter1 if token in counter2)
    if intersection == 0:
        return 0.0

    norm1 = sum(value * value for value in counter1.values()) ** 0.5
    norm2 = sum(value * value for value in counter2.values()) ** 0.5
    if norm1 == 0 or norm2 == 0:
        return 0.0

    return intersection / (norm1 * norm2)


def get_dynamic_recommendations(product_id, top_n=5):
    current_product = query_db("SELECT * FROM products WHERE id = ?", (product_id,), one=True)
    if not current_product:
        return []

    current_vector = product_text_vector(dict(current_product))
    candidates = query_db("SELECT * FROM products WHERE id != ?", (product_id,)) or []
    scored = []

    for candidate in candidates:
        score = cosine_similarity(current_vector, product_text_vector(dict(candidate)))
        scored.append((score, candidate))

    scored.sort(key=lambda x: x[0], reverse=True)
    recommended = [candidate for score, candidate in scored if score > 0][:top_n]
    if recommended:
        return recommended
    return [candidate for _, candidate in scored][:top_n]


def get_recommended_products(product_id, product_name, top_n=5):
    if recommendation_model_available and product_name:
        normalized_name = str(product_name).strip().lower()
        item_index = product_name_to_index.get(normalized_name)
        if item_index is not None:
            similar_items = sorted(
                enumerate(loaded_cosine_sim[item_index]),
                key=lambda x: x[1],
                reverse=True
            )

            recommended_names = []
            for index, score in similar_items:
                if index == item_index:
                    continue
                recommended_names.append(loaded_df.iloc[index]["product_name"])
                if len(recommended_names) >= top_n:
                    break

            recommended_products = []
            for recommendation_name in recommended_names:
                product = query_db("SELECT * FROM products WHERE name = ?", (recommendation_name,), one=True)
                if product:
                    recommended_products.append(product)

            if recommended_products:
                return recommended_products
            print(f"No model-based recommendations found for '{product_name}'.")

    return get_dynamic_recommendations(product_id, top_n)

# secret key for session
app.config['SECRET_KEY'] = 'your-secret-key-noor-jewelry'


def ensure_admin():
    user_id = session.get("user_id")
    if not user_id:
        return None, redirect(url_for("login_register"))

    user = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if not user or user["role"] != "admin":
        flash("Access denied. Admin privileges required.", "error")
        return None, redirect(url_for("my_account"))

    return user, None


def ensure_user_status_column():
    try:
        with db_session() as conn:
            conn.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'")
    except sqlite3.OperationalError:
        pass
    except Exception:
        pass


def save_uploaded_image(upload_file):
    if upload_file and upload_file.filename:
        filename = secure_filename(upload_file.filename)
        upload_folder = os.path.join('static', 'assets', 'img', 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        upload_file.save(file_path)
        return os.path.join('assets', 'img', 'uploads', filename).replace('\\', '/')
    return None


@app.context_processor
def inject_cart():
    user_id = session.get("user_id")
    cart_items = []
    total_price = 0
    cart_count = 0
    
    if user_id:
        db_cart_items = query_db(
            """SELECT ci.product_id as id, ci.quantity, p.name, p.price, p.image 
               FROM cart_items ci
               JOIN products p ON ci.product_id = p.id
               WHERE ci.user_id = ?""",
            (user_id,)
        )
        for item in db_cart_items:
            cart_items.append(item)
            total_price += item["price"] * item["quantity"]
            cart_count += item["quantity"]
    else:
        session_cart = session.get("cart", [])
        for item in session_cart:
            product = query_db("SELECT id, name, price, image FROM products WHERE id = ?", (item["product_id"],), one=True)
            if product:
                product_with_qty = dict(product)
                product_with_qty["quantity"] = item["quantity"]
                cart_items.append(product_with_qty)
                total_price += product["price"] * item["quantity"]
                cart_count += item["quantity"]
                
    return dict(global_cart_items=cart_items, global_cart_total=total_price, global_cart_count=cart_count)

@app.route('/')
@app.route('/index')
def index():
    # Get featured products for homepage
    featured_products = query_db("SELECT * FROM products LIMIT 8")
    # Get new products (most recent by ID)
    new_products = query_db("SELECT * FROM products ORDER BY id DESC LIMIT 8")
    return render_template('index.html', featured_products=featured_products, new_products=new_products)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/shop")
def shop():
    return redirect(url_for('shop_left_full_wide'))

@app.route("/shop-left-full-wide")
def shop_left_full_wide():
    products = query_db("SELECT * FROM products")
    return render_template("shop-left-full-wide.html", products=products)

@app.route("/categories")
def categories():
    return render_template("categories.html")

@app.route("/category/<category>")
def category_detail(category):
    normalized_category = category.strip().lower()
    products = query_db("SELECT * FROM products WHERE LOWER(category) = ?", (normalized_category,))
    return render_template("category-detail.html", category=category, products=products)

@app.route("/single-product")
def single_product():
    # Redirect to the first available product
    first_product = query_db("SELECT id FROM products ORDER BY id LIMIT 1", one=True)
    if first_product:
        return redirect(url_for('single_product_detail', product_id=first_product['id']))
    return render_template("single-product.html")

@app.route("/single-product-normal")
def single_product_normal():
    return render_template("single-product-normal.html")

@app.route("/single-product-external")
def single_product_external():
    return render_template("single-product-external.html")

@app.route("/single-product-group")
def single_product_group():
    return render_template("single-product-group.html")

@app.route("/add-to-cart", methods=["GET", "POST"])
def add_to_cart():
    product_id = request.form.get("product_id") or request.args.get("product_id")
    quantity = int(request.form.get("quantity", 1) or request.args.get("quantity", 1))
    
    if not product_id:
        return {"error": "Product ID required"}, 400
    
    # Check if product exists
    product = query_db("SELECT * FROM products WHERE id = ?", (product_id,), one=True)
    if not product:
        return {"error": "Product not found"}, 404
    
    user_id = session.get("user_id")
    
    if user_id:
        # Logged in: Save to database
        existing_item = query_db(
            "SELECT * FROM cart_items WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
            one=True
        )
        
        if existing_item:
            # Update quantity
            with db_session() as conn:
                conn.execute(
                    "UPDATE cart_items SET quantity = quantity + ? WHERE user_id = ? AND product_id = ?",
                    (quantity, user_id, product_id)
                )
        else:
            # Add new item
            insert_db(
                "INSERT INTO cart_items (user_id, product_id, product_name, quantity, added_date) VALUES (?, ?, ?, ?, ?)",
                (user_id, product_id, product["name"], quantity, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
        return redirect(url_for("cart"))
    else:
        # Not logged in: Use session cart
        cart = session.get("cart", [])
        
        # Check if product already in cart
        product_in_cart = False
        for item in cart:
            if item["product_id"] == int(product_id):
                item["quantity"] += quantity
                product_in_cart = True
                break
        
        if not product_in_cart:
            cart.append({
                "product_id": int(product_id),
                "quantity": quantity
            })
        
        session["cart"] = cart
        session.modified = True
        return redirect(url_for("cart"))


@app.route("/remove-from-cart/<int:product_id>", methods=["GET"])
def remove_from_cart(product_id):
    user_id = session.get("user_id")
    
    if user_id:
        # Remove from database
        with db_session() as conn:
            conn.execute("DELETE FROM cart_items WHERE user_id = ? AND product_id = ?", (user_id, product_id))
    else:
        # Remove from session cart
        cart = session.get("cart", [])
        session["cart"] = [item for item in cart if item["product_id"] != product_id]
        session.modified = True
    
    return redirect(url_for("cart"))


@app.route("/update-cart-quantity/<int:product_id>", methods=["POST"])
def update_cart_quantity(product_id):
    quantity = int(request.form.get("quantity", 1))
    user_id = session.get("user_id")
    
    if quantity <= 0:
        return redirect(url_for("remove_from_cart", product_id=product_id))
    
    if user_id:
        # Update in database
        with db_session() as conn:
            conn.execute(
                "UPDATE cart_items SET quantity = ? WHERE user_id = ? AND product_id = ?",
                (quantity, user_id, product_id)
            )
    else:
        # Update in session cart
        cart = session.get("cart", [])
        for item in cart:
            if item["product_id"] == product_id:
                item["quantity"] = quantity
                break
        session["cart"] = cart
        session.modified = True
    
    return redirect(url_for("cart"))



@app.route("/cart")
def cart():
    user_id = session.get("user_id")
    cart_items = []
    total_price = 0

    if user_id:
        # Get cart items from database
        db_cart_items = query_db(
            """SELECT p.*, ci.quantity 
               FROM cart_items ci
               JOIN products p ON ci.product_id = p.id
               WHERE ci.user_id = ?""",
            (user_id,)
        )
        for item in db_cart_items:
            cart_items.append(item)
            total_price += item["price"] * item["quantity"]
    else:
        # Get cart items from session
        session_cart = session.get("cart", [])
        for item in session_cart:
            product = query_db("SELECT * FROM products WHERE id = ?", (item["product_id"],), one=True)
            if product:
                # Create a combined object with quantity info
                product_with_qty = dict(product)
                product_with_qty["quantity"] = item["quantity"]
                cart_items.append(product_with_qty)
                total_price += product["price"] * item["quantity"]

    return render_template("cart.html", products=cart_items, total=total_price)

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    user_id = session.get("user_id")

    if request.method == "POST":
        # Get form data
        customer_name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        address = request.form.get("address")
        city = request.form.get("city")
        postal_code = request.form.get("postal_code")
        payment_method = request.form.get("paymentmethod", "cash")

        # Validation
        if not all([customer_name, email, phone, address, city, postal_code]):
            return render_template("checkout.html", error="Please fill all fields", products=[], total=0)

        # Get cart items
        if user_id:
            cart_items = query_db(
                """SELECT ci.product_id, ci.quantity, p.name, p.price 
                   FROM cart_items ci
                   JOIN products p ON ci.product_id = p.id
                   WHERE ci.user_id = ?""",
                (user_id,)
            )
        else:
            session_cart = session.get("cart", [])
            cart_items = []
            for item in session_cart:
                product = query_db("SELECT * FROM products WHERE id = ?", (item["product_id"],), one=True)
                if product:
                    cart_items.append({
                        "product_id": product["id"],
                        "quantity": item["quantity"],
                        "name": product["name"],
                        "price": product["price"]
                    })

        if not cart_items:
            return render_template("checkout.html", error="Cart is empty", products=[], total=0)

        # Calculate total and create items JSON
        total = sum(item["price"] * item["quantity"] for item in cart_items)
        items_json = json.dumps([dict(item) for item in cart_items])

        # Save order to database
        try:
            insert_db(
                """INSERT INTO orders (user_id, customer_name, email, phone, address, city, postal_code, items, total, status, payment_method, created_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, customer_name, email, phone, address, city, postal_code, items_json, total, "Processing", payment_method, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )

            # Clear cart (Commented out so that the cart_items remain in database as requested)
            # if user_id:
            #     with db_session() as conn:
            #         conn.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
            # else:
            #     session["cart"] = []
            #     session.modified = True

            return render_template("checkout.html", success="Order placed successfully! Thank you for your purchase.", products=[], total=0)
        except Exception as e:
            return render_template("checkout.html", error=f"Error processing order: {str(e)}", products=[], total=0)

    # GET request - show checkout form with cart items
    cart_items = []
    total_price = 0

    if user_id:
        db_cart_items = query_db(
            """SELECT p.*, ci.quantity 
               FROM cart_items ci
               JOIN products p ON ci.product_id = p.id
               WHERE ci.user_id = ?""",
            (user_id,)
        )
        for item in db_cart_items:
            cart_items.append(item)
            total_price += item["price"] * item["quantity"]
    else:
        session_cart = session.get("cart", [])
        for item in session_cart:
            product = query_db("SELECT * FROM products WHERE id = ?", (item["product_id"],), one=True)
            if product:
                product_with_qty = dict(product)
                product_with_qty["quantity"] = item["quantity"]
                cart_items.append(product_with_qty)
                total_price += product["price"] * item["quantity"]

    user = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True) if user_id else None

    return render_template("checkout.html", products=cart_items, total=total_price, user=user)

@app.route("/compare")
def compare():
    return render_template("compare.html")

@app.route("/wishlist")
def wishlist():
    return render_template("wishlist.html")

@app.route("/login-register", methods=["GET", "POST"])
def login_register():
    error = None
    success = None

    if request.method == "POST":
        action = request.form.get("action")

        if action == "login":
            # ========== LOGIN LOGIC ==========
            email = request.form.get("email")
            password = request.form.get("password")

            if not email or not password:
                error = "Please provide both email and password"
            else:
                # Check if user exists
                user = query_db("SELECT * FROM users WHERE email = ?", (email,), one=True)
                
                if user and check_password_hash(user["password_hash"], password):
                    # Login successful - set session
                    session["user_id"] = user["id"]
                    session["user_name"] = user["name"]
                    session["user_email"] = user["email"]
                    
                    # Merge session cart into database
                    session_cart = session.get("cart", [])
                    if session_cart:
                        for item in session_cart:
                            existing_item = query_db(
                                "SELECT * FROM cart_items WHERE user_id = ? AND product_id = ?",
                                (user["id"], item["product_id"]),
                                one=True
                            )
                            if existing_item:
                                with db_session() as conn:
                                    conn.execute(
                                        "UPDATE cart_items SET quantity = quantity + ? WHERE user_id = ? AND product_id = ?",
                                        (item["quantity"], user["id"], item["product_id"])
                                    )
                            else:
                                product_info = query_db("SELECT name FROM products WHERE id = ?", (item["product_id"],), one=True)
                                product_name = product_info["name"] if product_info else "Unknown Product"
                                insert_db(
                                    "INSERT INTO cart_items (user_id, product_id, product_name, quantity, added_date) VALUES (?, ?, ?, ?, ?)",
                                    (user["id"], item["product_id"], product_name, item["quantity"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                )
                        session.pop("cart", None)

                    # Redirect admin users to admin dashboard, others to my account
                    if user["role"] == "admin":
                        return redirect(url_for("admin_dashboard"))
                    else:
                        return redirect(url_for("my_account"))
                else:
                    error = "Invalid email or password - User not registered"

        elif action == "register":
            # ========== REGISTER LOGIC ==========
            name = request.form.get("name")
            email = request.form.get("email")
            password = request.form.get("password")
            confirm_password = request.form.get("confirm_password")

            # Validation
            if not all([name, email, password, confirm_password]):
                error = "Please fill in all fields"
            elif password != confirm_password:
                error = "Passwords do not match"
            elif len(password) < 6:
                error = "Password must be at least 6 characters"
            else:
                # Check if user already exists
                existing_user = query_db('SELECT * FROM users WHERE email = ?', (email,), one=True)
                if existing_user:
                    error = "Email already registered - Please login"
                else:
                    # Hash password and insert new user
                    try:
                        password_hash = generate_password_hash(password)
                        insert_db(
                            'INSERT INTO users (name, email, password_hash, role, preferences) VALUES (?, ?, ?, ?, ?)',
                            (name, email, password_hash, 'customer', json.dumps([]))
                        )
                        success = "Registration successful! Please login with your email and password."
                    except Exception as e:
                        error = f"Registration failed: {str(e)}"

    return render_template("login-register.html", error=error, success=success)
        # ---------------- REGISTER ----------------


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("index"))

@app.route("/my-account")
def my_account():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login_register"))

    user = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    # Show only orders associated with this user account
    orders = query_db("SELECT * FROM orders WHERE user_id = ?", (user_id,))

    # Convert to list of dicts and parse items JSON for each order
    orders_list = []
    for order in orders:
        order_dict = dict(order)  # Convert sqlite3.Row to dict
        if order_dict["items"]:
            try:
                order_dict["parsed_items"] = json.loads(order_dict["items"])
            except (ValueError, TypeError):
                order_dict["parsed_items"] = []
        else:
            order_dict["parsed_items"] = []
        orders_list.append(order_dict)

    return render_template("my-account.html", user=user, orders=orders_list)



@app.route("/admin/dashboard")
def admin_dashboard():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login_register"))

    # Check if user is admin
    user = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if user["role"] != "admin":
        flash("Access denied. Admin privileges required.", "error")
        return redirect(url_for("my_account"))

    # Get dashboard statistics
    total_products = query_db("SELECT COUNT(*) as count FROM products", one=True)["count"]
    total_orders = query_db("SELECT COUNT(*) as count FROM orders", one=True)["count"]
    total_users = query_db("SELECT COUNT(*) as count FROM users", one=True)["count"]
    total_reviews = query_db("SELECT COUNT(*) as count FROM reviews", one=True)["count"]
    total_cart_items = query_db("SELECT COUNT(*) as count FROM cart_items", one=True)["count"]
    total_revenue = query_db("SELECT SUM(total) as revenue FROM orders WHERE status = 'Completed'", one=True)["revenue"] or 0

    # Get recent orders
    recent_orders = query_db("SELECT * FROM orders ORDER BY created_date DESC LIMIT 5")

    return render_template("admin-dashboard.html",
                         total_products=total_products,
                         total_orders=total_orders,
                         total_users=total_users,
                         total_reviews=total_reviews,
                         total_cart_items=total_cart_items,
                         total_revenue=total_revenue,
                         recent_orders=recent_orders)



@app.route("/admin/products")
def admin_products():
    user, redirect_response = ensure_admin()
    if redirect_response:
        return redirect_response

    view_id = request.args.get("view_id", type=int)
    edit_id = request.args.get("edit_id", type=int)

    selected_product = query_db("SELECT * FROM products WHERE id = ?", (view_id,), one=True) if view_id else None
    edit_product = query_db("SELECT * FROM products WHERE id = ?", (edit_id,), one=True) if edit_id else None
    products = query_db("SELECT * FROM products ORDER BY id DESC")

    return render_template("admin-products.html", products=products, selected_product=selected_product, edit_product=edit_product)


@app.route("/admin/products/add", methods=["POST"])
def admin_add_product():
    user, redirect_response = ensure_admin()
    if redirect_response:
        return redirect_response

    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    price = float(request.form.get("price", 0) or 0)
    quantity = int(request.form.get("quantity", 0) or 0)
    material = request.form.get("material", "").strip()
    stone = request.form.get("stone", "").strip()
    short_description = request.form.get("short_description", "").strip()
    long_description = request.form.get("long_description", "").strip()
    image_file = request.files.get("image")
    image_path = save_uploaded_image(image_file) or "assets/img/product-1.jpg"

    insert_db(
        "INSERT INTO products (name, category, price, quantity, total_amount, gender, material, stone, short_description, long_description, image) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (name, category, price, quantity, price * quantity, "", material, stone, short_description, long_description, image_path)
    )

    flash("Product added successfully.", "success")
    return redirect(url_for("admin_products"))


@app.route("/admin/products/edit/<int:product_id>", methods=["POST"])
def admin_edit_product(product_id):
    user, redirect_response = ensure_admin()
    if redirect_response:
        return redirect_response

    product = query_db("SELECT * FROM products WHERE id = ?", (product_id,), one=True)
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("admin_products"))

    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    price = float(request.form.get("price", 0) or 0)
    quantity = int(request.form.get("quantity", 0) or 0)
    material = request.form.get("material", "").strip()
    stone = request.form.get("stone", "").strip()
    short_description = request.form.get("short_description", "").strip()
    long_description = request.form.get("long_description", "").strip()
    image_file = request.files.get("image")
    image_path = save_uploaded_image(image_file) or request.form.get("existing_image") or product["image"]

    with db_session() as conn:
        conn.execute(
            "UPDATE products SET name = ?, category = ?, price = ?, quantity = ?, total_amount = ?, material = ?, stone = ?, short_description = ?, long_description = ?, image = ? WHERE id = ?",
            (name, category, price, quantity, price * quantity, material, stone, short_description, long_description, image_path, product_id)
        )

    flash("Product updated successfully.", "success")
    return redirect(url_for("admin_products"))


@app.route("/admin/products/delete/<int:product_id>", methods=["POST"])
def admin_delete_product(product_id):
    user, redirect_response = ensure_admin()
    if redirect_response:
        return redirect_response

    with db_session() as conn:
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))

    flash("Product deleted successfully.", "success")
    return redirect(url_for("admin_products"))


@app.route("/admin/users")
def admin_users():
    user, redirect_response = ensure_admin()
    if redirect_response:
        return redirect_response

    ensure_user_status_column()

    view_id = request.args.get("view_id", type=int)
    edit_id = request.args.get("edit_id", type=int)

    selected_user = query_db("SELECT * FROM users WHERE id = ?", (view_id,), one=True) if view_id else None
    edit_user = query_db("SELECT * FROM users WHERE id = ?", (edit_id,), one=True) if edit_id else None

    users = query_db("SELECT * FROM users ORDER BY id DESC")

    total_users = len(users)
    active_users = len([u for u in users if (u["status"] if "status" in u.keys() else "active") == "active"])
    new_users_month = total_users
    admin_users = len([u for u in users if u["role"] == "admin"])

    return render_template("admin-users.html",
                         users=users,
                         total_users=total_users,
                         active_users=active_users,
                         new_users_month=new_users_month,
                         admin_users=admin_users,
                         selected_user=selected_user,
                         edit_user=edit_user)


@app.route("/admin/users/add", methods=["POST"])
def admin_add_user():
    user, redirect_response = ensure_admin()
    if redirect_response:
        return redirect_response

    ensure_user_status_column()

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", "customer").strip()
    preferences = request.form.get("preferences", "").strip()
    status = request.form.get("status", "active").strip()

    if query_db("SELECT * FROM users WHERE email = ?", (email,), one=True):
        flash("A user with that email already exists.", "error")
        return redirect(url_for("admin_users"))

    try:
        preferences_json = json.loads(preferences) if preferences else []
    except Exception:
        preferences_json = []

    password_hash = generate_password_hash(password) if password else ""

    insert_db(
        "INSERT INTO users (name, email, password_hash, role, preferences, status) VALUES (?, ?, ?, ?, ?, ?)",
        (name, email, password_hash, role, json.dumps(preferences_json), status)
    )

    flash("User added successfully.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/edit/<int:user_id>", methods=["POST"])
def admin_edit_user(user_id):
    admin, redirect_response = ensure_admin()
    if redirect_response:
        return redirect_response

    ensure_user_status_column()

    user_to_edit = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if not user_to_edit:
        flash("User not found.", "error")
        return redirect(url_for("admin_users"))

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", "customer").strip()
    preferences = request.form.get("preferences", "").strip()
    status = request.form.get("status", "active").strip()

    try:
        preferences_json = json.loads(preferences) if preferences else []
    except Exception:
        preferences_json = []

    params = [name, email, role, json.dumps(preferences_json), status, user_id]
    if password:
        password_hash = generate_password_hash(password)
        with db_session() as conn:
            conn.execute(
                "UPDATE users SET name = ?, email = ?, password_hash = ?, role = ?, preferences = ?, status = ? WHERE id = ?",
                [name, email, password_hash, role, json.dumps(preferences_json), status, user_id]
            )
    else:
        with db_session() as conn:
            conn.execute(
                "UPDATE users SET name = ?, email = ?, role = ?, preferences = ?, status = ? WHERE id = ?",
                params
            )

    flash("User updated successfully.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
def admin_delete_user(user_id):
    user, redirect_response = ensure_admin()
    if redirect_response:
        return redirect_response

    user_to_delete = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if not user_to_delete:
        flash("User not found.", "error")
        return redirect(url_for("admin_users"))

    if user_to_delete["role"] == "admin":
        flash("Admin accounts cannot be deleted.", "error")
        return redirect(url_for("admin_users"))

    if user_to_delete["id"] == user["id"]:
        flash("You cannot delete your own admin account.", "error")
        return redirect(url_for("admin_users"))

    with db_session() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

    flash("User deleted successfully.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/orders")
def admin_orders():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login_register"))

    user = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if user["role"] != "admin":
        flash("Access denied. Admin privileges required.", "error")
        return redirect(url_for("my_account"))

    orders = query_db(
        "SELECT o.*, u.name as user_name, u.email as user_email FROM orders o LEFT JOIN users u ON o.user_id = u.id ORDER BY o.created_date DESC"
    )

    # Convert to list of dicts and parse items JSON for each order
    orders_list = []
    for order in orders:
        order_dict = dict(order)  # Convert sqlite3.Row to dict
        if order_dict["items"]:
            try:
                order_dict["parsed_items"] = json.loads(order_dict["items"])
            except (ValueError, TypeError):
                order_dict["parsed_items"] = []
        else:
            order_dict["parsed_items"] = []
        orders_list.append(order_dict)

    return render_template("admin-orders.html", orders=orders_list)

@app.route("/admin/cart-items")
def admin_cart_items():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login_register"))

    user = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if user["role"] != "admin":
        flash("Access denied. Admin privileges required.", "error")
        return redirect(url_for("my_account"))

    cart_items = query_db(
        """
        SELECT ci.*, u.name as user_name, u.email as user_email, p.name as product_name, p.price as product_price
        FROM cart_items ci
        LEFT JOIN users u ON ci.user_id = u.id
        LEFT JOIN products p ON ci.product_id = p.id
        ORDER BY ci.added_date DESC
        """,
    )

    return render_template("admin-cart-items.html", cart_items=cart_items)

@app.route("/admin/reviews")
def admin_reviews():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login_register"))

    user = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if user["role"] != "admin":
        flash("Access denied. Admin privileges required.", "error")
        return redirect(url_for("my_account"))

    reviews = query_db(
        """
        SELECT r.*, p.name as product_name, u.email as user_email
        FROM reviews r
        LEFT JOIN products p ON r.product_id = p.id
        LEFT JOIN users u ON r.user_id = u.id
        ORDER BY r.date DESC
        """
    )

    return render_template("admin-reviews.html", reviews=reviews)


@app.route("/blog")
def blog():
    return redirect(url_for('single_blog'))

@app.route("/single-blog")
def single_blog():
    return render_template("single-blog.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/404")
def error_404():
    return render_template("404.html")

@app.route("/single-product/<int:product_id>")
def single_product_detail(product_id):
    product = query_db("SELECT * FROM products WHERE id = ?", (product_id,), one=True)
    if not product:
        return redirect(url_for("error_404"))
    
    # Get reviews for this product
    reviews = query_db("SELECT * FROM reviews WHERE product_id = ? ORDER BY date DESC", (product_id,))
    
    # Calculate average rating
    if reviews:
        total_rating = sum(review["rating"] for review in reviews)
        avg_rating = total_rating / len(reviews)
        review_count = len(reviews)
    else:
        avg_rating = 0
        review_count = 0

    recommendations = get_recommended_products(product_id, product["name"], top_n=5)
    
    return render_template(
        "single-product.html",
        product=product,
        reviews=reviews,
        avg_rating=avg_rating,
        review_count=review_count,
        recommendations=recommendations
    )

@app.route("/submit-review/<int:product_id>", methods=["POST"])
def submit_review(product_id):
    user_id = session.get("user_id")
    if not user_id:
        flash("Please login to submit a review", "error")
        return redirect(url_for("login_register"))
    
    # Check if product exists
    product = query_db("SELECT * FROM products WHERE id = ?", (product_id,), one=True)
    if not product:
        return redirect(url_for("error_404"))
    
    # Get form data
    rating = int(request.form.get("rating", 5))
    comment = request.form.get("comment", "").strip()
    
    if not comment:
        flash("Please provide a review comment", "error")
        return redirect(url_for("single_product_detail", product_id=product_id))
    
    # Get user info
    user = query_db("SELECT name FROM users WHERE id = ?", (user_id,), one=True)
    user_name = user["name"] if user else "Anonymous"
    
    # Insert review
    try:
        insert_db(
            "INSERT INTO reviews (product_id, user_id, user_name, rating, comment, date) VALUES (?, ?, ?, ?, ?, ?)",
            (product_id, user_id, user_name, rating, comment, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        flash("Review submitted successfully!", "success")
    except Exception as e:
        flash(f"Error submitting review: {str(e)}", "error")
    
    return redirect(url_for("single_product_detail", product_id=product_id))

@app.route("/my-reviews")
def my_reviews():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login_register"))
    
    reviews = query_db("SELECT r.*, p.name as product_name, p.image FROM reviews r JOIN products p ON r.product_id = p.id WHERE r.user_id = ? ORDER BY r.date DESC", (user_id,))
    
    return render_template("my-reviews.html", reviews=reviews)


if __name__ == '__main__':
    app.run(debug=True)
