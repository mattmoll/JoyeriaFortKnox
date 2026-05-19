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
users = [
    ('carlos_gomez',  'carlos.gomez@gmail.com',       'Carlos',  'Gomez'),
    ('ana_martinez',  'ana.martinez@hotmail.com',     'Ana',     'Martinez'),
    ('lucia_perez',   'lucia.perez@yahoo.com',        'Lucia',   'Perez'),
    ('attacker',      'attacker@mailinator.com',      'Juan',    'Atacante'),
]
c.executemany(
    'INSERT INTO users (username, email, first_name, last_name) VALUES (?,?,?,?)',
    users
)

# IDs de 7 digitos para que no sean trivialmente enumerables por fuerza bruta.
# El envio de la victima (carlos_gomez, user_id=1) es 3847291.
# El atacante (user_id=4) recibio el link de su propio envio: 4829163.
shipments = [
    (3847291, 1, 'ORD-2026-1001', 'En camino',  'Av. Corrientes 1234, CABA',   '2026-05-28'),
    (7281053, 2, 'ORD-2026-1002', 'Entregado',  'Av. Belgrano 456, CABA',      '2026-05-10'),
    (3562748, 3, 'ORD-2026-1003', 'Procesando', 'Calle Florida 789, CABA',     '2026-06-05'),
    (4829163, 4, 'ORD-2026-1004', 'En camino',  'Rivadavia 2100, CABA',        '2026-05-30'),
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
print("  carlos_gomez  user_id=1, shipment=3847291   (VICTIMA)")
print("  ana_martinez  user_id=2, shipment=7281053")
print("  lucia_perez   user_id=3, shipment=3562748")
print("  attacker      user_id=4, shipment=4829163   (ATACANTE)")
