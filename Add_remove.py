import json



# Funktion til at indlæse eksisterende enheder fra devices_db.json
def load_devices():
    try:
        with open("devices_db.json", "r") as file:
            data = file.read().strip()
            return json.loads(data) if data else {}  # Returner en tom dictionary, hvis filen er tom
    except FileNotFoundError:
        return {}

# Funktion til at gemme enheder i devices_db.json
def save_devices(devices):
    with open("devices_db.json", "w") as file:
        json.dump(devices, file, indent=4)

# Funktion til at generere unikke navne baseret på producent og model
def generate_device_name(producent, model):
    return f"{producent} {model}".replace(" ", " ")

# Funktion til at tilføje en ny modem med kabelhastigheder
def add_modem():
    devices = load_devices()

    producent = input("Indtast producenten: ")
    model = input("Indtast modelnavnet: ")
    name = generate_device_name(producent, model)  # Genererer navn automatisk

    # Modemer har én ethernet-port og ingen Wi-Fi
    cable_download = int(input("Indtast kabel downloadhastighed (Mbps): "))
    cable_upload = int(input("Indtast kabel uploadhastighed (Mbps): "))

    devices[name] = {
        "type": "modem",
        "producent": producent,
        "model": model,
        "ethernet_ports": 1,
        "wifi": False,
        "speeds": {
            "cable_download": cable_download,
            "cable_upload": cable_upload
        }
    }

    save_devices(devices)
    print(f"Modem '{name}' tilføjet!")

# Funktion til at tilføje en ny router med kabel- og Wi-Fi-hastigheder
def add_router():
    devices = load_devices()

    producent = input("Indtast producenten: ")
    model = input("Indtast modelnavnet: ")
    name = generate_device_name(producent, model)  # Genererer navn automatisk
    ethernet_ports = int(input("Hvor mange ethernet-porte har routeren? "))
    has_24ghz = input("Har routeren 2.4 GHz? (ja/nej): ").lower() == "ja"
    has_5ghz = input("Har routeren 5 GHz? (ja/nej): ").lower() == "ja"
    has_6ghz = input("Har routeren 6 GHz? (ja/nej): ").lower() == "ja"

    # Lad brugeren indtaste hastigheder for kabel- og Wi-Fi-forbindelser
    cable_download = int(input("Indtast kabel downloadhastighed (Mbps): "))
    cable_upload = int(input("Indtast kabel uploadhastighed (Mbps): "))
    wifi_24ghz_download = int(input("Indtast 2.4 GHz Wi-Fi downloadhastighed (Mbps): ")) if has_24ghz else 0
    wifi_24ghz_upload = int(input("Indtast 2.4 GHz Wi-Fi uploadhastighed (Mbps): ")) if has_24ghz else 0
    wifi_5ghz_download = int(input("Indtast 5 GHz Wi-Fi downloadhastighed (Mbps): ")) if has_5ghz else 0
    wifi_5ghz_upload = int(input("Indtast 5 GHz Wi-Fi uploadhastighed (Mbps): ")) if has_5ghz else 0
    wifi_6ghz_download = int(input("Indtast 6 GHz Wi-Fi downloadhastighed (Mbps): ")) if has_6ghz else 0
    wifi_6ghz_upload = int(input("Indtast 6 GHz Wi-Fi uploadhastighed (Mbps): ")) if has_6ghz else 0

    devices[name] = {
        "type": "router",
        "producent": producent,
        "model": model,
        "ethernet_ports": ethernet_ports,
        "2.4ghz": has_24ghz,
        "5ghz": has_5ghz,
        "6ghz": has_6ghz,
        "speeds": {
            "cable_download": cable_download,
            "cable_upload": cable_upload,
            "wifi_24ghz_download": wifi_24ghz_download,
            "wifi_24ghz_upload": wifi_24ghz_upload,
            "wifi_5ghz_download": wifi_5ghz_download,
            "wifi_5ghz_upload": wifi_5ghz_upload,
            "wifi_6ghz_download": wifi_6ghz_download,
            "wifi_6ghz_upload": wifi_6ghz_upload,
        }
    }

    save_devices(devices)
    print(f"Router '{name}' tilføjet!")

# Funktion til at fjerne en enhed (modem eller router) fra devices_db.json
def remove_device():
    devices = load_devices()
    if not devices:
        print("Der er ingen enheder at fjerne.")
        return

    print("\nTilgængelige enheder:")
    for i, device_name in enumerate(devices.keys(), start=1):
        print(f"{i}. {device_name}")

    choice = int(input("Vælg en enhed, der skal fjernes: ")) - 1
    device_name = list(devices.keys())[choice]

    del devices[device_name]
    save_devices(devices)
    print(f"Enhed '{device_name}' er blevet fjernet!")

# Hovedmenu til at tilføje eller fjerne enheder
def main_menu():
    while True:
        print("\nHovedmenu")
        print("1. Tilføj enhed")
        print("2. Fjern enhed")
        print("3. Vis enheder")
        print("4. Afslut")
        
        try:
            choice = input("Vælg en mulighed (1-4): ")
            print(f"Du valgte: {choice}")  # Debug-meddelelse

            if choice == "1":
                device_type = input("Vil du tilføje et modem eller en router? (modem/router): ").lower()
                if device_type == "modem":
                    add_modem()
                elif device_type == "router":
                    add_router()
                else:
                    print("Ugyldigt valg. Vælg enten 'modem' eller 'router'.")
            elif choice == "2":
                remove_device()
            elif choice == "3":
                show_devices()
            elif choice == "4":
                print("Afslutter programmet.")
                break
            else:
                print("Ugyldigt valg. Prøv igen.")
        except Exception as e:
            print(f"En fejl opstod: {e}")

# Tilføj en funktion til at vise eksisterende enheder
def show_devices():
    devices = load_devices()
    if devices:
        print("\nRegistrerede enheder:")
        for name, info in devices.items():
            print(f"{name} ({info['type']}) - Producent: {info['producent']}, Model: {info['model']}")
    else:
        print("Ingen enheder fundet.")

if __name__ == "__main__":
    main_menu()