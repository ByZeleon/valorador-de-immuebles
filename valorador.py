import os
import requests
import smtplib
from typing import Optional
from email.message import EmailMessage
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

# 1. CARGAMOS LAS VARIABLES DE ENTORNO OCULTAS (.env)
load_dotenv()

app = FastAPI(
    title="API de Valoración Inmobiliaria",
    description="Backend profesional para tasación de inmuebles en tiempo real.",
    version="1.0.0"
)

# URL de tu servidor de scraping de Fotocasa (server.py)
URL_SERVIDOR_PRECIOS = "http://localhost:5000/obtener_precio"

# 2. MOLDE DE LOS DATOS QUE LLEGARÁN DESDE EL FORMULARIO WEB (Cambiado 'barrio' por 'municipio')
class DatosCliente(BaseModel):
    nombre: str
    telefono: str
    email: str
    codigo_postal: str
    municipio: str            # Cambiado de 'barrio' a 'municipio'
    metros_vivienda: float
    estado_conservacion: str  # "A" (reformar), "B" (buen estado), "C" (excelente)
    m2_terraza: float = 0.0   # Opcional, por defecto 0.0
    plazas_garaje: int = 0    # Opcional, por defecto 0
    m2_trastero: float = 0.0  # Opcional, por defecto 0.0


# 3. FUNCIÓN PARA PREGUNTAR EL PRECIO DEL M2 A TU SERVIDOR (server.py)
def obtener_precio_m2_servidor(municipio: str) -> Optional[float]:
    try:
        respuesta = requests.post(
            URL_SERVIDOR_PRECIOS, 
            json={"municipio": municipio}, 
            timeout=10
        )
        if respuesta.status_code == 200:
            datos = respuesta.json()
            return float(datos.get("precio_m2"))
    except Exception as e:
        print(f"❌ Error al conectar con el servidor de scraping (server.py): {e}")
    return None


# 4. FUNCIÓN PARA ENVIAR EL CORREO ELECTRÓNICO (GMAIL SEGURO)
def enviar_alerta_agente(datos: DatosCliente, precio_calculado: Optional[float] = None):
    # Leemos las credenciales que guardaste de forma segura en tu .env
    REMITENTE = os.getenv("EMAIL_REMITENTE")
    PASSWORD = os.getenv("EMAIL_PASSWORD")
    DESTINATARIO = os.getenv("EMAIL_DESTINATARIO")

    # Verificación de seguridad por si olvidaste configurar el archivo .env
    if not REMITENTE or not PASSWORD or not DESTINATARIO:
        print("⚠️ ERROR: No se han configurado correctamente las variables del archivo .env")
        return

    traductor_estados = {
        "A": "A reformar",
        "B": "Buen estado",
        "C": "Excelente / Obra nueva"
    }
    
    # Buscamos la descripción. Si por error llega algo que no es A, B o C, pondrá "No especificado"
    estado_descriptivo = traductor_estados.get(datos.estado_conservacion.upper(), "No especificado")

    # Creamos la estructura de correo
    mensaje = EmailMessage()
    
    # Cambiamos el asunto dependiendo de si pudimos calcular el precio o no
    if precio_calculado is not None:
        mensaje['Subject'] = f"🚨 Nueva valoración web: {datos.nombre} ({datos.municipio})"
        valoracion_texto = f"🎯 VALORACIÓN ESTIMADA DE MERCADO: {precio_calculado:,.2f} €"
    else:
        mensaje['Subject'] = f"⚠️ Lead sin valorar (Revisión Manual): {datos.nombre} ({datos.municipio})"
        valoracion_texto = "⚠️ VALORACIÓN ESTIMADA DE MERCADO: No se pudo calcular automáticamente (requiere revisión manual)"

    mensaje['From'] = REMITENTE
    mensaje['To'] = DESTINATARIO

    cuerpo = f"""
    ¡Hola equipo!
    Se ha generado una nueva oportunidad de venta desde el tasador web.
    
    DATOS DE CONTACTO DEL INTERESADO:
    ==================================================
    • Nombre: {datos.nombre}
    • Teléfono: {datos.telefono}
    • Email: {datos.email}
    
    CARACTERÍSTICAS DEL INMUEBLE INTRODUCIDAS:
    ==================================================
    • Ubicación: CP {datos.codigo_postal} - Municipio: {datos.municipio}
    • Metros Vivienda: {datos.metros_vivienda} m²
    • Estado de Conservación: {estado_descriptivo}
    • Terraza/Balcón: {datos.m2_terraza} m²
    • Plazas de Garaje: {datos.plazas_garaje} plaza(s)
    • Trastero: {datos.m2_trastero} m²
    
    --------------------------------------------------
    {valoracion_texto}
    --------------------------------------------------
    """
    mensaje.set_content(cuerpo)

    try:
        # Servidor SMTP seguro de Gmail (Puerto 587 con cifrado TLS obligatorio hoy en día)
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()  # Iniciamos conexión cifrada segura
            server.login(REMITENTE, PASSWORD)
            server.send_message(mensaje)
        print("✅ ¡Email de alerta enviado con éxito al agente inmobiliario!")
    except Exception as e:
        print(f"❌ Error crítico al enviar el email por SMTP: {e}")


# 5. EL ENPOINT DE TU FORMULARIO (FastAPI)
@app.post("/api/calcular-valoracion")
def calcular_valoracion(datos: DatosCliente, background_tasks: BackgroundTasks):
    
    # A. Le preguntamos a nuestro server.py el precio por m2 del municipio
    precio_base_m2 = obtener_precio_m2_servidor(datos.municipio)

    # B. Si el servidor nos devuelve un precio válido, hacemos los cálculos automáticos
    if precio_base_m2 is not None:
        # Aplicamos los factores correctores de conservación
        factor_estado = 1.0
        if datos.estado_conservacion == 'A':
            factor_estado = 0.80  # Penalización del -20% por reforma
        elif datos.estado_conservacion == 'C':
            factor_estado = 1.15  # Plus del +15% por excelente/obra nueva

        precio_m2_ajustado = precio_base_m2 * factor_estado

        # Matemáticas de valoración detallada
        valor_vivienda = datos.metros_vivienda * precio_m2_ajustado
        valor_terraza = datos.m2_terraza * (precio_m2_ajustado * 0.5)      # Al 50% de valor real
        valor_garaje = datos.plazas_garaje * (precio_m2_ajustado * 5)      # Equivalente a 5m² por plaza
        valor_trastero = datos.m2_trastero * (precio_m2_ajustado * 0.5)    # Al 50% de valor real

        precio_final = valor_vivienda + valor_terraza + valor_garaje + valor_trastero

        # Mandamos el email al buzón con el precio calculado en segundo plano
        background_tasks.add_task(enviar_alerta_agente, datos, precio_final)

        # Devolvemos la respuesta para el Frontend
        return {
            "status": "success",
            "precio_estimado": round(precio_final, 2),
            "desglose": {
                "valor_vivienda": round(valor_vivienda, 2),
                "valor_terraza": round(valor_terraza, 2),
                "valor_garaje": round(valor_garaje, 2),
                "valor_trastero": round(valor_trastero, 2)
            }
        }
    
    # C. Si NO se encuentra el precio (fallo, bloqueo, etc.), enviamos el email SIN precio final
    else:
        background_tasks.add_task(enviar_alerta_agente, datos, None)
        
        return {
            "status": "pending",
            "precio_estimado": None,
            "mensaje": "Hemos recibido tus datos correctamente. En breve nos pondremos en contacto contigo para darte la valoración."
        }