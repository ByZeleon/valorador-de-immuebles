import os
import requests
import smtplib
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

# URL de tu GitHub público con la base de datos de barrios
URL_DATOS = "https://raw.githubusercontent.com/ByZeleon/valorador-de-immuebles/main/pricesDB.json"

# 2. MOLDE DE LOS DATOS QUE LLEGARÁN DESDE EL FORMULARIO WEB
class DatosCliente(BaseModel):
    nombre: str
    telefono: str
    email: str
    codigo_postal: str
    barrio: str
    metros_vivienda: float
    estado_conservacion: str  # "A" (reformar), "B" (buen estado), "C" (excelente)
    m2_terraza: float = 0.0   # Opcional, por defecto 0.0 si el cliente no lo pone
    plazas_garaje: int = 0    # Opcional, por defecto 0
    m2_trastero: float = 0.0  # Opcional, por defecto 0.0

# 3. FUNCIÓN PARA DESCARGAR TU BASE DE DATOS DESDE GITHUB
def cargar_datos_github():
    try:
        respuesta = requests.get(URL_DATOS)
        if respuesta.status_code == 200:
            return respuesta.json()
        return None
    except Exception as e:
        print(f"❌ Error de conexión al descargar de GitHub: {e}")
        return None

# 4. FUNCIÓN PARA ENVIAR EL CORREO ELECTRÓNICO (GMAIL SEGURO)
def enviar_alerta_agente(datos: DatosCliente, precio_calculado: float):
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
    mensaje['Subject'] = f"🚨 Nueva valoración web: {datos.nombre} ({datos.barrio})"
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
    • Ubicación: CP {datos.codigo_postal} - Barrio: {datos.barrio}
    • Metros Vivienda: {datos.metros_vivienda} m²
    • Estado de Conservación: {estado_descriptivo}
    • Terraza/Balcón: {datos.m2_terraza} m²
    • Plazas de Garaje: {datos.plazas_garaje} plaza(s)
    • Trastero: {datos.m2_trastero} m²
    
    --------------------------------------------------
    🎯 VALORACIÓN ESTIMADA DE MERCADO: {precio_calculado:,.2f} €
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

# 5. EL "CAMARERO" DE TU FORMULARIO (Endpoint de FastAPI)
@app.post("/api/calcular-valoracion")
def calcular_valoracion(datos: DatosCliente, background_tasks: BackgroundTasks):
    
    # A. Descargamos los precios frescos de tu GitHub
    db_precios = cargar_datos_github()
    if not db_precios:
        raise HTTPException(
            status_code=500, 
            detail="La base de datos de precios no está disponible en este momento."
        )

    cp = datos.codigo_postal.strip()
    barrio = datos.barrio.strip()

    # B. Validamos si el Código Postal existe en nuestro JSON
    if cp not in db_precios:
        raise HTTPException(
            status_code=404, 
            detail="Código Postal no disponible en la base de datos."
        )
    
    barrios_disponibles = db_precios[cp]["barrios"]
    
    # C. Validamos si el barrio seleccionado existe dentro de ese CP
    if barrio not in barrios_disponibles:
        raise HTTPException(
            status_code=404, 
            detail=f"El barrio '{barrio}' no está registrado para el CP {cp}."
        )

    # D. Traemos el precio base del metro cuadrado
    precio_base_m2 = barrios_disponibles[barrio]

    # E. Aplicamos los factores correctores de conservación
    factor_estado = 1.0
    if datos.estado_conservacion == 'A':
        factor_estado = 0.80  # Penalización del -20% por reforma
    elif datos.estado_conservacion == 'C':
        factor_estado = 1.15  # Plus del +15% por excelente/obra nueva

    precio_m2_ajustado = precio_base_m2 * factor_estado

    # F. Matemáticas de valoración detallada
    valor_vivienda = datos.metros_vivienda * precio_m2_ajustado
    valor_terraza = datos.m2_terraza * (precio_m2_ajustado * 0.5)      # Al 50% de valor real
    valor_garaje = datos.plazas_garaje * (precio_m2_ajustado * 5)      # Equivalente a 5m² por plaza
    valor_trastero = datos.m2_trastero * (precio_m2_ajustado * 0.5)    # Al 50% de valor real

    precio_final = valor_vivienda + valor_terraza + valor_garaje + valor_trastero

    # G. Mandamos el email al buzón en segundo plano (asíncrono) para no ralentizar la respuesta web
    background_tasks.add_task(enviar_alerta_agente, datos, precio_final)

    # H. Devolvemos la respuesta formateada que el Frontend mostrará al usuario
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