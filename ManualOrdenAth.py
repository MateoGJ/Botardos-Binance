from binance.client import Client
import mysql.connector
import requests
import logging
import time
import datetime
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

# Función para enviar notificación a Telegram
def enviar_notificacion_telegram(mensaje):
    token = '7909332354:AAFiFfZSC3Ws2qqzUHBy5gymM2ff15J97D0'
    chat_id = '1861668101'
    url = f'https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={mensaje}'
    requests.get(url)

# Conectar a la base de datos
def conectar_base_datos():
    try:
        return mysql.connector.connect(**db_config)
    except mysql.connector.Error as err:
        print(f"Error al conectar a la base de datos: {err}")
        return None

# Guardar operación en la base de datos
def guardar_operacion(simbolo, margen, apalancamiento, tipo_operacion, resultado, pnl, fecha_iso):
    try:
        conexion = conectar_base_datos()
        cursor = conexion.cursor()

        # Convertir fecha ISO-8601 a formato MySQL
        fecha_mysql = datetime.datetime.strptime(fecha_iso, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S")

        # Insertar la nueva operación
        sql_insert = """
            INSERT INTO operaciones (simbolo, margen, apalancamiento, tipo_operacion, resultado, pnl, fecha)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        valores = (simbolo, margen, apalancamiento, tipo_operacion, resultado, pnl, fecha_mysql)
        print(f"[DEBUG] Valores a insertar: {valores}")
        
        cursor.execute(sql_insert, valores)
        conexion.commit()
        cursor.close()
        conexion.close()
        print("[LOG] Operación guardada correctamente.")
    except mysql.connector.Error as err:
        print(f"[ERROR] Error al guardar operación en la base de datos: {err}")
        enviar_notificacion_telegram(f"⚠️ Error al guardar operación en la base de datos: {err}")
    except Exception as e:
        print(f"[ERROR] Error inesperado: {e}")
        enviar_notificacion_telegram(f"⚠️ Error inesperado: {e}")





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
    try:
        # Obtener balance disponible y calcular la cantidad de USDT a usar
        balance_disponible = obtener_balance_disponible()
        cantidad_usdt = (porcentaje_cuenta / 100) * balance_disponible
        print(f"[LOG] Usando {cantidad_usdt:.2f} USDT de un balance disponible de {balance_disponible:.2f} USDT")

        # Ajustar apalancamiento
        client.futures_change_leverage(symbol=simbolo, leverage=apalancamiento)

        # Obtener precio actual y precisiones del mercado
        precio_actual = float(client.futures_symbol_ticker(symbol=simbolo)["price"])
        info = client.futures_exchange_info()
        symbol_info = next(filter(lambda x: x['symbol'] == simbolo, info['symbols']))
        step_size = float(next(filter(lambda f: f['filterType'] == 'LOT_SIZE', symbol_info['filters']))['stepSize'])
        min_qty = float(next(filter(lambda f: f['filterType'] == 'LOT_SIZE', symbol_info['filters']))['minQty'])
        tick_size = float(next(filter(lambda f: f['filterType'] == 'PRICE_FILTER', symbol_info['filters']))['tickSize'])

        # Logs de valores obtenidos del mercado
        print(f"[LOG] Precio actual: {precio_actual}")
        print(f"[LOG] Step size: {step_size}, Min qty: {min_qty}, Tick size: {tick_size}")
        print(f"[DEBUG] Símbolo seleccionado: {simbolo}")

        # Calcular la cantidad ajustada
        cantidad_usdt = (porcentaje_cuenta / 100) * balance_disponible
        cantidad = (cantidad_usdt * apalancamiento) / precio_actual
        cantidad_ajustada = ajustar_precision(cantidad, step_size)

        if cantidad_ajustada < min_qty:
            print(f"⚠️ Cantidad ajustada ({cantidad_ajustada}) menor al mínimo ({min_qty}). Usando mínimo permitido.")
            cantidad_ajustada = ajustar_precision(min_qty, step_size)

        # Validar que el precio cumpla con el tick_size
        precio_actual_ajustado = ajustar_precision(precio_actual, tick_size)
        print(f"[LOG] Precio ajustado con tick size: {precio_actual_ajustado}")

        # Validar margen suficiente (opcional, según tu API Key)
        account_info = client.futures_account()
        free_margin = float(account_info['totalMarginBalance'])
        notional_value = precio_actual_ajustado * cantidad_ajustada
        print(f"[LOG] Margen libre: {free_margin}, Valor nocional: {notional_value}")

        if notional_value / apalancamiento > free_margin:
            print(f"⚠️ No hay margen suficiente para operar {cantidad_ajustada} contratos en {simbolo}.")
            return None

        # Enviar la orden
        side = 'BUY' if direccion == 'l' else 'SELL'
        print(f"[LOG] Enviando orden: Lado: {side}, Cantidad: {cantidad_ajustada}")
        orden = client.futures_create_order(
            symbol=simbolo,
            side=side,
            type='MARKET',
            quantity=cantidad_ajustada
        )
        mensaje = f"✅ Orden de {'compra (LONG)' if side == 'BUY' else 'venta (SHORT)'} ejecutada para {simbolo}.\nCantidad: {cantidad_ajustada} | Apalancamiento: {apalancamiento}x"
        print(mensaje)
        logging.info(mensaje)
        enviar_notificacion_telegram(mensaje)

        # Obtener el precio de entrada
        posicion = next(filter(lambda x: x['symbol'] == simbolo, client.futures_position_information()))
        precio_entrada = float(posicion['entryPrice'])
        return precio_entrada, cantidad_ajustada
    except BinanceAPIException as bne:
        logging.error(f"API Exception: {bne}")
        print(f"[ERROR] Binance API Exception: {bne}")
        enviar_notificacion_telegram(f"⚠️ Binance API Exception: {bne}")
        return None
    except Exception as e:
        logging.error(f"Error al crear la orden: {e}")
        print(f"[ERROR] Error al crear la orden: {e}")
        enviar_notificacion_telegram(f"⚠️ Error al crear la orden: {e}")
        return None



# Configuración de PP con ajustes progresivos
pp_configurations = {
    "tendencial": {"nivel_roi_inicial": 40, "incremento_nivel_roi": 20, "primer_ajuste_sl": 25, "incremento_sl_post": 20},
    "moderada": {"nivel_roi_inicial": 30, "incremento_nivel_roi": 20, "primer_ajuste_sl": 10, "incremento_sl_post": 20},
    "conservadora": {"nivel_roi_inicial": 33, "incremento_nivel_roi": 20, "primer_ajuste_sl": 20, "incremento_sl_post": 23},
    
}

# Monitoreo de ROI y ajuste dinámico de SL basado en configuraciones de PP
def monitorear_roi_con_pp(config, tp_porcentaje, pp_activado, simbolo, cantidad, apalancamiento, direccion):
    nivel_roi = config["nivel_roi_inicial"]
    sl_dinamico = -sl_porcentaje  # Stop Loss inicial negativo
    primer_ajuste_realizado = False

    try:
        while True:
            # Obtener información de la posición
            posicion = next(filter(lambda x: x['symbol'] == simbolo, client.futures_position_information()))
            unrealized_pnl = float(posicion['unRealizedProfit'])
            precio_entrada = float(posicion['entryPrice'])

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
                mensaje = f"🔒 Profit Protection ajustado a {sl_dinamico:.2f}%. PNL: {unrealized_pnl:.2f}$ USDT. ROI Actual: {roi:.2f}%."
                print(mensaje)
                enviar_notificacion_telegram(mensaje)

            print(f"ROI: {roi:.2f}% | PNL: {unrealized_pnl:.2f} USDT | SL Dinámico: {sl_dinamico:.2f}%")

            # Evaluar cierre de posición
            if roi <= sl_dinamico:
                estado = "SL"
                resultado = roi
                mensaje = f"🔴 SL alcanzado: ROI: {roi:.2f}%, PNL: {unrealized_pnl:.2f} USDT"
                print(mensaje)
                enviar_notificacion_telegram(mensaje)
                cerrar_operacion(simbolo, cantidad, direccion, estado, resultado, unrealized_pnl)
                return estado
            elif roi >= tp_porcentaje:
                estado = "TP"
                resultado = nivel_roi
                mensaje = f"🎉 TP alcanzado: ROI: {roi:.2f}%, PNL: {unrealized_pnl:.2f} USDT"
                enviar_notificacion_telegram(mensaje)
                cerrar_operacion(simbolo, cantidad, direccion, estado, resultado, unrealized_pnl)
                return estado

            time.sleep(0.07)
    except Exception as e:
        logging.error(f"Error en el monitoreo de ROI: {e}")
        print(f"Error en el monitoreo de ROI: {e}")
        enviar_notificacion_telegram(f"⚠️ Error en el monitoreo de ROI: {e}")
        estado = "None"
        return estado



def cerrar_operacion(simbolo, cantidad, direccion, estado, resultado, pnl_final):
    try:
        # Cierra la posición
        client.futures_create_order(
            symbol=simbolo,
            side='SELL' if direccion == 'l' else 'BUY',
            type='MARKET',
            quantity=cantidad,
            reduceOnly=True
        )

        # Guardar operación en la base de datos
        fecha_iso = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        guardar_operacion(
            simbolo=simbolo,
            margen=cantidad,  # Calculado antes
            apalancamiento=apalancamiento,
            tipo_operacion="BUY" if direccion == "l" else "SELL",
            resultado=resultado,
            pnl=pnl_final,
            fecha_iso=fecha_iso
        )


    except Exception as e:
        logging.error(f"[ERROR] Error al cerrar operación: {e}")
        print(f"[ERROR] Error al cerrar operación: {e}")
        return False


# Parámetros de proximidad al ATH
ath_proximity_percentage = float(input("Ingresa la proximidad al ath (ej. 1.1): "))  # Proximidad máxima al ATH en porcentaje

# Lista de símbolos a excluir de la búsqueda (por ejemplo, USDCUSDT)
excepciones = ["USDCUSDT", "USDTBUSD", "ETHUSDT", "BTCUSDT", "BTCUSDT_250328", "BTCUSDT_241227"]  # Puedes añadir otros símbolos aquí

def get_ath(symbol):
    """Obtiene el ATH de un mercado de futuros en las últimas 52 semanas."""
    klines = client.futures_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1WEEK, limit=11)
    high_prices = [float(kline[2]) for kline in klines]
    return max(high_prices)

def obtener_simbolos_cercanos_al_ath():
    """Obtiene los 3 símbolos más cercanos al ATH entre los mercados USDT perpetuos."""
    print("🔍 Buscando los 3 símbolos más cercanos al ATH en futuros perpetuos USDT...")
    try:
        futures_info = client.futures_exchange_info()
        usdt_markets = [
            symbol['symbol'] for symbol in futures_info['symbols']
            if symbol['quoteAsset'] == 'USDT' and 
               symbol['status'] == 'TRADING' and 
               symbol['contractType'] == 'PERPETUAL' and
               symbol['symbol'] not in excepciones
        ]
        print(f"[DEBUG] Total mercados perpetuos USDT: {len(usdt_markets)}")

        # Buscar los mercados más cercanos al ATH
        closest_markets = find_closest_markets_to_ath(usdt_markets, top_n=3)
        if closest_markets:
            print(f"✅ Símbolos más cercanos al ATH encontrados: {closest_markets}")
            return closest_markets
        else:
            print(":)")
            return []
    except Exception as e:
        print(f"❌ Error al obtener los mercados de futuros: {e}")
        return []


def find_closest_markets_to_ath(markets, top_n=3):
    """Encuentra los mercados más cercanos al ATH dentro de un rango especificado."""
    proximity_list = []
    
    for symbol in markets:
        try:
            ath = get_ath(symbol)
            ticker_info = client.futures_symbol_ticker(symbol=symbol)
            current_price = float(ticker_info.get('price', 0))
            if current_price == 0:
                continue  # Omitir si no hay precio
            
            proximity_percentage = ((ath - current_price) / ath) * 100
            if 0 <= proximity_percentage <= ath_proximity_percentage:
                proximity_list.append((symbol, proximity_percentage))
        except BinanceAPIException as e:
            print(f"[DEBUG] Error en símbolo {symbol}: {e}")
            continue
        except Exception as e:
            print(f"[ERROR] Problema inesperado con {symbol}: {e}")
    
    # Ordenar por proximidad y devolver los top_n mercados
    proximity_list.sort(key=lambda x: x[1])
    return [symbol for symbol, _ in proximity_list[:top_n]]

def monitorear_mercados(market_list):
    """Monitorea múltiples mercados y reacciona si alguno rompe su ATH."""
    tiempo_inicio = time.time()  # Registrar el tiempo inicial
    while True:
        for symbol in market_list:
            try:
                ath = get_ath(symbol)
                ticker_info = client.futures_symbol_ticker(symbol=symbol)
                current_price = float(ticker_info.get('price', 0))
                if current_price < ath:
                    print(f"🔍 Monitoreando {symbol}: Precio: {current_price}, ATH: {ath}")
                
                elif current_price > ath:
                    print(f"🎉 {symbol} rompió su ATH: Precio actual {current_price} > ATH {ath}")
                    enviar_notificacion_telegram(f"🎉 {symbol} rompió su ATH: Precio actual {current_price}")
                    
                    # Ejecutar orden
                    precio_entrada, cantidad_ajustada = crear_orden(symbol, porcentaje_cuenta, apalancamiento, direccion)
                    if precio_entrada and cantidad_ajustada:
                        estado = monitorear_roi_con_pp(config, tp_porcentaje, pp_activado, symbol, cantidad_ajustada, apalancamiento, direccion)
                        return  # Salir tras la operación exitosa
                    
            except BinanceAPIException as e:
                print(f"[ERROR] Error en API de Binance con {symbol}: {e}")
            except Exception as e:
                print(f"[ERROR] Error al monitorear {symbol}: {e}")
        
        # Comprobar si han pasado 7 minutos
        tiempo_actual = time.time()
        if tiempo_actual - tiempo_inicio >= 1020:  # 7 minutos = 420 segundos
            print("⏳ Han pasado 7 minutos, actualizando la lista de mercados...")
            market_list = obtener_simbolos_cercanos_al_ath()  # Actualizar la lista de mercados
            tiempo_inicio = tiempo_actual  # Reiniciar el tiempo inicial

        time.sleep(0.1)  # Intervalo de monitoreo (ajustable)




if __name__ == "__main__":
    # Solicita los parámetros iniciales
    porcentaje_cuenta = float(input("Ingresa el porcentaje de tu cuenta para usar en cada operación (ej. 5 para 5%): "))
    apalancamiento = int(input("Ingresa el apalancamiento deseado: "))
    direccion = input("¿Deseas operar en LONG (l) o SHORT (s)?: ").strip().lower()
    tp_porcentaje = 99997777
    sl_porcentaje = float(input("Ingresa el porcentaje de Stop Loss (ej. 50): "))
    pp_activado = "si"

    print("Selecciona el perfil de Profit Protection:")
    print("1. Tendencial")
    print("2. Moderada")
    print("3. Conservadora")
    config_choice = input("Elige una opción (1/2/3): ").strip()
    config = pp_configurations["tendencial"] if config_choice == "3" else \
             pp_configurations["moderada"] if config_choice == "2" else \
             pp_configurations["conservadora"] if config_choice == "1" else \
             print("no elegiste na /;")
    
     # Buscar los 3 mercados más cercanos al ATH
    mercados_cercanos = obtener_simbolos_cercanos_al_ath()

    if not mercados_cercanos:
        print("❌ No hay mercados cercanos al ATH. Finalizando...")
    else:
        print(f"📊 Monitoreando mercados: {mercados_cercanos}")
        monitorear_mercados(mercados_cercanos)
