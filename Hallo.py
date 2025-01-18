from binance.client import Client
import mysql.connector
import requests
import logging
import time
import datetime
import pytz
from decimal import Decimal, ROUND_DOWN
from binance.client import Client
from binance.exceptions import BinanceAPIException

# Inicializa la API de Binance
client = Client(api_key='MoAcsgKcNJFW1oXGqnKHm9sgn4iIMXtiDkdohXyjhdwevXQMEl9zTVXrOKYEefIp', 
                api_secret='bBnH4g7LsLyN93cm38pWAsmTw8XNmV2HPXTpoCN4MmUZ66LxczHKpCt0H1FCQchW')

# Configuración de MySQL
db_config = {
    'user': 'root',
    'password': 'maximiliano1o1o',
    'host': 'localhost',
    'database': 'trading_db'
}

# Configuración de logging
logging.basicConfig(filename='operaciones.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Función para enviar notificación a diferentes chats de Telegram
def enviar_notificacion_telegram(mensaje, tipo):
    
    if tipo == 1:  # Para SL negativo
        token = '7988085883:AAFuFjqMn-XZ9t3g2qBRlwscH5fFzrQOiDs'
        chat_id = '1861668101'  # Reemplaza con el ID del chat para pérdidas
    else:  # Para SL positivo o TP
        token = '7909332354:AAFiFfZSC3Ws2qqzUHBy5gymM2ff15J97D0'
        chat_id = '1861668101'  # Reemplaza con el ID del chat para ganancias/protección
    
    url = f'https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={mensaje}'
    requests.get(url)


# Conectar a la base de datos
def conectar_base_datos():
    try:
        return mysql.connector.connect(**db_config)
    except mysql.connector.Error as err:
        print(f"Error al conectar a la base de datos: {err}")
        return None


# Lista de símbolos a excluir de la búsqueda (por ejemplo, USDCUSDT)
excepciones = ["DGBUSDT", "OCEANUSDT", "ETHUSDT", "BTCUSDT", "RAYSOLUSDT", "SPELLUSDT", "AGIXUSDT"]  # Puedes añadir otros símbolos aquí

# Función para obtener los 10 mercados con mayor cambio positivo en 24 horas
def obtener_mercados_mayor_cambio():
    try:
        mercados = client.futures_ticker()
        
        # Filtrar solo los mercados que terminan en "USDT" y no están en excepciones
        mercados_usdt = [mercado for mercado in mercados if mercado['symbol'].endswith('USDT') and mercado['symbol'] not in excepciones]

        # Filtrar solo los mercados con cambio positivo en 24 horas
        mercados_positivos = [mercado for mercado in mercados_usdt if float(mercado['priceChangePercent']) > 0]

        # Ordenar los mercados por el cambio porcentual de precio (descendente)
        mercados_ordenados = sorted(mercados_positivos, key=lambda x: float(x['priceChangePercent']), reverse=True)
        top_10 = mercados_ordenados[:10]

        # Obtener el precio del heatmap para cada mercado
        mercados_con_heatmap = []
        for mercado in top_10:
            simbolo = mercado['symbol']
            precio_heatmap = obtener_precio_heatmap(simbolo)  # Aquí usamos el símbolo del mercado
            if precio_heatmap:
                mercados_con_heatmap.append({'symbol': simbolo, 'heatmap_price': precio_heatmap})

        return mercados_con_heatmap
    except Exception as e:
        logging.error(f"Error al obtener mercados: {e}")
        print(f"Error al obtener mercados: {e}")
        return []

# Función para calcular precio del heatmap
def obtener_precio_heatmap(simbolo):
    try:
        depth = client.futures_order_book(symbol=simbolo)
        bids = depth.get('bids', [])
        if not bids:
            print(f"⚠️ No se encontraron órdenes de compra para {simbolo}.")
            return None
        max_bid = max(bids, key=lambda x: float(x[1]))
        return float(max_bid[0])
    except Exception as e:
        logging.error(f"Error al obtener precio del heatmap: {e}")
        return None


# Guardar operación en la base de datos
def guardar_operacion(simbolo, margen, apalancamiento, tipo_operacion, resultado, pnl, fecha_iso, duracion):
    try:
        conexion = conectar_base_datos()
        cursor = conexion.cursor()

        # Convertir fecha ISO-8601 (UTC) a formato MySQL con zona horaria local
        utc_timezone = pytz.utc
        local_timezone = pytz.timezone("America/Argentina/Buenos_Aires")  # Cambia esto a tu zona horaria
        
        # Parsear fecha ISO y convertirla a la zona local
        fecha_utc = utc_timezone.localize(datetime.datetime.strptime(fecha_iso, "%Y-%m-%dT%H:%M:%SZ"))
        fecha_local = fecha_utc.astimezone(local_timezone)
        fecha_mysql = fecha_local.strftime("%Y-%m-%d %H:%M:%S")

        # Insertar la nueva operación
        sql_insert = """
            INSERT INTO bot24operaciones (simbolo, margen, apalancamiento, tipo_operacion, resultado, pnl, fecha, duracion)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        valores = (simbolo, margen, apalancamiento, tipo_operacion, resultado, pnl, fecha_mysql, duracion)
        print(f"[DEBUG] Valores a insertar: {valores}")
        
        cursor.execute(sql_insert, valores)
        conexion.commit()
        cursor.close()
        conexion.close()
        print("[LOG] Operación guardada correctamente.")
    except mysql.connector.Error as err:
        print(f"[ERROR] Error al guardar operación en la base de datos: {err}")
    except Exception as e:
        print(f"[ERROR] Error inesperado: {e}")




# Ajustar la cantidad y el precio según las especificaciones del mercado
def ajustar_precision(valor, step_size):
    """
    Ajusta un valor numérico para que sea múltiplo de step_size.
    """
    precision = Decimal(str(step_size))
    valor_ajustado = (Decimal(valor) // precision) * precision
    return float(valor_ajustado)


def obtener_balance_disponible():
    try:
        cuenta = client.futures_account()
        balance_disponible = float(cuenta['availableBalance'])
        return balance_disponible
    except Exception as e:
        logging.error(f"Error al obtener balance: {e}")
        print(f"Error al obtener balance: {e}")
        return 0


# Función para ejecutar la orden de compra/venta
def crear_orden(simbolo, porcentaje_cuenta, apalancamiento, direccion):
    """
    Crea una orden de compra o venta en el mercado de futuros de Binance.
    """
    try:
        # Obtener balance disponible y calcular la cantidad de USDT a usar
        balance_disponible = obtener_balance_disponible()
        cantidad_usdt = (porcentaje_cuenta / 100) * balance_disponible

        # Ajustar apalancamiento dinámicamente
        try:
            leverage_brackets = client.futures_leverage_bracket()
            symbol_leverage_info = next(filter(lambda x: x['symbol'] == simbolo.upper(), leverage_brackets))
            max_leverage = symbol_leverage_info['brackets'][0]['initialLeverage']

            if apalancamiento > max_leverage:
                print(f"⚠️ Apalancamiento ingresado ({apalancamiento}) supera el máximo permitido ({max_leverage}). Ajustando al máximo permitido.")
                apalancamiento = max_leverage

            client.futures_change_leverage(symbol=simbolo.upper(), leverage=apalancamiento)
            print(f"✅ Apalancamiento configurado a {apalancamiento}x para {simbolo.upper()}.")

        except Exception as e:
            print(f"[ERROR] Error al ajustar el apalancamiento: {e}")
            return None

        # Obtener precio actual y especificaciones del mercado
        precio_actual = float(client.futures_symbol_ticker(symbol=simbolo.upper())["price"])
        info = client.futures_exchange_info()
        symbol_info = next(filter(lambda x: x['symbol'] == simbolo.upper(), info['symbols']))
        step_size = float(next(filter(lambda f: f['filterType'] == 'LOT_SIZE', symbol_info['filters']))['stepSize'])
        min_qty = float(next(filter(lambda f: f['filterType'] == 'LOT_SIZE', symbol_info['filters']))['minQty'])
        tick_size = float(next(filter(lambda f: f['filterType'] == 'PRICE_FILTER', symbol_info['filters']))['tickSize'])
        min_notional = float(next(filter(lambda f: f['filterType'] == 'MIN_NOTIONAL', symbol_info['filters']))['notional'])

        print(f"\n[LOG] Precio actual: {precio_actual}")

        # Calcular cantidad ajustada
        print(f"cantidad_usdt: {cantidad_usdt:.2f}")
        cantidad = (cantidad_usdt * apalancamiento) / precio_actual
        cantidad_ajustada = ajustar_precision(cantidad, step_size)

        print(f"cantidad_ajustada: {cantidad_ajustada:.2f}")

        # Validar si la cantidad cumple con los requisitos mínimos
        if cantidad_ajustada < min_qty:
            cantidad_ajustada = ajustar_precision(min_qty, step_size)
            cantidad_usdt = cantidad_ajustada * precio_actual / apalancamiento
            print(f"[LOG] Cantidad ajustada por cantidad mínima permitida: {cantidad_ajustada:.2f} - {cantidad_usdt:.2f}$")
            print(f"\nUsando {cantidad_usdt:.2f} USDT para esta operación (Balance: {balance_disponible:.2f} USDT)")

        # Validar si hay margen suficiente
        free_margin = obtener_balance_disponible()
        if (cantidad_ajustada * precio_actual) / apalancamiento > free_margin:
            print(f"⚠️ No hay margen suficiente para operar {cantidad_usdt:.2f}$ en {simbolo}.")
            return None

        # Enviar la orden
        side = 'BUY' if direccion == 'l' else 'SELL'
        cantidad_ajustada = round(cantidad_ajustada, 2)  # Redondear a dos decimales

        while True:
            try:
                orden = client.futures_create_order(
                    symbol=simbolo.upper(),
                    side=side,
                    type='MARKET',
                    quantity=cantidad_ajustada
                )
                break
            except Exception as e:
                error_message = str(e)
                if "notional must be no smaller than" in error_message:
                    print("[ERROR] Orden rechazada: valor nocional menor al mínimo permitido. Ajustando cantidad...")
                    min_notional += 1  # Incrementar ligeramente el mínimo
                    cantidad_ajustada = ajustar_precision(min_notional / precio_actual, step_size)
                    cantidad_usdt = cantidad_ajustada * precio_actual / apalancamiento  # Actualizar cantidad_usdt
                    print(f"[LOG] Cantidad ajustada por valor nocional mínimo: {cantidad_ajustada:.2f} - {cantidad_usdt:.2f}$")
                    print(f"\nUsando {cantidad_usdt:.2f} USDT para esta operación (Balance: {balance_disponible:.2f} USDT)")
                else:
                    logging.error(f"Error al crear la orden: {e}")
                    print(f"[ERROR] Error al crear la orden: {e}")
                    return None

        mensaje = f" \n✅ Orden de {'compra (LONG)' if side == 'BUY' else 'venta (SHORT)'} ejecutada para {simbolo.upper()}.\nCantidad: {cantidad_usdt:.2f}$$ | Apalancamiento: {apalancamiento}x \n"
        print(mensaje)
        logging.info(mensaje)
        enviar_notificacion_telegram(mensaje, tipo="positivo")

        # Retornar detalles de la orden
        precio_entrada = float(next(filter(lambda x: x['symbol'] == simbolo.upper(), client.futures_position_information()))['entryPrice'])
        timestamp_inicio = time.time()
        return precio_entrada, cantidad_ajustada, cantidad_usdt, apalancamiento, timestamp_inicio

    except Exception as e:
        logging.error(f"Error al crear la orden: {e}")
        print(f"[ERROR] Error al crear la orden: {e}")
        return None







# Configuración de PP con ajustes progresivos
pp_configurations = {
    "tendencial": {"nivel_roi_inicial": 60, "incremento_nivel_roi": 75, "primer_ajuste_sl": 31, "incremento_sl_post": 69},
    "moderada": {"nivel_roi_inicial": 40, "incremento_nivel_roi": 40, "primer_ajuste_sl": 31, "incremento_sl_post": 31},
    "conservadora": {"nivel_roi_inicial": 25, "incremento_nivel_roi": 23, "primer_ajuste_sl": 22, "incremento_sl_post": 22},
    
}

# Monitoreo de ROI y ajuste dinámico de SL basado en configuraciones de PP
def monitorear_roi_con_pp(config, tp_porcentaje, pp_activado, simbolo, cantidad, cantidad_usdt, apalancamiento, direccion):
    nivel_roi = config["nivel_roi_inicial"]
    sl_dinamico = -sl_porcentaje  # Stop Loss inicial negativo
    primer_ajuste_realizado = False

    # Registrar el inicio de la operación
    timestamp_inicio = time.time()

    try:
        while True:
            # Obtener información de la posición
            posicion = next(filter(lambda x: x['symbol'] == simbolo, client.futures_position_information()))
            unrealized_pnl = float(posicion['unRealizedProfit'])
            precio_entrada = float(posicion['entryPrice'])
            precio_actual = float(client.futures_symbol_ticker(symbol=simbolo)["price"])

            # Calcular la duración de la operación
            # Calcular la duración de la operación
            timestamp_actual = time.time()
            duracion_segundos = int(timestamp_actual - timestamp_inicio)
            duracion_formateada = f"{duracion_segundos // 60}m {duracion_segundos % 60}s"
            duracion = time.time() - timestamp_inicio
            minutos = int(duracion // 60)
            segundos = int(duracion % 60)


            # Calcular ROI utilizando el apalancamiento proporcionado
            roi = (unrealized_pnl / (precio_entrada * cantidad)) * apalancamiento * 100 if cantidad > 0 else 0

            # Profit Protection: Ajustar SL dinámico
            if pp_activado and roi >= nivel_roi:
                if not primer_ajuste_realizado:
                    sl_dinamico = config["primer_ajuste_sl"]
                    primer_ajuste_realizado = True
                else:
                    sl_dinamico += config["incremento_sl_post"]
                nivel_roi += config["incremento_nivel_roi"]
                mensaje = f"🔒 Profit Protection ajustado a {sl_dinamico:.2f}%. PNL: {(sl_dinamico * cantidad_usdt) / 100:.2f}$ USDT. ROI: {roi:.2f}% - {minutos}m {segundos}s."
                print(mensaje)
                enviar_notificacion_telegram(mensaje, tipo="positivo")
                
            
            if sl_dinamico == -sl_porcentaje:
                print(f"ROI: {roi:.2f}% | Precio: {precio_actual:.5f}$ | PNL: {unrealized_pnl:.2f}$ | SL: {sl_dinamico:.2f}% | Duración: {duracion_formateada}")
            if sl_dinamico >= 0:
                print(f"ROI: {roi:.2f}% | Precio: {precio_actual:.5f}$ | PNL: {unrealized_pnl:.2f}$ | PP: {sl_dinamico:.2f}% | Duración: {duracion_formateada}")

            # Evaluar cierre de posición
            if roi <= sl_dinamico:
                estado = "SL"
                resultado = roi
                print(f"precio de cierre: {precio_actual:.5f}")
                cerrar_operacion(simbolo, cantidad, cantidad_usdt, direccion, estado, resultado, unrealized_pnl, timestamp_inicio)
                return estado
            elif roi >= tp_porcentaje:
                estado = "TP"
                resultado = nivel_roi
                print(f"precio de cierre: {precio_actual:.5f}")
                cerrar_operacion(simbolo, cantidad, cantidad_usdt, direccion, estado, resultado, unrealized_pnl, timestamp_inicio)
                return estado

            time.sleep(0.07)
    except Exception as e:
        logging.error(f"Error en el monitoreo de ROI: {e}")
        print(f"Error en el monitoreo de ROI: {e}")
        estado = "None"
        return estado

def cerrar_operacion(simbolo, cantidad, cantidad_usdt, direccion, estado, resultado, pnl_final, timestamp_inicio):
    try:
        # Calcular la duración de la operación
        duracion = time.time() - timestamp_inicio
        minutos = int(duracion // 60)
        segundos = int(duracion % 60)

        # Cerrar posición
        client.futures_create_order(
            symbol=simbolo,
            side='SELL' if direccion == 'l' else 'BUY',
            type='MARKET',
            quantity=cantidad,
            reduceOnly=True
        )
        
        # Guardar operación en la base de datos
        guardar_operacion(
            simbolo=simbolo,
            margen=cantidad_usdt,
            apalancamiento=apalancamiento,
            tipo_operacion="BUY" if direccion == "l" else "SELL",
            resultado=resultado,
            pnl=pnl_final,
            fecha_iso=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            duracion=duracion
        )
        # Mensaje y envío a Telegram
        if estado == "SL" and pnl_final < 0:
            mensaje = f"🔴 SL alcanzado. PNL Final: {pnl_final:.2f} USDT - ROI: {resultado:.2f}% - Mercado: {simbolo}"
            print(f"La operación estuvo abierta durante {minutos} minutos y {segundos} segundos.")
            enviar_notificacion_telegram(mensaje, tipo=1)
        else:
            mensaje = f"🎉Profit protegido alcanzado🎉               PNL: {pnl_final:.2f} USDT  -  ROI: {resultado:.2f}%"
            print(f"La operación estuvo abierta durante {minutos} minutos y {segundos} segundos.")
            enviar_notificacion_telegram(mensaje, tipo="positivo")
        
        print(mensaje)
    except Exception as e:
        logging.error(f"Error al cerrar operación: {e}")
        print(f"[ERROR] Error al cerrar operación: {e}")




if __name__ == "__main__":
    porcentaje_cuenta = float(input("Ingresa el porcentaje de tu cuenta para usar en cada operación (ej. 5 para 5%): "))
    apalancamiento = int(input("Ingresa el apalancamiento deseado: "))
    direccion = input("¿Deseas operar en LONG (l) o SHORT (s)?: ").strip().lower()
    tp_porcentaje = 8888
    sl_porcentaje = float(input("Ingresa el porcentaje de Stop Loss (ej. 50): "))
    pp_activado = "s"

    print("Selecciona la configuración de Profit Protection (PP):")
    print("1. Tendencial (la sigue de lejito)")
    print("2. Moderada (le pisa las patas)")
    print("3. Conservadora (no sale ni a la esquina, cierra +20%)")
    config_choice = input("Elige una opción (1/2/3): ").strip()
    config = pp_configurations["tendencial"] if config_choice == "1" else \
         pp_configurations["moderada"] if config_choice == "2" else \
         pp_configurations["conservadora"] if config_choice == "3" else None

    if not config:
        print("no elegiste na /;")
        exit()

    apalaX = apalancamiento
             


    # Paso 1: Obtener mercados y HeatMap
    mercados = obtener_mercados_mayor_cambio()
    if not mercados:
        print("⚠️ No se encontraron mercados para monitorear. Intenta más tarde.")
        exit()

    print("📊 Mercados detectados:")
    for i, mercado in enumerate(mercados, 1):
        print(f"{i}. {mercado['symbol']} - Precio HeatMap: {mercado['heatmap_price']}")

    ath_dict = {m['symbol']: m['heatmap_price'] for m in mercados}
    tiempo_inicio = time.time()

    while True:
        balance_disponible = obtener_balance_disponible()
        cantidad_usdt = (porcentaje_cuenta / 100) * balance_disponible
        print(f"\nUsando {cantidad_usdt:.2f} USDT para esta operación (Balance: {balance_disponible:.2f} USDT)")

        for mercado in mercados:
            simbolo = mercado['symbol']
            precio_objetivo = ath_dict[simbolo]

            try:
                ticker_info = client.futures_symbol_ticker(symbol=simbolo)
                precio_actual = float(ticker_info['price'])
                
                # Calcular la distancia en porcentaje al precio objetivo
                if precio_objetivo > 0:
                    distancia_porcentaje = ((precio_actual - precio_objetivo) / precio_objetivo) * 100
                else:
                    distancia_porcentaje = 0
                
                # Mostrar la información en la consola
                print(f"🔍 Monitoreando: {simbolo} - 📈 Precio: {precio_actual:.5f} - HeatMap: {precio_objetivo:.5f} - 📊 Distancia: {distancia_porcentaje:.2f}%")

                # Activar orden si la distancia es menor o igual a 0.3%
                if abs(distancia_porcentaje) <= 0.3:
                    print(f"🚀 Activando operación en {simbolo}")
                    orden_inicial = crear_orden(simbolo, porcentaje_cuenta, apalaX, direccion)
                    
                    if orden_inicial:
                        precio_entrada, cantidad, cantidad_usdt, apalancamiento, _ = orden_inicial  # Ajusta según los valores devueltos
                        tiempo_inicio = time.time()  # Registrar tiempo de inicio
                        
                        estado = monitorear_roi_con_pp(config, tp_porcentaje, pp_activado, simbolo, cantidad, cantidad_usdt, apalancamiento, direccion)
                        
                        # Salir del monitoreo de este mercado si se ejecuta la operación
                        mercados.remove(mercado)

            except BinanceAPIException as e:
                print(f"⚠️ Error en la API de Binance con {simbolo}: {e}")
            except Exception as e:
                print(f"⚠️ Error al monitorear {simbolo}: {e}")

        # Actualizar lista de mercados cada cierto tiempo
        tiempo_actual = time.time()
        if tiempo_actual - tiempo_inicio >= 660:
            print("⏳ Ha pasado varios minutos, actualizando la lista de mercados...")
            mercados = obtener_mercados_mayor_cambio()
            ath_dict = {m['symbol']: m['heatmap_price'] for m in mercados}
            tiempo_inicio = tiempo_actual

        time.sleep(0.1)  # Intervalo corto para monitorear rápidamente