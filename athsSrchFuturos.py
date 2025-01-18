import requests
from binance.client import Client
from binance.exceptions import BinanceAPIException

# Configuración de la API de Binance
client = Client(api_key='MoAcsgKcNJFW1oXGqnKHm9sgn4iIMXtiDkdohXyjhdwevXQMEl9zTVXrOKYEefIp', 
                api_secret='bBnH4g7LsLyN93cm38pWAsmTw8XNmV2HPXTpoCN4MmUZ66LxczHKpCt0H1FCQchW')

# Configuración del bot de Telegram
telegram_token = "7895510218:AAEyjFmp4iZOTwc1qsMxwziE_ATpL5GCDBc"
telegram_chat_id = "1861668101"

# Función para enviar un mensaje a Telegram
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    payload = {"chat_id": telegram_chat_id, "text": message}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error al enviar mensaje a Telegram: {e}")

# Función para obtener el ATH de un mercado de futuros
def get_ath(symbol):
    klines = client.futures_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1WEEK, limit=52)  # Últimas 52 semanas
    high_prices = [float(kline[2]) for kline in klines]
    return max(high_prices)

# Función para seleccionar los mercados cercanos al ATH dentro del rango especificado
def find_markets_near_ath(markets, ath_proximity_percentage):
    selected_markets = []
    for symbol in markets:
        try:
            ath = get_ath(symbol)
            ticker_info = client.futures_symbol_ticker(symbol=symbol)
            current_price = float(ticker_info.get('price', 0))
            if current_price == 0:
                continue  # Omitir si no hay precio
            
            proximity_percentage = ((ath - current_price) / ath) * 100
            if 0 <= proximity_percentage <= ath_proximity_percentage:
                selected_markets.append({
                    'symbol': symbol,
                    'current_price': round(current_price, 8),
                    'proximity_percentage': round(proximity_percentage, 2)
                })
        except BinanceAPIException:
            continue  # Omitir errores no importantes
    # Ordenar por proximidad al ATH
    selected_markets.sort(key=lambda x: x['proximity_percentage'])
    return selected_markets

# Obtener todos los mercados de futuros USDT, excluyendo BTC y USDC
def get_usdt_futures_markets():
    futures_info = client.futures_exchange_info()
    return [symbol['symbol'] for symbol in futures_info['symbols'] if symbol['quoteAsset'] == 'USDT' and "BTC" not in symbol['symbol'] and "USDC" not in symbol['symbol'] and "DGB" not in symbol['symbol'] and "ETH" not in symbol['symbol']]

# Formatear los resultados en una tabla
def print_markets_table(selected_markets):
    print("╔════════════════╦═══════════════════════╦══════════════════════╗")
    print("║    FSímbolo    ║  Precio Actual (USDT) ║ Proximidad al ATH (%)║")
    print("╠════════════════╬═══════════════════════╬══════════════════════╣")
   
    for market in selected_markets:
        print(f"║ {market['symbol']:<14} ║  {market['current_price']:<17}  ║ {market['proximity_percentage']:<18}  ║")
    
    print("╚════════════════╩═══════════════════════╩══════════════════════╝")
    print("🔍 Buscando mercados cercanos al ATH...\n")

# Proceso principal
def main():
    ath_proximity_percentage = float(input("Ingresa el porcentaje de proximidad al ATH (por ejemplo, 4.0 para 4%): "))
    
    while True:
        usdt_futures_markets = get_usdt_futures_markets()
        selected_markets = find_markets_near_ath(usdt_futures_markets, ath_proximity_percentage)
        
        if selected_markets:
            print_markets_table(selected_markets)

            # Enviar al Telegram solo el mercado más cercano al ATH
            nearest_market = selected_markets[0]
            message = (
                f"📈 Mercado más cercano al ATH:\n"
                f"📈 Símbolo: {nearest_market['symbol']}\n"
                f"🔹 Precio Actual: {nearest_market['current_price']} USDT\n"
                f"🔹 Proximidad al ATH: {nearest_market['proximity_percentage']}%"
            )
            send_telegram_message(message)
        else:
            print("❌ No se encontraron mercados cercanos al ATH en el rango especificado.\n")

# Ejecutar el código
if __name__ == "__main__":
    main()
