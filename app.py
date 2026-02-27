from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3, hashlib, os, json
from datetime import datetime

app = Flask(__name__, static_folder='static')
CORS(app)

DB = 'moda.db'

# ===== DATABASE INIT =====
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            brand TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            old_price REAL,
            emoji TEXT DEFAULT '👕',
            stars INTEGER DEFAULT 5,
            badge TEXT,
            description TEXT,
            stock INTEGER DEFAULT 100,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_num TEXT UNIQUE NOT NULL,
            user_name TEXT NOT NULL,
            user_email TEXT,
            items TEXT NOT NULL,
            total REAL NOT NULL,
            status TEXT DEFAULT 'معلق',
            address TEXT,
            phone TEXT,
            payment_method TEXT DEFAULT 'cash',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    # Seed admin user
    admin_pass = hashlib.sha256('admin123'.encode()).hexdigest()
    c.execute("INSERT OR IGNORE INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
              ('أدمن المتجر', 'admin@moda.com', admin_pass, 'admin'))

    # Seed products
    seed_products = [
        ('قميص أكسفورد كلاسيك',   'MODA Classic', 'رسمي',   450,  600,  '👔', 5, 'جديد',  'قميص رجالي فاخر من القطن المصري 100%'),
        ('بنطلون جينز سليم فيت',   'MODA Jeans',   'كاجوال', 380,  None, '👖', 4, None,    'جينز عالي الجودة بقصة عصرية'),
        ('جاكيت جلد كلاسيك',       'MODA Classic', 'كاجوال', 1850, 2200, '🧥', 4, 'sale',  'جاكيت جلد طبيعي بتصميم كلاسيك'),
        ('تيشيرت بريمويم كوتون',   'MODA Basic',   'كاجوال', 220,  300,  '👕', 5, 'sale',  'تيشيرت قطن عالي الجودة'),
        ('بدلة رسمية كاملة',        'MODA Suit',    'رسمي',   2800, None, '🤵', 5, 'جديد',  'بدلة رجالية كاملة للمناسبات'),
        ('تراكسوت سبور',            'MODA Sport',   'سبور',   650,  850,  '🏃', 4, 'sale',  'تراكسوت خفيف ومريح للرياضة'),
        ('شورت سبور درايفت',        'MODA Sport',   'سبور',   195,  250,  '🩳', 5, None,    'شورت رياضي خفيف ومريح'),
        ('كنزة صوف شتوية',          'MODA Winter',  'كاجوال', 520,  700,  '🧶', 4, 'sale',  'كنزة صوف دافئة للشتاء'),
        ('قميص هاواي كاجوال',       'MODA Casual',  'كاجوال', 310,  None, '🌺', 4, None,    'قميص كاجوال مميز للسهرات'),
        ('بنطلون تشينو رسمي',       'MODA Classic', 'رسمي',   480,  600,  '👖', 5, 'جديد',  'بنطلون تشينو أنيق للإطلالات الرسمية'),
        ('تيشيرت بولو فاخر',        'MODA Polo',    'رسمي',   340,  420,  '🏅', 5, None,    'بولو قطن بيما فاخر'),
        ('هودي رياضي',              'MODA Sport',   'سبور',   580,  None, '🧥', 4, 'جديد',  'هودي رياضي دافئ ومريح'),
    ]
    c.executemany(
        "INSERT OR IGNORE INTO products (name, brand, category, price, old_price, emoji, stars, badge, description) VALUES (?,?,?,?,?,?,?,?,?)",
        seed_products
    )

    conn.commit()
    conn.close()


# ===== HELPERS =====
def hash_pass(p): return hashlib.sha256(p.encode()).hexdigest()

def product_dict(row):
    return {
        'id': row['id'], 'name': row['name'], 'brand': row['brand'],
        'category': row['category'], 'price': row['price'],
        'old_price': row['old_price'], 'emoji': row['emoji'],
        'stars': row['stars'], 'badge': row['badge'],
        'description': row['description'], 'stock': row['stock'],
        'created_at': row['created_at']
    }


# ===== ROUTES: STATIC =====
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


