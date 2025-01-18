import pandas as pd
import numpy as np
from itertools import product

# Define parámetros a evaluar
percent_account = [1, 2, 5, 10]
leverages = [10, 25, 50, 75]
pp_strategies = {
    "tendencial": {"nivel_roi_inicial": 60, "incremento_nivel_roi": 75, "primer_ajuste_sl": 31, "incremento_sl_post": 69},
    "moderada": {"nivel_roi_inicial": 40, "incremento_nivel_roi": 40, "primer_ajuste_sl": 31, "incremento_sl_post": 31},
    "conservadora": {"nivel_roi_inicial": 40, "incremento_nivel_roi": 20, "primer_ajuste_sl": 25, "incremento_sl_post": 20}
}

# Generar combinaciones de parámetros
combinations = list(product(percent_account, leverages, pp_strategies.keys()))

# Simulación
def simulate_trading(data, percent_account, leverage, strategy):
    pnl = 0
    for _, row in data.iterrows():
        # Simulación simplificada
        entry_price = row['open']
        exit_price = row['close']
        pnl += (exit_price - entry_price) * leverage * (percent_account / 100)
    return pnl

# Leer datos históricos (ejemplo)
data = pd.read_csv("historical_data.csv")  # Descargar con la API de Binance

# Evaluar cada combinación
results = []
for percent, leverage, strategy in combinations:
    pnl = simulate_trading(data, percent, leverage, pp_strategies[strategy])
    results.append({
        "percent_account": percent,
        "leverage": leverage,
        "strategy": strategy,
        "pnl": pnl
    })

# Convertir resultados a DataFrame
results_df = pd.DataFrame(results)

# Visualizar mejores estrategias
print(results_df.sort_values(by="pnl", ascending=False))
