import os

def main():
    print("BOTARDOO DE LOS ATH")
    print("¿Quieres reinicio automático?")
    print("1: Sí")
    print("2: No")
    
    choice = input("Selecciona una opción (1/2): ").strip()
    
    if choice == "1":
        print("Ejecutando el archivo 'AutoOrdenAth.py'...")
        os.system("python AutoOrdenAth.py")
    elif choice == "2":
        print("Ejecutando el archivo 'ManualOrdenAth.py'...")
        os.system("python ManualOrdenAth.py")
    else:
        print("Opción no válida. Inténtalo de nuevo.")
        main()  # Vuelve a preguntar si la opción no es válida.

if __name__ == "__main__":
    main()