# ===== ROUTES: AUTH =====
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    name  = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    pwd   = data.get('password', '')
    if not name or not email or not pwd:
        return jsonify({'error': 'جميع الحقول مطلوبة'}), 400
    if len(pwd) < 6:
        return jsonify({'error': 'كلمة المرور قصيرة جداً'}), 400
    conn = get_db()
    try:
        conn.execute("INSERT INTO users (name, email, password) VALUES (?,?,?)",
                     (name, email, hash_pass(pwd)))
        conn.commit()
        return jsonify({'message': 'تم إنشاء الحساب بنجاح'})
    except sqlite3.IntegrityError:
        return jsonify({'error': 'هذا البريد مسجل بالفعل'}), 409
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data  = request.json
    email = data.get('email', '').strip().lower()
    pwd   = data.get('password', '')
    conn  = get_db()
    user  = conn.execute("SELECT * FROM users WHERE email=? AND password=?",
                         (email, hash_pass(pwd))).fetchone()
    conn.close()
    if not user:
        return jsonify({'error': 'بيانات الدخول غير صحيحة'}), 401
    return jsonify({'id': user['id'], 'name': user['name'],
                    'email': user['email'], 'role': user['role']})


# ===== ROUTES: PRODUCTS =====
@app.route('/api/products', methods=['GET'])
def get_products():
    category = request.args.get('category')
    sale     = request.args.get('sale')
    conn     = get_db()
    if category and category != 'الكل':
        rows = conn.execute("SELECT * FROM products WHERE category=? ORDER BY id DESC", (category,)).fetchall()
    elif sale:
        rows = conn.execute("SELECT * FROM products WHERE badge='sale' ORDER BY id DESC").fetchall()
    else:
        rows = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    conn.close()
    return jsonify([product_dict(r) for r in rows])

@app.route('/api/products', methods=['POST'])
def add_product():
    d = request.json
    name  = d.get('name','').strip()
    brand = d.get('brand','').strip()
    cat   = d.get('category','').strip()
    price = d.get('price')
    if not name or not brand or not cat or not price:
        return jsonify({'error': 'يرجى ملء جميع الحقول'}), 400
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO products (name, brand, category, price, old_price, emoji, stars, badge, description, stock) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (name, brand, cat, float(price),
         d.get('old_price'), d.get('emoji','👕'),
         int(d.get('stars', 5)), d.get('badge'),
         d.get('description',''), int(d.get('stock', 100)))
    )
    conn.commit()
    row = conn.execute("SELECT * FROM products WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(product_dict(row)), 201

@app.route('/api/products/<int:pid>', methods=['PUT'])
def update_product(pid):
    d = request.json
    conn = get_db()
    conn.execute(
        "UPDATE products SET name=?, brand=?, category=?, price=?, old_price=?, emoji=?, stars=?, badge=?, description=?, stock=? WHERE id=?",
        (d['name'], d['brand'], d['category'], d['price'], d.get('old_price'),
         d.get('emoji','👕'), d.get('stars',5), d.get('badge'),
         d.get('description',''), d.get('stock',100), pid)
    )
    conn.commit()
    conn.close()
    return jsonify({'message': 'تم التحديث'})

@app.route('/api/products/<int:pid>', methods=['DELETE'])
def delete_product(pid):
    conn = get_db()
    conn.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'تم الحذف'})


# ===== ROUTES: ORDERS =====
@app.route('/api/orders', methods=['GET'])
def get_orders():
    conn  = get_db()
    rows  = conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/orders', methods=['POST'])
def create_order():
    d          = request.json
    order_num  = '#' + str(1000 + int(datetime.now().timestamp()) % 9000)
    items_json = json.dumps(d.get('items', []), ensure_ascii=False)
    conn = get_db()
    conn.execute(
        "INSERT INTO orders (order_num, user_name, user_email, items, total, address, phone, payment_method) VALUES (?,?,?,?,?,?,?,?)",
        (order_num, d.get('user_name','ضيف'), d.get('user_email',''),
         items_json, d['total'], d.get('address',''), d.get('phone',''), d.get('payment_method','cash'))
    )
    conn.commit()
    conn.close()
    return jsonify({'order_num': order_num, 'message': 'تم الطلب بنجاح'}), 201

@app.route('/api/orders/<int:oid>/status', methods=['PUT'])
def update_order_status(oid):
    status = request.json.get('status')
    conn   = get_db()
    conn.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
    conn.commit()
    conn.close()
    return jsonify({'message': 'تم تحديث الحالة'})


# ===== ROUTES: STATS =====
@app.route('/api/stats', methods=['GET'])
def get_stats():
    conn     = get_db()
    products = conn.execute("SELECT COUNT(*) as c FROM products").fetchone()['c']
    users    = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()['c']
    orders   = conn.execute("SELECT COUNT(*) as c FROM orders").fetchone()['c']
    revenue  = conn.execute("SELECT COALESCE(SUM(total),0) as s FROM orders WHERE status != 'ملغي'").fetchone()['s']
    conn.close()
    return jsonify({'products': products, 'users': users, 'orders': orders, 'revenue': revenue})


if __name__ == '__main__':
    init_db()
    print("✅ MODA Store running on http://localhost:5000")
    app.run(debug=True, port=5000)
