import requests

# Tu enlace a GitHub (asegúrate de que es main o master)
URL_DATOS = "https://raw.githubusercontent.com/ByZeleon/valorador-de-immuebles/main/pricesDB.json"

def cargar_datos():
    print("Conectando con la base de datos...")
    try:
        respuesta = requests.get(URL_DATOS)
        if respuesta.status_code == 200:
            return respuesta.json()
        return None
    except:
        return None

def realizar_tasacion():
    db_precios = cargar_datos()
    if not db_precios:
        print("Error al conectar con GitHub. Saliendo del programa.")
        return

    print("\n" + "="*50)
    print(" 🏡 VALORADOR INMOBILIARIO AVANZADO (Por Barrios)")
    print("="*50)

    ficha = {}

    # --- 1. UBICACIÓN Y BARRIOS ---
    cp = input("\n📍 1. Código Postal: ").strip()
    
    if cp in db_precios:
        zona = db_precios[cp]
        print(f"\n🗺️ Municipio detectado: {zona['municipio']}")
        print("¿En qué barrio se encuentra el inmueble?")
        
        # Extraemos los barrios y mostramos el menú
        nombres_barrios = list(zona["barrios"].keys())
        for i, barrio in enumerate(nombres_barrios):
            print(f"  {i + 1}. {barrio}")
            
        try:
            opcion = int(input("\nElige el número del barrio: "))
            barrio_elegido = nombres_barrios[opcion - 1]
            precio_base_m2 = zona["barrios"][barrio_elegido]
            
            print(f"   -> Seleccionado: {barrio_elegido}. Precio base: {precio_base_m2} €/m²")
            ficha["Ubicación"] = f"{zona['municipio']} - {barrio_elegido} (CP: {cp})"
        except (ValueError, IndexError):
            print("❌ Opción inválida. Debes introducir el número correcto.")
            return
    else:
        print("❌ No tenemos datos para ese Código Postal en la base de datos.")
        return

    # --- 2. METROS CUADRADOS ---
    try:
        metros_vivienda = float(input("\n📐 2. Metros cuadrados de la vivienda: "))
        ficha["Metros Vivienda"] = f"{metros_vivienda} m²"
    except ValueError:
        print("❌ Error: Debes introducir un número.")
        return

    # --- 3. ESTADO DEL INMUEBLE (Factor Multiplicador) ---
    print("\n🛠️ 3. Estado de conservación:")
    print("   A - A reformar")
    print("   B - Buen estado")
    print("   C - Excelente / Obra nueva")
    estado = input("   Elige (A/B/C): ").strip().upper()
    
    factor_estado = 1.0
    if estado == 'A':
        factor_estado = 0.80
        ficha["Estado"] = "A reformar"
    elif estado == 'C':
        factor_estado = 1.15
        ficha["Estado"] = "Excelente"
    else:
        ficha["Estado"] = "Buen estado"

    precio_m2_ajustado = precio_base_m2 * factor_estado

    # --- 4. EXTRAS (Terraza, Garaje, Trastero) ---
    valor_terraza = 0
    tiene_terraza = input("\n☀️ 4. ¿Tiene terraza o balcón? (S/N): ").strip().upper()
    if tiene_terraza == 'S':
        try:
            m2_terraza = float(input("   ¿Cuántos metros cuadrados?: "))
            valor_terraza = m2_terraza * (precio_m2_ajustado * 0.5)
            ficha["Terraza"] = f"Sí, {m2_terraza} m²"
        except ValueError: pass
    else: ficha["Terraza"] = "No"

    valor_garaje = 0
    tiene_garaje = input("\n🚗 5. ¿Tiene plaza de garaje? (S/N): ").strip().upper()
    if tiene_garaje == 'S':
        try:
            plazas = int(input("   ¿Cuántas plazas?: "))
            valor_garaje = plazas * (precio_m2_ajustado * 5)
            ficha["Garaje"] = f"Sí, {plazas} plaza(s)"
        except ValueError: pass
    else: ficha["Garaje"] = "No"

    valor_trastero = 0
    tiene_trastero = input("\n📦 6. ¿Tiene trastero? (S/N): ").strip().upper()
    if tiene_trastero == 'S':
        try:
            m2_trastero = float(input("   ¿Cuántos metros cuadrados?: "))
            valor_trastero = m2_trastero * (precio_m2_ajustado * 0.5)
            ficha["Trastero"] = f"Sí, {m2_trastero} m²"
        except ValueError: pass
    else: ficha["Trastero"] = "No"

    # --- MATEMÁTICAS FINALES ---
    valor_base_vivienda = metros_vivienda * precio_m2_ajustado
    valor_total = valor_base_vivienda + valor_terraza + valor_garaje + valor_trastero
    
    ficha["Precio Base Barrio"] = f"{precio_base_m2:,.2f} €/m²"
    ficha["Valoración Final"] = f"{valor_total:,.2f} €"

    # --- RESULTADOS ---
    print("\n" + "*"*50)
    print(f" 🎯 VALOR ESTIMADO TOTAL: {valor_total:,.2f} €")
    print("*"*50)
    
    print("\n--- DESGLOSE DEL PRECIO ---")
    print(f"Valor interior vivienda: {valor_base_vivienda:,.2f} €")
    if valor_terraza > 0: print(f"Valor extra por terraza: +{valor_terraza:,.2f} €")
    if valor_garaje > 0: print(f"Valor extra por garaje: +{valor_garaje:,.2f} €")
    if valor_trastero > 0: print(f"Valor extra por trastero: +{valor_trastero:,.2f} €")

    print("\n" + "-"*50)
    print(" 📩 FICHA REGISTRADA PARA EL AGENTE INMOBILIARIO")
    print("-" * 50)
    for clave, valor in ficha.items():
        print(f"{clave}: {valor}")

if __name__ == "__main__":
    realizar_tasacion()