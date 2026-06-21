from flask import Flask, request, render_template, redirect, url_for, session, flash
from functools import wraps
import sqlite3
import os
import json
import base64
import random
from datetime import datetime, timedelta

app = Flask(__name__)

# Clave compartida con el portal de tracking (mecanismo SSO).
# La cookie fk_session creada aqui es automaticamente valida en el puerto 5001
# porque ambos portales comparten el mismo secret_key.
app.secret_key = 'fortknox-sso-shared-secret-2026'
app.config['SESSION_COOKIE_NAME'] = 'fk_session'

DB_PATH = os.path.join(os.path.dirname(__file__), 'clientes.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


# ---------------------------------------------------------------------------
# Login / Logout
# ---------------------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        conn = get_db()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ? AND password = ?',
            (username, password)
        ).fetchone()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        error = 'Usuario o contraseña incorrectos.'

    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    orders = conn.execute(
        'SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC',
        (session['user_id'],)
    ).fetchall()
    conn.close()
    return render_template('dashboard.html', user=user, orders=orders)


# ---------------------------------------------------------------------------
# Perfil del cliente — datos sensibles + direccion de envio + compra express.
# Demuestra el IMPACTO de la toma de cuenta: con la sesion de la victima el
# atacante ve su tarjeta guardada, cambia la direccion de envio y compra a su
# nombre. Todo mockeado, pero ilustra el provecho real del ataque.
# ---------------------------------------------------------------------------

# Catalogo mock para la compra de un clic con la tarjeta guardada.
CATALOG = [
    {'name': 'Reloj Oro Rosa 18k',       'amount': 89000},
    {'name': 'Aros de Brillantes 1ct',   'amount': 124000},
    {'name': 'Anillo Esmeralda Premium', 'amount': 156000},
]


@app.route('/profile')
@login_required
def profile():
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    return render_template('profile.html', user=user, catalog=CATALOG)


@app.route('/profile/address', methods=['POST'])
@login_required
def update_address():
    new_address = request.form.get('address', '').strip()
    if new_address:
        conn = get_db()
        conn.execute('UPDATE users SET address = ? WHERE id = ?',
                     (new_address, session['user_id']))
        conn.commit()
        conn.close()
        flash(f'Dirección de envío actualizada a: {new_address}')
    return redirect(url_for('profile'))


@app.route('/profile/purchase', methods=['POST'])
@login_required
def purchase():
    try:
        idx = int(request.form.get('item', -1))
    except ValueError:
        idx = -1

    if 0 <= idx < len(CATALOG):
        item = CATALOG[idx]
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        order_number = 'ORD-2026-' + str(random.randint(2000, 9999))
        conn.execute(
            '''INSERT INTO orders (user_id, order_number, product_name, amount, status, created_at)
               VALUES (?,?,?,?,?,?)''',
            (session['user_id'], order_number, item['name'], item['amount'],
             'En preparacion', datetime.utcnow().strftime('%Y-%m-%d'))
        )
        conn.commit()
        conn.close()
        monto = '{:,.0f}'.format(item['amount']).replace(',', '.')
        flash(f"Compra confirmada: {item['name']} — $ {monto} cargado a "
              f"{user['card_brand']} ····{user['card_last4']}, envío a {user['address']}")
    return redirect(url_for('profile'))


# ---------------------------------------------------------------------------
# Recuperacion de cuenta
# VULNERABILIDAD A02: Security Misconfiguration
# El campo debug_token devuelve el token de recuperacion en la respuesta HTTP.
# En produccion ese token solo deberia enviarse por email; nunca en la respuesta.
# ---------------------------------------------------------------------------

@app.route('/account/recover', methods=['GET', 'POST'])
def recover():
    if request.method == 'GET':
        return render_template('recover.html')

    email = request.form.get('email', '').strip()

    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()

    if not user:
        return render_template('recover.html', error='No existe una cuenta con ese email.')

    payload = {
        'user': user['username'],
        'authorized_email': user['email'],
        'exp': (datetime.utcnow() + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }
    # Token: JSON codificado en base64url, sin firma — A08
    token = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).decode().rstrip('=')

    # A02: token incluido en header de respuesta — TODO: remover antes de deploy a produccion
    response = render_template('recover_sent.html', email=user['email'])
    from flask import make_response
    resp = make_response(response)
    resp.headers['X-Debug-Token'] = token
    return resp


# ---------------------------------------------------------------------------
# Confirmacion de recuperacion
# VULNERABILIDAD A08: Insecure Deserialization / Token Tampering
# El servidor decodifica el token sin verificar ningun HMAC ni firma.
# Un atacante puede modificar authorized_email y el servidor acepta el token como valido.
# Impacto: acceso total a la cuenta de la victima con el email del atacante.
# ---------------------------------------------------------------------------

@app.route('/account/confirm-recovery')
def confirm_recovery():
    token_str = request.args.get('token', '').strip()
    if not token_str:
        return render_template('confirm_recovery.html',
                               error='Falta el token de recuperacion.')

    try:
        padded = token_str + '=' * (-len(token_str) % 4)
        # A08: decodificacion sin verificacion de firma — cualquier base64 valido es aceptado
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())

        username = payload.get('user')
        authorized_email = payload.get('authorized_email')

        if not username or not authorized_email:
            return render_template('confirm_recovery.html', error='Token invalido.')

        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

        if not user:
            conn.close()
            return render_template('confirm_recovery.html', error='Token invalido.')

        # Actualiza el email al que dice el token — sin validar que no fue modificado
        conn.execute('UPDATE users SET email = ? WHERE id = ?',
                     (authorized_email, user['id']))
        conn.commit()
        conn.close()

        session['user_id'] = user['id']
        session['username'] = user['username']

        return render_template('confirm_recovery.html', success=True,
                               username=username, new_email=authorized_email)

    except Exception:
        return render_template('confirm_recovery.html',
                               error='Token invalido o mal formado.')


if __name__ == '__main__':
    app.run(debug=True, port=5000, host=os.environ.get('FLASK_HOST', '127.0.0.1'))
