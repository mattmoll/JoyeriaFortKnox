"""
Inicializa y puebla la base de datos del portal de clientes.
Ejecutar una sola vez antes de correr app.py:
    python seed.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'clientes.db')

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.executescript('''
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT UNIQUE NOT NULL,
    password    TEXT NOT NULL,
    email       TEXT NOT NULL,
    first_name  TEXT NOT NULL,
    last_name   TEXT NOT NULL,
    phone       TEXT,
    address     TEXT,
    card_brand  TEXT,
    card_last4  TEXT
);

CREATE TABLE orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    order_number TEXT NOT NULL,
    product_name TEXT NOT NULL,
    amount       REAL NOT NULL,
    status       TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
''')

# Los usernames coinciden con los del portal de tracking (campo compartido via SSO).
# IDs de cliente ofuscados (no secuenciales) — iguales en ambos portales.
# Passwords en texto claro — este es un lab de seguridad, no produccion.
users = [
    (204815, 'carlos_gomez', 'FK2026!', 'carlos.gomez@gmail.com',   'Carlos', 'Gomez',
     '+54 9 11 4821-7766', 'Av. Corrientes 1234, Piso 8 "B", CABA (C1043)', 'Visa', '4821'),
    (119273, 'ana_martinez', 'FK2026!', 'ana.martinez@hotmail.com', 'Ana',    'Martinez',
     '+54 9 11 3372-1180', 'Av. Belgrano 456, CABA', 'Mastercard', '7732'),
    (387640, 'lucia_perez',  'FK2026!', 'lucia.perez@yahoo.com',    'Lucia',  'Perez',
     '+54 9 11 5567-9043', 'Calle Florida 789, CABA', 'Visa', '2290'),
    (256108, 'attacker',     'FK2026!', 'attacker@mailinator.com',  'Juan',   'Atacante',
     '+54 9 11 2211-0090', 'Rivadavia 2100, CABA', 'Visa', '0001'),
]
c.executemany(
    '''INSERT INTO users (id, username, password, email, first_name, last_name,
                          phone, address, card_brand, card_last4)
       VALUES (?,?,?,?,?,?,?,?,?,?)''',
    users
)

orders = [
    (204815, 'ORD-2026-1001', 'Anillo de Diamantes 0.5ct', 45000, 'Enviado',         '2026-05-12'),
    (119273, 'ORD-2026-1002', 'Collar de Oro 18k',          28000, 'Entregado',       '2026-05-01'),
    (387640, 'ORD-2026-1003', 'Pulsera de Plata 925',       15000, 'En preparacion',  '2026-05-18'),
    (256108, 'ORD-2026-1004', 'Cadena de Plata 50cm',       12000, 'Enviado',         '2026-05-15'),
]
c.executemany(
    '''INSERT INTO orders (user_id, order_number, product_name, amount, status, created_at)
       VALUES (?,?,?,?,?,?)''',
    orders
)

conn.commit()
conn.close()
print("Base de datos del portal de clientes inicializada correctamente.")
print()
print("Usuarios (password: FK2026! para todos):")
print("  carlos_gomez  ->  carlos.gomez@gmail.com   (VICTIMA)")
print("  ana_martinez  ->  ana.martinez@hotmail.com")
print("  lucia_perez   ->  lucia.perez@yahoo.com")
print("  attacker      ->  attacker@mailinator.com  (ATACANTE)")
