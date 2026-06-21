# Fort Knox — Laboratorio de cadena de ataque

Trabajo Práctico de Seguridad en Aplicaciones Web · UTN FRBA (K5061) · Grupo 4 · 2026

Dos portales web de una joyería ficticia, **Fort Knox**, conectados por una sesión
compartida (SSO). Cada uno tiene vulnerabilidades que, encadenadas, permiten a un
atacante pasar de tener una cuenta común a **tomar el control total de la cuenta de
otra persona** y operar a su nombre.

Todo el ataque se realiza **navegando con el browser** (más las herramientas de
desarrollador F12 y, opcionalmente, Burp Suite para la fuerza bruta). No hace falta
escribir requests a mano.

---

## La cadena en una mirada

| # | Vulnerabilidad | Portal | Qué obtiene el atacante |
|---|----------------|--------|--------------------------|
| 1 | IDOR / Broken Access Control | Seguimiento (5001) | Nombre + ID de cliente de la víctima |
| 2 | SQL Injection | Seguimiento (5001) | Email de la víctima |
| 3 | Security Misconfiguration | Clientes (5000) | Token de recuperación de cuenta |
| 4 | Token Tampering (Data Integrity) | Clientes (5000) | Sesión activa como la víctima |
| ★ | Impacto | Clientes (5000) | Tarjeta guardada, cambio de dirección, compras |

Cada paso es **necesario**: sin el ID de cliente no podés apuntar la inyección, sin el
email no podés pedir la recuperación, sin el token no hay toma de cuenta. El IDOR
expone el ID pero **no** el email, así que el SQL Injection es obligatorio para
conseguirlo.

---

## Los dos portales

```
JoyeriaFortKnox/
├── clientes/                   Portal de Clientes — http://localhost:5000
│   ├── app.py
│   ├── seed.py                 crea y puebla clientes.db
│   ├── requirements.txt
│   └── templates/
│       ├── base.html
│       ├── login.html
│       ├── dashboard.html      "Mi cuenta": pedidos del cliente
│       ├── profile.html        "Mi perfil": datos sensibles, tarjeta, compras
│       ├── recover.html        formulario de recuperación de cuenta
│       ├── recover_sent.html   confirmación de envío del mail
│       └── confirm_recovery.html  procesa el token de recuperación
│
└── tracking/                   Portal de Seguimiento — http://localhost:5001
    ├── app.py
    ├── seed.py                 crea y puebla tracking.db
    ├── requirements.txt
    └── templates/
        ├── base.html
        ├── login.html          pantalla cuando falta la cookie SSO
        ├── index.html          búsqueda de envíos por email (vector del SQLi)
        └── tracking.html       detalle de un envío (vector del IDOR)
```

Material de apoyo en la raíz: `ataque.html` (diagrama visual de la cadena),
`como_probar.txt` (guía rápida) y `bruteforce_shipment.py` (script opcional de
fuerza bruta).

---

## Cómo levantar el laboratorio

Requisitos: **Python 3.10+** y **Flask** (`python -m pip install flask`).

Cada portal corre en su propia terminal. Conviene arrancar primero el de clientes.

**Terminal 1 — Portal de Clientes (puerto 5000)**

```
cd clientes
python -m pip install flask     (solo la primera vez)
python seed.py                  (solo la primera vez — crea clientes.db)
python app.py
```

**Terminal 2 — Portal de Seguimiento (puerto 5001)**

```
cd tracking
python -m pip install flask     (solo la primera vez)
python seed.py                  (solo la primera vez — crea tracking.db)
python app.py
```

Con ambos corriendo, el laboratorio queda en:

- Portal de Clientes → http://localhost:5000
- Portal de Seguimiento → http://localhost:5001

> **Resetear entre pruebas:** el ataque modifica datos (email, dirección, pedidos).
> Para volver al estado inicial, frená las apps, volvé a correr `python seed.py` en
> cada carpeta y arrancá de nuevo. Útil para repetir la demo o regrabar el video.

---

## Usuarios de prueba

**Portal de Clientes** (todos con contraseña `FK2026!`)

| Usuario | Rol | ID de cliente | Nº de envío |
|---------|-----|---------------|-------------|
| `carlos_gomez` | Víctima | 204815 | 692 |
| `ana_martinez` | — | 119273 | 759 |
| `lucia_perez` | — | 387640 | 481 |
| `attacker` | Atacante | 256108 | 666 |

