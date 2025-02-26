from collections import defaultdict
from flask import Flask, flash, json, jsonify, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
from werkzeug.utils import secure_filename
import os
from datetime import timedelta
app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MySQL Bağlantı Ayarları
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'restaurant_db'
mysql = MySQL(app)

app.secret_key = 'gizli_anahtar'  # Güvenlik için gerekli
app.permanent_session_lifetime = timedelta(minutes=30)  # 30 dakika sonra oturum sonlanır

# Resim Yükleme Ayarları
app.config['UPLOAD_FOLDER'] = 'static/uploads'  # Yüklenen dosyalar bu klasöre kaydedilecek
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}  # İzin verilen dosya uzantıları

# Dosya uzantısını kontrol etme fonksiyonu
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Anasayfa
@app.route('/')
def index():
    cursor = mysql.connection.cursor()

    # Kategorileri çek
    cursor.execute("SELECT id, name FROM categories")
    categories = cursor.fetchall()

    # Ürünleri ve kategorileri çek
    cursor.execute("""
        SELECT products.id, products.name, products.description, products.price, 
            products.image_url, products.category_id, categories.name AS category_name 
        FROM products 
        JOIN categories ON products.category_id = categories.id
    """)
    products = cursor.fetchall()

    # Logo URL'sini çek
    cursor.execute("SELECT logo_url FROM settings WHERE id = 1")
    logo_data = cursor.fetchone()
    
    logo_url = logo_data[0] if logo_data else "/static/default-logo.png"

    cursor.close()

    # Kategorilere göre ürünleri ayır ve boş olanları filtrele
    categorized_products = {}
    for category in categories:
        category_id, category_name = category
        category_products = [product for product in products if product[5] == category_id]
        
        if category_products:  # Eğer bu kategoride ürün varsa ekle
            categorized_products[category_name] = category_products

    return render_template('index.html', products=products, logo_url=logo_url, categorized_products=categorized_products)



# Admin Giriş Sayfası
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM admins WHERE username = %s AND password = %s", (username, password))
        admin = cursor.fetchone()
        if admin:
            session['admin_id'] = admin[0]  # Admin'in id'sini session'a kaydediyoruz
            return redirect(url_for('admin_dashboard'))
        else:
            return "Kullanıcı adı veya şifre yanlış!"
    return render_template('login.html')

