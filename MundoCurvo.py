import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import plotly.graph_objects as go

# ----- CÍRCULO 2D -----
def plot_circle(radius):
    theta = np.linspace(0, 2 * np.pi, 100)
    x = radius * np.cos(theta)
    y = radius * np.sin(theta)

    plt.figure(figsize=(6, 6))
    plt.plot(x, y, label=f"Círculo (radio={radius})")
    plt.scatter([0], [0], color="red", label="Centro")
    plt.axis('equal')
    plt.title("Representación de un círculo en 2D")
    plt.legend()
    plt.show()

# ----- ESFERA 3D -----
def plot_sphere(radius):
    u = np.linspace(0, 2 * np.pi, 100)
    v = np.linspace(0, np.pi, 100)
    x = radius * np.outer(np.cos(u), np.sin(v))
    y = radius * np.outer(np.sin(u), np.sin(v))
    z = radius * np.outer(np.ones(np.size(u)), np.cos(v))

    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, projection='3d')
    ax.plot_surface(x, y, z, color='cyan', alpha=0.6, edgecolor='gray')
    ax.set_title("Representación de una esfera en 3D")
    plt.show()

# ----- ESFERA 3D INTERACTIVA (PLOTLY) -----
def interactive_sphere(radius):
    u = np.linspace(0, 2 * np.pi, 100)
    v = np.linspace(0, np.pi, 100)
    x = radius * np.outer(np.cos(u), np.sin(v))
    y = radius * np.outer(np.sin(u), np.sin(v))
    z = radius * np.outer(np.ones(np.size(u)), np.cos(v))

    fig = go.Figure(data=[go.Surface(z=z, x=x, y=y, colorscale='Viridis')])
    fig.update_layout(title=f"Esfera interactiva (radio={radius})", scene=dict(
        xaxis_title='X',
        yaxis_title='Y',
        zaxis_title='Z'))
    fig.show()

# ----- MAIN -----
if __name__ == "__main__":
    print("Visualización de dimensiones curvas")
    print("1. Círculo 2D")
    print("2. Esfera 3D (estática)")
    print("3. Esfera 3D (interactiva)")
    choice = int(input("Elige una opción (1/2/3): "))

    radius = float(input("Ingresa el radio: "))

    if choice == 1:
        plot_circle(radius)
    elif choice == 2:
        plot_sphere(radius)
    elif choice == 3:
        interactive_sphere(radius)
    else:
        print("Opción no válida.")