El atacante es un cliente legítimo de la joyería: tiene su propia cuenta y su propio
envío (`666`). A partir de ahí ataca a Carlos.

---

# Ejecución del ataque (paso a paso)

Todo se hace en el navegador. Donde dice "abrí", navegás a esa dirección en la barra
del browser.

## Paso 0 — Iniciar sesión como atacante

Abrí el Portal de Clientes e iniciá sesión con la cuenta propia del atacante:

```
http://localhost:5000/login
   usuario:     attacker
   contraseña:  FK2026!
```

Esto crea la cookie de sesión `fk_session`. Como ambos portales comparten la misma
clave secreta y el mismo nombre de cookie, **esa sesión también es válida en el
portal de seguimiento** (puerto 5001) sin volver a iniciar sesión.

---

## Paso 1 — IDOR: ver el envío de otra persona

El atacante conoce el número de su propio envío. Abrilo:

```
http://localhost:5001/tracking?shipment_id=666
```

Muestra los datos del envío del atacante. La clave: el portal **no verifica que el
envío te pertenezca**. Cambiando el número se accede a envíos ajenos. Probá subiendo
desde el propio número hasta encontrar uno válido:

```
http://localhost:5001/tracking?shipment_id=692
```

Aparecen los datos del destinatario sin ser el dueño del envío:

| Dato | Valor |
|------|-------|
| Nombre | Carlos Gomez |
| ID de cliente | **204815** |
| Orden | ORD-2026-1001 |

El detalle **no muestra el email** — solo el ID de cliente, que es lo que habilita el
Paso 2.

### Automatizar la búsqueda con Burp Suite (recomendado para la demo)

Los números no son consecutivos, así que conviene enumerarlos. Un envío que existe
devuelve **200**; uno inexistente devuelve **404**. Ese contraste delata los válidos.

1. Capturá en Burp la request a `/tracking?shipment_id=666` (con la cookie `fk_session`).
2. Mandala a **Intruder** y marcá el número como posición de payload.
3. En **Payloads** → tipo **Numbers** → From `666`, To `999`, Step `1`
   (Max integer digits `3`).
4. **Start attack** y ordená por **Status code**: los `200` (envíos reales) saltan
   entre los `404`. Subiendo desde 666, el primero ajeno es `692`.

> **Por qué funciona:** el endpoint valida que haya sesión, pero no compara el dueño
> del envío con el usuario de la sesión. **Prevención:** verificar ownership del
> recurso (que el `shipment_id` pertenezca al usuario autenticado) antes de devolverlo.

---

## Paso 2 — SQL Injection: obtener el email

El portal de seguimiento te deja buscar tus envíos por email. Abrí la página principal:

```
http://localhost:5001/
```

Ese buscador es vulnerable a inyección SQL. El atacante todavía **no tiene el email**
de la víctima (el Paso 1 solo le dio el ID de cliente), así que lo inyecta para
extraerlo usando ese ID. Pegá esto en el campo de búsqueda y confirmá:

```
' UNION SELECT email,'-','-','-','-' FROM users WHERE id=204815--
```

La grilla muestra una fila donde la columna **Nro. de envío** contiene el email de la
víctima: **`carlos.gomez@gmail.com`**. (Los datos aparecen en columnas que no
corresponden — esa "UI rota" es justamente la señal de la inyección.)

> **Por qué funciona:** el backend arma la consulta pegando el texto del campo
> directamente, sin separarlo de la instrucción SQL. **Prevención:** usar consultas
> parametrizadas (placeholders `?`), nunca concatenar entrada del usuario.

---

## Paso 3 — Security Misconfiguration: capturar el token de recuperación

Ya con el email, el atacante pide recuperar la cuenta de Carlos. Abrí:

```
http://localhost:5000/account/recover
```

Ingresá el email `carlos.gomez@gmail.com` y enviá. La pantalla solo dice que se mandó
un mail a ese correo — el atacante **no tiene acceso al buzón de la víctima**. Pero el
servidor filtra el token en la propia respuesta:

