import os
import re
import sqlite3
import secrets
from datetime import datetime, timedelta
from decimal import Decimal
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get('SUSHIWAVE_DB', str(BASE / 'sushiwave.db')))
TZ = ZoneInfo('Europe/Kyiv')
app = Flask(__name__)
app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY', 'development-only-change-this-secret'), JSON_AS_ASCII=False, MAX_CONTENT_LENGTH=64*1024)

MENU = [
    ('Роли', 'Філадельфія класична', 'Лосось, сир вершковий, огірок, рис, норі', 289, '🍣', 'Лосось, молоко, риба'),
    ('Роли', 'Філадельфія з авокадо', 'Лосось, сир вершковий, авокадо, рис', 319, '🥑', 'Риба, молоко'),
    ('Роли', 'Каліфорнія з крабом', 'Сурімі, огірок, авокадо, ікра масаго', 249, '🦀', 'Риба, яйця, молюски'),
    ('Роли', 'Каліфорнія з креветкою', 'Креветка, авокадо, кунжут, рис', 279, '🍤', 'Ракоподібні, кунжут'),
    ('Роли', 'Золотий дракон', 'Вугор, огірок, унагі, кунжут', 349, '🐉', 'Риба, соя, кунжут'),
    ('Роли', 'Червоний дракон', 'Тунець, лосось, огірок, пікантний соус', 359, '🌶️', 'Риба, яйця'),
    ('Роли', 'Макі з огірком', 'Огірок, рис, норі, кунжут', 109, '🥒', 'Кунжут'),
    ('Роли', 'Макі з лососем', 'Лосось, рис, норі', 169, '🐟', 'Риба'),
    ('Роли', 'Темпура з креветкою', 'Креветка, крем-сир, панірування', 299, '🍤', 'Ракоподібні, молоко, глютен'),
    ('Роли', 'Запечений сирний рол', 'Сирний соус, лосось, рис, норі', 309, '🧀', 'Риба, молоко'),
    ('Суші', 'Нігірі лосось', 'Скибка лосося, рис, 2 шт.', 119, '🍣', 'Риба'),
    ('Суші', 'Нігірі тунець', 'Тунець, рис, 2 шт.', 129, '🐟', 'Риба'),
    ('Суші', 'Нігірі креветка', 'Креветка, рис, 2 шт.', 129, '🍤', 'Ракоподібні'),
    ('Суші', 'Гункан масаго', 'Ікра масаго, рис, норі, 2 шт.', 139, '🍙', 'Риба'),
    ('Сети', 'Сет SushiWave', 'Філадельфія, Каліфорнія, макі — 24 шт.', 749, '🍱', 'Риба, молоко, кунжут'),
    ('Сети', 'Сет для двох', 'Три авторські роли — 24 шт.', 849, '🍱', 'Риба, молоко, соя'),
    ('Сети', 'Великий сімейний сет', 'П’ять популярних ролів — 40 шт.', 1299, '🥢', 'Риба, молоко, кунжут'),
    ('Сети', 'Вегетаріанський сет', 'Макі огірок, авокадо, овочевий рол', 529, '🥑', 'Кунжут, соя'),
    ('Закуски', 'Місо-суп', 'Бульйон місо, тофу, водорості вакаме', 129, '🍲', 'Соя'),
    ('Закуски', 'Едамаме', 'Молоді соєві боби з морською сіллю', 119, '🫛', 'Соя'),
    ('Закуски', 'Креветки темпура', 'Креветки в хрусткому паніруванні, 5 шт.', 259, '🍤', 'Ракоподібні, глютен'),
    ('Закуски', 'Салат чука', 'Водорості чука, горіховий соус', 149, '🥗', 'Кунжут, горіхи'),
    ('Напої', 'Матча-лате', 'Японський зелений чай з молоком, 300 мл', 129, '🍵', 'Молоко'),
    ('Напої', 'Зелений чай', 'Листовий зелений чай, 400 мл', 69, '🍵', 'Не заявлені'),
    ('Напої', 'Лимонад юзу', 'Цитрусовий лимонад, 400 мл', 109, '🍋', 'Не заявлені'),
    ('Напої', 'Вода негазована', 'Мінеральна вода, 500 мл', 49, '💧', 'Не заявлені'),
]

