# Fort Knox — TP Seguridad Web (K5061)

Laboratorio de cadena de ataque sobre dos portales web vulnerables de una joyería ficticia.  
UTN FRBA · Grupo 4 · 2026

---

## Cadena de ataque

```
Paso 1 — A01: IDOR / BOLA          Portal de Seguimiento (5001)
  GET /tracking?shipment_id=1000001234
  → sin autenticacion, devuelve datos del destinatario:
    user_id=1, nombre, email de la victima

Paso 2 — A05: SQL Injection         Portal de Seguimiento (5001)
  GET /support/search?user_id=1 UNION SELECT id,username,first_name,last_name FROM users WHERE id=1--
  → extrae el username de la victima: "carlos_gomez"
  (requiere cookie SSO del portal de clientes)

Paso 3 — A02: Security Misconfiguration   Portal de Clientes (5000)
  POST /account/recover  { username: "carlos_gomez" }
  → la respuesta incluye debug_token con el token de recuperacion en texto

Paso 4 — A08: Token Tampering       Portal de Clientes (5000)
  Decodifica el token, cambia authorized_email al email del atacante,
  re-codifica y lo envia al endpoint de confirmacion
  → acceso total a la cuenta de carlos_gomez
```

---

## Estructura del proyecto

```
JoyeriaFortKnox/
├── tracking/                   ← Portal de Seguimiento de Envios (puerto 5001)
│   ├── app.py
│   ├── seed.py
│   ├── requirements.txt
│   ├── tracking.db             ← generado por seed.py (no commitear)
│   └── templates/
│       ├── base.html
│       ├── index.html          ← landing page publica
│       ├── tracking.html       ← VULNERABLE: IDOR
│       ├── support.html        ← VULNERABLE: SQLi
│       └── no_access.html      ← 403 sin SSO
└── clientes/                   ← Portal de Clientes (pendiente)
```

---

## Requisitos

- Python 3.10+
- `python -m pip install flask`

---

## Correr el portal de seguimiento

```bash
cd tracking

python -m pip install flask    # solo la primera vez
python seed.py                 # solo la primera vez — crea tracking.db
python app.py                  # inicia en http://localhost:5001
```

---

## Ejecutar el ataque (paso a paso)

### Paso 1 — IDOR: ver el envio de la victima

El atacante recibio el link de seguimiento de su propio pedido por email:
```
http://localhost:5001/tracking?shipment_id=1000004728
```

Modifica el `shipment_id` en la barra de direcciones:
```
http://localhost:5001/tracking?shipment_id=1000001234
```

**Resultado:** el servidor devuelve los datos de Carlos Gomez sin pedir ninguna autenticacion.

| Campo       | Valor obtenido              |
|-------------|-----------------------------|
| Nombre      | Carlos Gomez                |
| Email       | carlos.gomez@gmail.com      |
| ID de cliente | `1`                       |
| Orden       | ORD-2026-1001               |

**Por que funciona:** el endpoint no verifica que el `shipment_id` pertenezca
a quien hace la request. Solo busca en la DB por ID y devuelve lo que encuentra.

---

### Paso 2 — SQL Injection: extraer el username

Con el `ID de cliente: 1` obtenido antes, el atacante va a:
```
http://localhost:5001/support/search?user_id=1
```

> **Nota:** este endpoint requiere la cookie SSO del portal de clientes.  
> Para testear localmente sin el portal de clientes, ir primero a:
> `http://localhost:5001/dev/auth`  
> (disponible solo con `debug=True`, simula estar logueado en el portal de clientes)

Consulta normal — devuelve nombre y email de Carlos. Ahora el atacante inyecta:
```
http://localhost:5001/support/search?user_id=1 UNION SELECT id,username,first_name,last_name FROM users WHERE id=1--
```

**Resultado:** aparece una segunda fila con `carlos_gomez` en la columna de nombre.

**Por que funciona:** el backend construye la query concatenando el parametro directamente:
```python
query = f"SELECT id, first_name, last_name, email FROM users WHERE id = {user_id}"
```
El `UNION SELECT` se ejecuta como SQL valido. No hay password en esta tabla,
por lo que la inyeccion solo expone el username — suficiente para el paso siguiente.

---

## Usuarios de prueba

| Usuario        | Email                        | user_id | shipment_id  | Rol      |
|----------------|------------------------------|---------|--------------|----------|
| `carlos_gomez` | carlos.gomez@gmail.com       | 1       | 1000001234   | Victima  |
| `ana_martinez` | ana.martinez@hotmail.com     | 2       | 1000002847   | —        |
| `lucia_perez`  | lucia.perez@yahoo.com        | 3       | 1000003591   | —        |
| `attacker`     | attacker@mailinator.com      | 4       | 1000004728   | Atacante |

---

## Mecanismo SSO

Ambos portales comparten `secret_key = 'fortknox-sso-shared-secret-2026'`
y el nombre de cookie `fk_session`. Los navegadores envian cookies de `localhost`
sin distinguir puerto, por lo que la sesion creada en el puerto 5000 (clientes)
es automaticamente valida en el puerto 5001 (tracking).
