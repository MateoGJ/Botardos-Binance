from binance.client import Client
import pandas as pd

# Configura tu cliente de Binance
client = Client(api_key='MoAcsgKcNJFW1oXGqnKHm9sgn4iIMXtiDkdohXyjhdwevXQMEl9zTVXrOKYEefIp', 
                api_secret='bBnH4g7LsLyN93cm38pWAsmTw8XNmV2HPXTpoCN4MmUZ66LxczHKpCt0H1FCQchW')

# Descarga datos históricos
symbol = "HIVEUSDT"  # Cambia al símbolo que necesites
interval = Client.KLINE_INTERVAL_1MINUTE
klines = client.get_historical_klines(symbol, interval, "90 day ago UTC")

# Guarda los datos en un archivo CSV
columns = ["timestamp", "open", "high", "low", "close", "volume", "close_time", "quote_asset_volume", "number_of_trades", "taker_buy_base", "taker_buy_quote", "ignore"]
df = pd.DataFrame(klines, columns=columns)
df.to_csv("historical_data.csv", index=False)