MODIFIERS = [('Додатковий імбир', 20), ('Васабі', 15), ('Соєвий соус', 15), ('Палички (пара)', 0)]


def db():
    if 'db' not in g:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
        g.db.execute('PRAGMA busy_timeout = 5000')
    return g.db


@app.teardown_appcontext
def close_db(_error):
    conn = g.pop('db', None)
    if conn is not None:
        conn.close()


def init_db():
    conn = db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
        CREATE TABLE IF NOT EXISTS products(
            id INTEGER PRIMARY KEY, category_id INTEGER NOT NULL REFERENCES categories(id),
            name TEXT NOT NULL UNIQUE, description TEXT NOT NULL, price INTEGER NOT NULL CHECK(price>=0),
            emoji TEXT NOT NULL, allergens TEXT NOT NULL, available INTEGER NOT NULL DEFAULT 1 CHECK(available IN (0,1))
        );
        CREATE TABLE IF NOT EXISTS modifiers(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, price INTEGER NOT NULL CHECK(price>=0));
        CREATE TABLE IF NOT EXISTS operators(id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY, tracking_token TEXT NOT NULL UNIQUE, customer_name TEXT NOT NULL,
            phone TEXT NOT NULL, pickup_at TEXT NOT NULL, comment TEXT NOT NULL DEFAULT '',
            total INTEGER NOT NULL CHECK(total>=0), status TEXT NOT NULL DEFAULT 'Нове', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS order_items(
            id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id), product_id INTEGER NOT NULL REFERENCES products(id),
            product_name TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity>=1), unit_price INTEGER NOT NULL CHECK(unit_price>=0)
        );
        CREATE TABLE IF NOT EXISTS item_modifiers(
            id INTEGER PRIMARY KEY, order_item_id INTEGER NOT NULL REFERENCES order_items(id),
            modifier_name TEXT NOT NULL, price INTEGER NOT NULL CHECK(price>=0)
        );
        CREATE TABLE IF NOT EXISTS status_history(
            id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id), status TEXT NOT NULL, changed_at TEXT NOT NULL
        );
    ''')
    for name in ['Роли', 'Суші', 'Сети', 'Закуски', 'Напої']:
        conn.execute('INSERT OR IGNORE INTO categories(name) VALUES (?)', (name,))
    ids = {row['name']: row['id'] for row in conn.execute('SELECT * FROM categories')}
    for cat, name, description, price, emoji, allergens in MENU:
        conn.execute('''INSERT OR IGNORE INTO products(category_id,name,description,price,emoji,allergens)
                        VALUES (?,?,?,?,?,?)''', (ids[cat], name, description, price, emoji, allergens))
    for name, price in MODIFIERS:
        conn.execute('INSERT OR IGNORE INTO modifiers(name,price) VALUES (?,?)', (name, price))
    # Local development account only: replace password by environment variable before demonstration.
    username = os.environ.get('ADMIN_USER', 'operator')
    password = os.environ.get('ADMIN_PASSWORD', 'DemoSushi2026!')
    conn.execute('INSERT OR IGNORE INTO operators(username,password_hash) VALUES (?,?)',
                 (username, generate_password_hash(password)))
    conn.commit()


def now_kyiv():
    return datetime.now(TZ)


def menu_data():
    products = [dict(r) for r in db().execute('''SELECT p.*, c.name category FROM products p JOIN categories c ON c.id=p.category_id
                                                    ORDER BY c.id, p.id''')]
    return {'products': products, 'modifiers': [dict(r) for r in db().execute('SELECT * FROM modifiers')]}


@app.before_request
def csrf_check():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_urlsafe(32)
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        sent = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token', '')
        if not secrets.compare_digest(sent, session['csrf_token']):
            if request.is_json:
                return jsonify(error='Недійсний захисний токен. Оновіть сторінку.'), 403
            abort(403)


@app.context_processor
def inject_csrf():
    return {'csrf_token': session.get('csrf_token', '')}


def operator_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get('operator_id'):
            if request.path.startswith('/api/'):
                return jsonify(error='Потрібен вхід оператора'), 401
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapped


@app.route('/')
def index():
    return render_template('index.html')


@app.get('/api/menu')
def api_menu():
    return jsonify(menu_data())


def validate_order(payload):
    if not isinstance(payload, dict):
        raise ValueError('Неправильний формат даних')
    name = str(payload.get('name', '')).strip()
    phone = re.sub(r'[\s()\-]', '', str(payload.get('phone', '')))
    comment = str(payload.get('comment', '')).strip()
    if not 2 <= len(name) <= 80:
        raise ValueError('Ім’я повинно містити від 2 до 80 символів')
    if not re.fullmatch(r'\+?\d{10,13}', phone):
        raise ValueError('Вкажіть номер телефону з 10–13 цифр')
    if len(comment) > 300:
        raise ValueError('Коментар надто довгий')
    try:
        pickup = datetime.fromisoformat(str(payload.get('pickup_at', '')))
    except (TypeError, ValueError):
        raise ValueError('Оберіть дату й час отримання')
    if pickup.tzinfo is not None:
        raise ValueError('Введіть місцевий час отримання')
    pickup = pickup.replace(tzinfo=TZ)
    current = now_kyiv()
    if not current + timedelta(minutes=45) <= pickup <= current + timedelta(days=7):
        raise ValueError('Час отримання: від 45 хвилин до 7 днів від зараз')
    if not (11 <= pickup.hour < 21 or (pickup.hour == 21 and pickup.minute == 0)):
        raise ValueError('Замовлення видаємо з 11:00 до 21:00')
    if pickup.minute not in (0, 30) or pickup.second != 0:
        raise ValueError('Оберіть час з кроком 30 хвилин')
    lines = payload.get('items')
    if not isinstance(lines, list) or not 1 <= len(lines) <= 30:
        raise ValueError('Кошик порожній або містить забагато позицій')
    clean_items = []
    total = 0
    for item in lines:
        if not isinstance(item, dict) or type(item.get('id')) is not int or type(item.get('quantity')) is not int:
            raise ValueError('Некоректні дані позиції')
        quantity = item['quantity']
        if not 1 <= quantity <= 20:
            raise ValueError('Кількість кожної страви має бути від 1 до 20')
        product = db().execute('SELECT * FROM products WHERE id=?', (item['id'],)).fetchone()
        if not product or not product['available']:
            raise ValueError('Одна зі страв зараз недоступна')
        mids = item.get('modifiers', [])
        if not isinstance(mids, list) or len(mids) > 4 or any(type(m) is not int for m in mids) or len(set(mids)) != len(mids):
            raise ValueError('Некоректні додатки до страви')
        extras = []
        for mid in mids:
            modifier = db().execute('SELECT * FROM modifiers WHERE id=?', (mid,)).fetchone()
            if modifier is None:
                raise ValueError('Один із додатків не існує')
            extras.append(dict(modifier))
        unit = product['price'] + sum(m['price'] for m in extras)
        total += unit * quantity
        clean_items.append((dict(product), quantity, extras, unit))
    if total > 100000:
        raise ValueError('Замовлення перевищує ліміт навчального сервісу')
    return name, phone, pickup, comment, clean_items, total


@app.post('/api/orders')
def create_order():
    try:
        name, phone, pickup, comment, lines, total = validate_order(request.get_json(silent=True))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    token = secrets.token_urlsafe(24)
    created = now_kyiv().isoformat(timespec='seconds')
    conn = db()
    try:
        conn.execute('BEGIN IMMEDIATE')
        cur = conn.execute('''INSERT INTO orders(tracking_token,customer_name,phone,pickup_at,comment,total,status,created_at)
                              VALUES (?,?,?,?,?,?,?,?)''',
                           (token, name, phone, pickup.isoformat(timespec='minutes'), comment, total, 'Нове', created))
        order_id = cur.lastrowid
        for product, quantity, extras, unit in lines:
            item_cur = conn.execute('INSERT INTO order_items(order_id,product_id,product_name,quantity,unit_price) VALUES (?,?,?,?,?)',
                                    (order_id, product['id'], product['name'], quantity, unit))
            for modifier in extras:
                conn.execute('INSERT INTO item_modifiers(order_item_id,modifier_name,price) VALUES (?,?,?)',
                             (item_cur.lastrowid, modifier['name'], modifier['price']))
        conn.execute('INSERT INTO status_history(order_id,status,changed_at) VALUES (?,?,?)', (order_id, 'Нове', created))
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        return jsonify(error='Не вдалося зберегти замовлення'), 500
    return jsonify(id=order_id, total=total, tracking_url=url_for('track', token=token)), 201


def get_order_items(order_id):
    rows = [dict(x) for x in db().execute('SELECT * FROM order_items WHERE order_id=?', (order_id,))]
    for row in rows:
        row['modifiers'] = [dict(x) for x in db().execute('SELECT modifier_name,price FROM item_modifiers WHERE order_item_id=?', (row['id'],))]
    return rows


@app.get('/track/<token>')
def track(token):
    order = db().execute('SELECT * FROM orders WHERE tracking_token=?', (token,)).fetchone()
    if order is None:
        abort(404)
    history = [dict(x) for x in db().execute('SELECT * FROM status_history WHERE order_id=? ORDER BY id', (order['id'],))]
    return render_template('track.html', order=order, items=get_order_items(order['id']), history=history)


@app.route('/operator/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        operator = db().execute('SELECT * FROM operators WHERE username=?', (request.form.get('username', ''),)).fetchone()
        if operator and check_password_hash(operator['password_hash'], request.form.get('password', '')):
            session.clear()
            session['operator_id'] = operator['id']
            session['csrf_token'] = secrets.token_urlsafe(32)
            return redirect(url_for('dashboard'))
        flash('Неправильний логін або пароль', 'error')
    return render_template('login.html')


@app.post('/operator/logout')
@operator_required
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.get('/operator')
@operator_required
def dashboard():
    orders = [dict(x) for x in db().execute('SELECT * FROM orders ORDER BY id DESC')]
    statuses = ['Нове', 'Готується', 'Готове', 'Видано', 'Скасовано']
    return render_template('operator.html', orders=orders, statuses=statuses)


TRANSITIONS = {'Нове': {'Готується', 'Скасовано'}, 'Готується': {'Готове', 'Скасовано'},
               'Готове': {'Видано'}, 'Видано': set(), 'Скасовано': set()}


@app.post('/operator/order/<int:order_id>/status')
@operator_required
def change_status(order_id):
    order = db().execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
    if not order:
        abort(404)
    new_status = request.form.get('status', '')
    if new_status not in TRANSITIONS.get(order['status'], set()):
        flash('Недозволений перехід статусу', 'error')
    else:
        conn = db()
        conn.execute('UPDATE orders SET status=? WHERE id=?', (new_status, order_id))
        conn.execute('INSERT INTO status_history(order_id,status,changed_at) VALUES (?,?,?)',
                     (order_id, new_status, now_kyiv().isoformat(timespec='seconds')))
        conn.commit()
        flash(f'Замовлення №{order_id}: статус «{new_status}»', 'success')
    return redirect(url_for('dashboard'))


@app.get('/operator/products')
@operator_required
def admin_products():
    return render_template('products.html', products=menu_data()['products'])


@app.post('/operator/products/<int:product_id>/toggle')
@operator_required
def toggle_product(product_id):
    conn = db()
    conn.execute('UPDATE products SET available=1-available WHERE id=?', (product_id,))
    conn.commit()
    return redirect(url_for('admin_products'))


@app.errorhandler(404)
def not_found(_):
    return render_template('error.html', message='Сторінку не знайдено'), 404


@app.errorhandler(403)
def forbidden(_):
    return render_template('error.html', message='Доступ заборонено'), 403


# Initialize for any start method, including flask run and test client.
with app.app_context():
    init_db()


if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1', port=5000)
