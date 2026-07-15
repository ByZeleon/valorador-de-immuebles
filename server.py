from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
import re
import unicodedata

app = Flask(__name__)

def slugify(text):
    """
    Convierte 'Vilafranca del Penedès' en 'vilafranca-del-penedes'
    o 'Móstoles' en 'mostoles' para encajar en la URL.
    """
    if not text:
        return ""
    # Quita acentos y diéresis
    text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8')
    text = text.lower()
    # Quita caracteres raros
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    # Cambia espacios por guiones
    text = re.sub(r'[\s-]+', '-', text).strip('-')
    return text

def obtener_precio_directo(municipio):
    """
    Ataca directamente a la URL simplificada de Fotocasa
    """
    municipio_slug = slugify(municipio)
    
    # Construimos la URL mágica que has descubierto
    url = f"https://www.fotocasa.es/indice-precio-vivienda/{municipio_slug}/todas-las-zonas"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9",
        "Referer": "https://www.google.com/"
    }
    
    try:
        print(f"📡 Solicitando directamente: {url}")
        response = requests.get(url, headers=headers, timeout=6)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            texto_pagina = soup.get_text()
            
            # Buscamos el patrón del precio (ejemplo: "1.950 €/m²")
            precios = re.findall(r'([\d\.]+)\s*€/m²', texto_pagina)
            if precios:
                precio_m2 = int(precios[0].replace('.', ''))
                return precio_m2
            else:
                print("⚠️ No se encontró el texto '€/m²' en el HTML de la página.")
                return None
        else:
            print(f"❌ Error de respuesta de Fotocasa (Código {response.status_code}) para: {municipio_slug}")
            return None
            
    except Exception as e:
        print(f"❌ Error físico de conexión: {e}")
        return None


# --- EL ENDPOINT AL QUE LE PREGUNTA EL VALORADOR ---
@app.route('/obtener_precio', methods=['POST'])
def obtener_precio():
    data = request.get_json() or {}
    municipio = data.get('municipio')
    
    if not municipio:
        return jsonify({"status": "error", "message": "Falta el municipio en la petición"}), 400
        
    precio = obtener_precio_directo(municipio)
    
    if precio:
        print(f"🎯 ¡Éxito! {municipio} -> {precio} €/m²")
        return jsonify({
            "status": "success", 
            "precio_m2": precio,
            "municipio": municipio
        })
        
    return jsonify({
        "status": "not_found", 
        "message": "No se pudo extraer el precio de este municipio"
    }), 404

if __name__ == '__main__':
    # Arrancamos en el puerto 5000
    app.run(port=5000)