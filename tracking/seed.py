"""
Inicializa y puebla la base de datos del portal de seguimiento de envios.
Ejecutar una sola vez antes de correr app.py:
    python seed.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'tracking.db')

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.executescript('''
DROP TABLE IF EXISTS shipments;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT UNIQUE NOT NULL,
    email       TEXT NOT NULL,
    first_name  TEXT NOT NULL,
    last_name   TEXT NOT NULL
);

CREATE TABLE shipments (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    shipment_id        INTEGER UNIQUE NOT NULL,
    user_id            INTEGER NOT NULL,
    order_number       TEXT NOT NULL,
    status             TEXT NOT NULL,
    destination        TEXT NOT NULL,
    estimated_delivery TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
''')

# Sin campo password — este portal no maneja autenticacion propia.
# Los usernames coinciden con los del portal de clientes (campo compartido via SSO).
# IDs de cliente ofuscados (no secuenciales) — iguales en ambos portales.
users = [
    (204815, 'carlos_gomez',  'carlos.gomez@gmail.com',       'Carlos',  'Gomez'),
    (119273, 'ana_martinez',  'ana.martinez@hotmail.com',     'Ana',     'Martinez'),
    (387640, 'lucia_perez',   'lucia.perez@yahoo.com',        'Lucia',   'Perez'),
    (256108, 'attacker',      'attacker@mailinator.com',      'Juan',    'Atacante'),
]
c.executemany(
    'INSERT INTO users (id, username, email, first_name, last_name) VALUES (?,?,?,?,?)',
    users
)

# IDs de 3 digitos, no consecutivos pero dentro del rango 100-999.
# El atacante (id=256108) recibio el link de su propio envio: 666.
# La victima (carlos_gomez, id=204815) es 692 — a solo 26 del atacante,
# asi un barrido desde 666 hacia arriba la encuentra rapido (demo en vivo).
# ana y lucia quedan fuera de la ventana 666-692 para que el primer hit sea 692.
shipments = [
    (692, 204815, 'ORD-2026-1001', 'En camino',  'Av. Corrientes 1234, CABA',   '2026-05-28'),
    (759, 119273, 'ORD-2026-1002', 'Entregado',  'Av. Belgrano 456, CABA',      '2026-05-10'),
    (481, 387640, 'ORD-2026-1003', 'Procesando', 'Calle Florida 789, CABA',     '2026-06-05'),
    (666, 256108, 'ORD-2026-1004', 'En camino',  'Rivadavia 2100, CABA',        '2026-05-30'),
]
c.executemany(
    '''INSERT INTO shipments
       (shipment_id, user_id, order_number, status, destination, estimated_delivery)
       VALUES (?,?,?,?,?,?)''',
    shipments
)

conn.commit()
conn.close()
print("Base de datos del portal de tracking inicializada correctamente.")
print()
print("Usuarios (sin password - este portal no tiene login propio):")
print("  carlos_gomez  id=204815, shipment=692   (VICTIMA)")
print("  ana_martinez  id=119273, shipment=759")
print("  lucia_perez   id=387640, shipment=481")
print("  attacker      id=256108, shipment=666   (ATACANTE)")
