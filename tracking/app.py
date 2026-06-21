from flask import Flask, request, render_template, redirect, url_for, session, abort
from functools import wraps
import sqlite3
import os

app = Flask(__name__)

# Clave compartida con el portal de clientes (mecanismo SSO).
# La cookie fk_session firmada por el portal de clientes es valida aqui
# porque ambos portales comparten el mismo secret_key.
app.secret_key = 'fortknox-sso-shared-secret-2026'
app.config['SESSION_COOKIE_NAME'] = 'fk_session'

DB_PATH = os.path.join(os.path.dirname(__file__), 'tracking.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def sso_required(f):
    """
    Verifica que exista una cookie de sesion valida emitida por el portal de clientes.
    Si no existe, redirige al login con un mensaje de error.
    No hay rate limiting ni ninguna proteccion adicional — el endpoint es enumerable.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', error='no_cookie'))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Login — solo muestra el error cuando no hay cookie SSO.
# El tracking portal no tiene login propio: la sesion la provee el portal de clientes.
# ---------------------------------------------------------------------------

@app.route('/login')
def login():
    error = request.args.get('error')
    return render_template('login.html', error=error)


# ---------------------------------------------------------------------------
# Dev: simula haber iniciado sesion en el portal de clientes.
# En produccion esto lo maneja el portal de clientes (puerto 5000).
# Solo disponible con debug=True.
# ---------------------------------------------------------------------------

@app.route('/dev/login')
def dev_login():
    if not app.debug:
        abort(404)
    session['user_id'] = 256108
    session['username'] = 'attacker'
    return '''
        <div style="font-family:sans-serif; max-width:420px; margin:80px auto; text-align:center;">
            <p style="color:#6b7280; font-size:.85rem; margin-bottom:1.5rem;">
                [DEV] Simulado login portal clientes — cookie creada
            </p>
            <a href="/" style="display:inline-block; padding:.6rem 1.4rem;
               background:#1b4f8a; color:#fff; border-radius:.4rem;
               text-decoration:none; font-size:.9rem;">
                Volver al portal de seguimiento
            </a>
        </div>
    '''


@app.route('/dev/logout')
def dev_logout():
    if not app.debug:
        abort(404)
    session.clear()
    return redirect(url_for('login', error='no_cookie'))


# ---------------------------------------------------------------------------
# Landing + busqueda de envios por email (busqueda publica, realista).
# VULNERABILIDAD A05: el parametro email se concatena directo en la query SQL.
# Del Paso 1 (IDOR) el atacante solo tiene el ID de cliente, no el email.
# Inyecta para extraer el EMAIL de la victima usando ese ID:
#   ' UNION SELECT email,'-','-','-','-' FROM users WHERE id=204815--
# Efecto: el email de la victima aparece en la columna "Nro. de envio".
# ---------------------------------------------------------------------------

@app.route('/')
@sso_required
def index():
    email = request.args.get('email', '').strip()
    results = []
    error = None
    searched = bool(email)

    if email:
        conn = get_db()
        try:
            # BUG A05: concatenacion directa de string — sin consultas parametrizadas.
            query = (
                f"SELECT s.shipment_id, s.order_number, s.status, "
                f"s.destination, s.estimated_delivery "
                f"FROM shipments s JOIN users u ON s.user_id = u.id "
                f"WHERE u.email = '{email}'"
            )
            results = conn.execute(query).fetchall()
        except Exception as e:
            error = str(e)
        finally:
            conn.close()

    return render_template('index.html', results=results,
                           email=email, error=error, searched=searched)


# ---------------------------------------------------------------------------
# Detalle de envio
# VULNERABILIDAD A01: IDOR — no verifica que el shipment_id pertenezca al usuario
# autenticado. Valida el token SSO pero no el ownership del recurso.
# No hay rate limiting: los IDs son enumerables por fuerza bruta.
# ---------------------------------------------------------------------------

@app.route('/tracking')
@sso_required
def tracking():
    shipment_id = request.args.get('shipment_id', '').strip()
    shipment = None
    error = None

    if shipment_id:
        conn = get_db()
        # BUG A01: cualquier usuario autenticado puede ver cualquier envio.
        shipment = conn.execute(
            '''SELECT s.shipment_id, s.order_number, s.status, s.destination,
                      s.estimated_delivery, s.user_id,
                      u.first_name, u.last_name, u.email
               FROM shipments s
               JOIN users u ON s.user_id = u.id
               WHERE s.shipment_id = ?''',
            (shipment_id,)
        ).fetchone()
        conn.close()
        if not shipment:
            # Envio inexistente -> 404. Un envio existente (de cualquier dueño)
            # devuelve 200 con los datos. Ese contraste 200 vs 404 es el que
            # delata el IDOR durante la enumeracion por fuerza bruta.
            error = f'No se encontró ningún envío con el ID {shipment_id}.'
            return render_template('tracking.html', shipment=None,
                                   error=error, shipment_id=shipment_id), 404

    return render_template('tracking.html', shipment=shipment,
                           error=error, shipment_id=shipment_id)



if __name__ == '__main__':
    app.run(debug=True, port=5001, host=os.environ.get('FLASK_HOST', '127.0.0.1'))
