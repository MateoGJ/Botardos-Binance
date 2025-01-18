import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# ----- SIMULACIÓN DE ESPACIO CURVO CERCA DE UN AGUJERO NEGRO -----
def schwarzschild_metric(mass, grid_size):
    """
    Calcula la curvatura del espacio-tiempo usando la métrica de Schwarzschild.

    Parámetros:
    - mass: Masa del agujero negro (en unidades solares).
    - grid_size: Tamaño de la cuadrícula (para la simulación).

    Retorna:
    - x, y, z: Coordenadas espaciales en 3D.
    - curvature: Valores de curvatura en cada punto.
    """
    # Constantes
    G = 6.67430e-11  # Constante gravitacional
    c = 3.0e8        # Velocidad de la luz
    rs = 2 * G * mass / c**2  # Radio de Schwarzschild

    # Crear una cuadrícula esférica
    r = np.linspace(rs, rs * 5, grid_size)
    theta = np.linspace(0, np.pi, grid_size)
    phi = np.linspace(0, 2 * np.pi, grid_size)
    r, theta, phi = np.meshgrid(r, theta, phi)

    # Coordenadas esféricas a cartesianas
    x = r * np.sin(theta) * np.cos(phi)
    y = r * np.sin(theta) * np.sin(phi)
    z = r * np.cos(theta)

    # Curvatura basada en la métrica
    curvature = 1 - (rs / r)

    return x, y, z, curvature

# ----- VISUALIZACIÓN -----
def plot_schwarzschild_space(x, y, z, curvature):
    """Genera una visualización de la curvatura del espacio-tiempo."""
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection='3d')

    # Colorear según la curvatura
    img = ax.scatter(x, y, z, c=curvature, cmap='viridis', marker='o')
    fig.colorbar(img, ax=ax, label="Curvatura")

    ax.set_title("Espacio curvado alrededor de un agujero negro")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")

    plt.show()

# ----- MAIN -----
if __name__ == "__main__":
    print("Simulación del espacio curvado cerca de un agujero negro")
    mass = float(input("Ingresa la masa del agujero negro (en masas solares): "))
    grid_size = int(input("Tamaño de la cuadrícula para la simulación (sugerido: 50): "))

    x, y, z, curvature = schwarzschild_metric(mass, grid_size)
    plot_schwarzschild_space(x, y, z, curvature)
