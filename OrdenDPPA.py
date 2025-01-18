from binance.client import Client
import mysql.connector
import requests
import logging
import time
import datetime
from decimal import Decimal, ROUND_DOWN

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

        # Calcular la cantidad ajustada
        cantidad = (cantidad_usdt * apalancamiento) / precio_actual
        cantidad_ajustada = ajustar_precision(cantidad, step_size)
        print(f"[LOG] Cantidad calculada: {cantidad}, Cantidad ajustada: {cantidad_ajustada}")

        # Validar que la cantidad no sea menor a la cantidad mínima permitida
        if cantidad_ajustada < min_qty:
            print(f"⚠️ La cantidad ajustada ({cantidad_ajustada}) es menor a la mínima permitida ({min_qty}) para {simbolo}.")
            cantidad_ajustada = ajustar_precision(min_qty, step_size)
            print(f"[LOG] Cantidad ajustada a la mínima permitida: {cantidad_ajustada}")

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
        enviar_notificacion_telegram(mensaje, tipo="positivo")

        # Obtener el precio de entrada
        posicion = next(filter(lambda x: x['symbol'] == simbolo, client.futures_position_information()))
        precio_entrada = float(posicion['entryPrice'])
        return precio_entrada, cantidad_ajustada
    except Exception as e:
        logging.error(f"Error al crear la orden: {e}")
        print(f"[ERROR] Error al crear la orden: {e}")
        return None