# Admin Paneli - Dashboard
@app.route('/admin_dashboard')
def admin_dashboard():

    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT products.id, products.name, products.description, products.price, 
            products.image_url, categories.name AS category_name 
        FROM products 
        JOIN categories ON products.category_id = categories.id
    """)
    products = cursor.fetchall()
    

    
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    cursor = mysql.connection.cursor()
    
    cursor.execute("SELECT * FROM categories")
    categories = cursor.fetchall()
    return render_template('admin_dashboard.html', products=products, categories=categories)

# Domain Güncelleme
@app.route('/admin_update_domain', methods=['GET', 'POST'])
def admin_update_domain():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        domain = request.form['domain']
        cursor = mysql.connection.cursor()
        cursor.execute("UPDATE admins SET domain = %s WHERE id = %s", (domain, session['admin_id']))
        mysql.connection.commit()
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin_update_domain.html')

# Kategori Ekleme
@app.route('/add_category', methods=['GET', 'POST'])
def add_category():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        category_name = request.form['category_name']
        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO categories (name) VALUES (%s)", (category_name,))
        mysql.connection.commit()
        return redirect(url_for('admin_dashboard'))
    
    return render_template('add_category.html')

# Yeni Ürün Ekleme
@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM categories")
    categories = cursor.fetchall()
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = request.form['price']
        category_id = request.form['category_id']
        
        # Resim URL veya yerel dosya seçimi
        image_url = request.form['image_url']
        
        # Eğer yerel dosya yüklenmişse
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                image_url = url_for('static', filename=f'uploads/{filename}')  # URL'yi MySQL'e kaydediyoruz
        
        # Veritabanına yeni ürünü ekliyoruz
        cursor.execute("INSERT INTO products (name, description, price, category_id, image_url) VALUES (%s, %s, %s, %s, %s)",
                       (name, description, price, category_id, image_url))
        mysql.connection.commit()
        return redirect(url_for('admin_dashboard'))
    
    return render_template('add_product.html', categories=categories)

# Ürün Silme
@app.route('/delete_product/<int:id>')
def delete_product(id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM products WHERE id = %s", (id,))
    mysql.connection.commit()
    return redirect(url_for('admin_dashboard'))

# Kategori Silme
@app.route('/delete_category/<int:id>')
def delete_category(id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM categories WHERE id = %s", (id,))
    mysql.connection.commit()
    return redirect(url_for('admin_dashboard'))


@app.route('/place_order', methods=['POST'])
def place_order():
    if request.method == 'POST':
        data = request.json  # JSON verisini al
        cart = data.get('cart', [])
        table_number = data.get('table_number')  # Masa numarasını al

        if not cart:
            return jsonify({"error": "Sepet boş!"}), 400
        cursor = mysql.connection.cursor()
        if not table_number:
            return jsonify({"error": "Masa numarası gereklidir!"}), 400

        try:
            # Ürünleri tek satırda JSON formatında sakla
            items_str = json.dumps(cart, ensure_ascii=False)

            # Siparişi veritabanına ekle
            cursor.execute("INSERT INTO orders (table_number, items, status) VALUES (%s, %s, 'Beklemede')",
                           (table_number, items_str))
            mysql.connection.commit()

            return jsonify({"success": "Siparişiniz başarıyla alındı!"})
        except Exception as e:
            mysql.connection.rollback()
            return jsonify({"error": str(e)}), 500

# Admin Paneli - Siparişleri Listele
import json
from flask import render_template

import json
from datetime import datetime

@app.route('/admin_orders')
def admin_orders():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, table_number, items, status, created_at FROM orders ORDER BY table_number, created_at ASC")
    orders = cursor.fetchall()
    cursor.close()

    parsed_orders = []
    for order in orders:
        order_id, table_number, items_json, status, created_at = order

        # Eğer items JSON string ise, parse edelim
        try:
            items = json.loads(items_json) if items_json else []
        except json.JSONDecodeError:
            items = []

        # Eğer created_at string olarak geldiyse datetime nesnesine çevirelim
        if isinstance(created_at, str):
            created_at = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")

        parsed_orders.append({
            "order_ids": [order_id], 
            "table_number": table_number, 
            "items": items, 
            "total_price": round(sum(float(i['price']) * int(i['quantity']) for i in items), 2),  # Burada virgül doğru yerde olmalı

            "status": status, 
            "created_at": created_at
        })

    return render_template('admin_orders.html', orders=parsed_orders)






# Admin - Sipariş Durumunu Güncelle (Teslim Edildi)
@app.route('/update_order_status/<int:order_id>', methods=['POST'])
def update_order_status(order_id):
    if 'admin_id' not in session:
        return jsonify({"error": "Yetkisiz erişim!"}), 403

    cursor = mysql.connection.cursor()

    # Önce siparişin var olup olmadığını kontrol et
    cursor.execute("SELECT id FROM orders WHERE id = %s", (order_id,))
    existing_order = cursor.fetchone()

    if not existing_order:
        cursor.close()
        return jsonify({"error": "Sipariş bulunamadı!"}), 404

    # Sipariş durumunu güncelle
    cursor.execute("UPDATE orders SET status = 'Teslim Edildi' WHERE id = %s", (order_id,))
    mysql.connection.commit()

    # Güncelleme başarılı oldu mu kontrol et
    if cursor.rowcount == 0:
        cursor.close()
        return jsonify({"error": "Sipariş durumu güncellenemedi!"}), 500

    cursor.close()
    return jsonify({"success": "Sipariş başarıyla güncellendi!"})












# Admin - LOGO
@app.route('/update_logo', methods=['POST'])
def update_logo():
    if 'logo' in request.files:
        logo = request.files['logo']
        if logo.filename != '':
            filename = secure_filename(logo.filename)
            logo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            logo.save(logo_path)
            cursor = mysql.connection.cursor()
            cursor.execute("UPDATE settings SET logo_url = %s WHERE id = 1", (url_for('static', filename=f'uploads/{filename}'),))
            mysql.connection.commit()
            cursor.close()
            return redirect(url_for('admin_dashboard'))
    return 'Logo yüklenemedi!'
#ÇIKIŞ YAP
@app.route('/logout')
def logout():
    session.pop('admin_id', None)  # Oturumu kapat
    return redirect(url_for('login'))  # Giriş sayfasına yönlendir


# ÜRÜN Düzenle
@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    cursor = mysql.connection.cursor()
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = request.form['price']
        category_id = request.form['category_id']
        image_url = request.form['image_url']  # Yeni URL al

        # Mevcut ürün bilgilerini çek (resmi kontrol etmek için)
        cursor.execute("SELECT image_url FROM products WHERE id = %s", (product_id,))
        old_product = cursor.fetchone()
        old_image = old_product[0] if old_product else None

        image_file = request.files['image']

        # Eğer dosya yüklendiyse
        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)
            image_url = '/' + image_path  # Yeni resmin yolu

        # Eğer ne URL ne de dosya girilmediyse, eski resim korunur
        if not image_url:
            image_url = old_image  

        cursor.execute("""
            UPDATE products 
            SET name = %s, description = %s, price = %s, category_id = %s, image_url = %s
            WHERE id = %s
        """, (name, description, price, category_id, image_url, product_id))
        
        mysql.connection.commit()
        cursor.close()
        return redirect('/admin_dashboard')

    # Mevcut ürün bilgilerini çek
    cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
    product = cursor.fetchone()

    # Kategori listesini çek
    cursor.execute("SELECT * FROM categories")
    categories = cursor.fetchall()

    cursor.close()

    return render_template('edit_product.html', product=product, categories=categories)


@app.route('/check_session')
def check_session():
    return jsonify({"session": dict(session)})

if __name__ == '__main__':
    app.run(debug=True)