1. Antes de enviar el formulario, abrí las herramientas de desarrollador con **F12**.
2. Andá a la pestaña **Network** (Red) y tildá **Preserve log** (Conservar registro).
3. Ingresá `carlos_gomez` y enviá el formulario.
4. En la lista, hacé clic en la entrada **`recover`**.
5. Abrí la pestaña **Headers** y bajá a **Response Headers**.
6. Ahí está el token, en texto plano:
   ```
   X-Debug-Token: eyJ1c2VyIjogImNhcmxvc19nb21leiIs...
   ```
7. Copiá ese valor.

> **Por qué funciona:** quedó un encabezado de debug que expone el token de recuperación
> en la respuesta. **Prevención:** el token solo debe viajar por el canal seguro previsto
> (el email del dueño), nunca en la respuesta; quitar artefactos de debug antes de
> publicar.

---

## Paso 4 — Token Tampering: tomar el control de la cuenta

El token es un JSON codificado en Base64URL **sin ninguna firma**. Su contenido es:

```
{ "user": "carlos_gomez", "authorized_email": "carlos.gomez@gmail.com", "exp": "..." }
```

El atacante lo decodifica, le cambia `authorized_email` por su propio correo, lo vuelve
a codificar y visita la confirmación con el token modificado. Como el servidor no
verifica integridad, lo acepta.

La forma más limpia de hacerlo en vivo es desde la consola del navegador:

1. Quedate en una pestaña de `localhost:5000`.
2. Abrí **F12** → pestaña **Console**.
3. Pegá esto, reemplazando `PEGA_EL_TOKEN_ACA` con el token del Paso 3:

```js
const token = "PEGA_EL_TOKEN_ACA";
// 1. decodificar Base64URL -> JSON
const b64 = token.replace(/-/g,'+').replace(/_/g,'/');
const payload = JSON.parse(atob(b64 + "=".repeat((4 - b64.length % 4) % 4)));
console.log("Token original:", payload);
// 2. cambiar el email autorizado por el del atacante
payload.authorized_email = "attacker@mailinator.com";
console.log("Token modificado:", payload);
// 3. re-codificar a Base64URL (sin padding)
const tampered = btoa(JSON.stringify(payload))
  .replace(/\+/g,'-').replace(/\//g,'_').replace(/=/g,'');
// 4. navegar a la confirmación con el token alterado
location.href = "http://localhost:5000/account/confirm-recovery?token=" + tampered;
```

4. Enter. El navegador navega solo y muestra "acceso concedido": **quedás con la sesión
   iniciada como `carlos_gomez`**, con el email de la cuenta cambiado al del atacante.

> **Por qué funciona:** Base64 es codificación, no cifrado — cualquiera lo decodifica,
> edita y recodifica. Sin una firma que el servidor valide, no hay forma de detectar
> que el token fue alterado. **Prevención:** firmar el token (HMAC/JWT con secreto) y
> verificar la firma antes de procesarlo.

---

## Paso ★ — Impacto: qué puede hacer el atacante adentro

Ya dentro de la cuenta de Carlos, en la navbar hacé clic en **Mi perfil**:

```
http://localhost:5000/profile
```

Desde ahí el atacante puede:

- **Ver datos sensibles:** teléfono, dirección y la **tarjeta de pago guardada**
  (`Visa ···· 4821`). El email ya figura como el del atacante (lo cambió el Paso 4),
  mientras la tarjeta y la dirección siguen siendo de Carlos: está claramente dentro
  de la cuenta real de la víctima.
- **Cambiar la dirección de envío** a la suya — los próximos pedidos se entregan donde
  él diga.
- **Comprar con un clic** usando la tarjeta de la víctima. La compra queda registrada
  en la cuenta de Carlos y se envía a la dirección que el atacante puso.

Esto convierte la toma de cuenta en daño concreto: fraude con la tarjeta de la víctima
y mercadería desviada al atacante.

---

## Cómo funciona el SSO compartido

Ambos portales usan la **misma clave secreta** de sesión y el **mismo nombre de cookie**
(`fk_session`). Los navegadores envían las cookies de `localhost` sin distinguir el
puerto, así que la sesión creada al iniciar sesión en el portal de clientes (5000) es
automáticamente válida en el de seguimiento (5001). Por eso el atacante inicia sesión
una sola vez (Paso 0) y queda habilitado en ambos.