# Configuración de PP con ajustes progresivos
pp_configurations = {
    "tendencial": {"nivel_roi_inicial": 40, "incremento_nivel_roi": 20, "primer_ajuste_sl": 25, "incremento_sl_post": 20},
    "moderada": {"nivel_roi_inicial": 33, "incremento_nivel_roi": 20, "primer_ajuste_sl": 22, "incremento_sl_post": 23},
    "conservadora": {"nivel_roi_inicial": 23, "incremento_nivel_roi": 30, "primer_ajuste_sl": 22, "incremento_sl_post": 23},
                                         #3= % - % - % - %             
                                         #2= 40%- +25% - +20% - +20%
                                         #1= 30% - % - % - %
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
                mensaje = f"🔒 Profit Protection: SL dinámico ajustado a {sl_dinamico:.2f}%. ROI Actual: {roi:.2f}%. PNL: {unrealized_pnl:.2f} USDT"
                print(mensaje)
                enviar_notificacion_telegram(mensaje, tipo="positivo")

            print(f"ROI: {roi:.2f}% | PNL: {unrealized_pnl:.2f} USDT | SL Dinámico: {sl_dinamico:.2f}%")

            # Evaluar cierre de posición
            if roi <= sl_dinamico:
                estado = "SL"
                resultado = roi
                cerrar_operacion(simbolo, cantidad, direccion, estado, resultado, unrealized_pnl)
                return estado
            elif roi >= tp_porcentaje:
                estado = "TP"
                resultado = nivel_roi
                cerrar_operacion(simbolo, cantidad, direccion, estado, resultado, unrealized_pnl)
                return estado

            time.sleep(0.07)
    except Exception as e:
        logging.error(f"Error en el monitoreo de ROI: {e}")
        print(f"Error en el monitoreo de ROI: {e}")


def cerrar_operacion(simbolo, cantidad, direccion, estado, resultado, pnl_final):
    try:
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
            fecha_iso=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        
        # Mensaje y envío a Telegram
        if estado == "SL" and pnl_final < 0:
            mensaje = f"🔴 SL alcanzado. PNL Final: {pnl_final:.2f} USDT - ROI: {resultado:.2f}% - Mercado: {simbolo}"
            enviar_notificacion_telegram(mensaje, tipo=1)
        else:
            mensaje = f"🎉Profit protegido alcanzado🎉               PNL: {pnl_final:.2f} USDT  -  ROI: {resultado:.2f}%"
            enviar_notificacion_telegram(mensaje, tipo="positivo")
        
        print(mensaje)
    except Exception as e:
        logging.error(f"Error al cerrar operación: {e}")
        print(f"[ERROR] Error al cerrar operación: {e}")




if __name__ == "__main__":
    simbolo = input("Ingresa el símbolo del mercado a monitorear (ej. BTCUSDT): ").upper()
    porcentaje_cuenta = float(input("Ingresa el porcentaje de tu cuenta para usar en cada operación (ej. 5 para 5%): "))
    apalancamiento = int(input("Ingresa el apalancamiento deseado: "))
    direccion = input("¿Deseas operar en LONG (l) o SHORT (s)?: ").strip().lower()
    tp_porcentaje = 8888
    sl_porcentaje = float(input("Ingresa el porcentaje de Stop Loss (ej. 50): "))
    pp_activado = input("¿Activar Profit Protection (PP)? (s/n): ").strip().lower() == "s"
    reiniciar_operaciones = input("¿Deseas reiniciar automáticamente después de cerrar una operación? (si/no): ").strip().lower() == "si"
    max_sl_consecutivos = 0

    if reiniciar_operaciones:
        max_sl_consecutivos = int(input("¿Cuántos cierres consecutivos en SL permitir antes de detener las operaciones?: "))

    # Inputs adicionales para margen descendente
    usar_margen_descendente = input("¿Usar margen descendente? (si/no): ").strip().lower() == "si"
    if usar_margen_descendente:
        decremento_margen = float(input("¿Cuánto porcentaje reducir por operación (ej. 25 para 25%)?: "))

    print("Selecciona la configuración de Profit Protection (PP):")
    print("1. Tendencial (mantiene más tiempo las operaciones abiertas)")
    print("2. Moderada (equilibrio entre cierre rápido y maximización de beneficios)")
    print("3. Conservadora (cierra operaciones rápidamente)")
    config_choice = input("Elige una opción (1/2/3): ").strip()
    config = pp_configurations["tendencial"] if config_choice == "1" else \
             pp_configurations["moderada"] if config_choice == "2" else \
             pp_configurations["conservadora"]

    sl_consecutivos = 0  # Contador de SL consecutivos

    while True:
        # Actualizar margen si el modo descendente está activo
        if usar_margen_descendente:
            print(f"[INFO] Margen actual antes de la operación: {porcentaje_cuenta:.2f}%")
            porcentaje_cuenta = max(porcentaje_cuenta - (porcentaje_cuenta * decremento_margen / 100), 1)
            print(f"[INFO] Nuevo margen ajustado para esta operación: {porcentaje_cuenta:.2f}%")

        # Calcular cantidad de USDT a usar
        balance_disponible = obtener_balance_disponible()
        cantidad_usdt = (porcentaje_cuenta / 100) * balance_disponible
        print(f"Usando {cantidad_usdt:.2f} USDT para esta operación (Balance: {balance_disponible:.2f} USDT)")

        # Ejecutar la orden inicial
        orden_inicial = crear_orden(simbolo, porcentaje_cuenta, apalancamiento, direccion)

        if orden_inicial:
            precio_entrada, cantidad = orden_inicial
            estado = monitorear_roi_con_pp(config, tp_porcentaje, pp_activado, simbolo, cantidad, apalancamiento, direccion)

            # Manejar cierre según el estado de la operación
            if estado == "SL":
                pnl_final = -1  # Asume un PNL negativo hasta verificar en cerrar_operacion
                if pnl_final < 0:  # Incrementa el contador si es SL negativo
                    sl_consecutivos += 1
                    print(f"[LOG] Cierres consecutivos en SL negativo: {sl_consecutivos}/{max_sl_consecutivos}")
                    if reiniciar_operaciones and sl_consecutivos >= max_sl_consecutivos:
                        print("Se alcanzó el límite de cierres consecutivos en SL negativo. Deteniendo operaciones.")
                        break
                else:
                    sl_consecutivos = 0  # Reinicia el contador si el SL no fue negativo

            if not reiniciar_operaciones:
                # Preguntar si desea reiniciar con los mismos parámetros
                continuar = input("¿Deseas reiniciar con los mismos parámetros? (s/n): ").strip().lower() == "s"
                if continuar:
                    direccion = input("Ingresa la nueva dirección para operar (l para LONG / s para SHORT): ").strip().lower()
                    continue
                else:
                    print("Operación finalizada. No se reiniciarán operaciones automáticamente.")
                    break
        else:
            print("No se pudo ejecutar la orden inicial. Finalizando.")
            break
