import json
import time
import speedtest as spd
import requests
import paramiko
import wmi
import os
import configparser
from pywifi import PyWiFi, const, Profile
import argparse


stop_flag = False




def load_config(file_path="config.ini"):
    config = configparser.ConfigParser()
    config.read(file_path)

    network_settings = config["NetworkSettings"]
    ip_address = network_settings.get("ip_address")
    subnet_mask = network_settings.get("subnet_mask")
    gateway = network_settings.get("gateway")
    dns_servers = network_settings.get("dns_servers").split(",")

    ssh_settings = config["SSH"]
    hostname = ssh_settings.get("hostname")
    username = ssh_settings.get("username")
    password = ssh_settings.get("password")
    switchname = ssh_settings.get("switchname")

    wifi_settings = config["WifiSettings"]
    wifi_password = wifi_settings.get("wifi_password")

    internet_config = config["InternetCheck"]
    internet_timeout = int(internet_config.get("timeout"))

    router_settings = config["WifiRouterSettings"]
    number_of_routers = int(router_settings.get("number_of_routers"))
    maximum_attempts = int(router_settings.get("maximum_attempts"))

    return ip_address, subnet_mask, gateway, dns_servers, hostname, username, password, wifi_password, number_of_routers, maximum_attempts, internet_timeout, switchname


def update_number_of_routers(num_routers):
    config = configparser.ConfigParser()
    config.read('config.ini')

    if 'WifiRouterSettings' in config:
        config['WifiRouterSettings']['number_of_routers'] = str(num_routers)
        with open('config.ini', 'w') as configfile:
            config.write(configfile)




def load_devices(file_path="devices_db.json"):
    try:
        with open(file_path, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"{file_path} blev ikke fundet.")
        return {}


def check_internet(timeout):
    print("[DEBUG] Tjekker internetforbindelse...")
    url = "http://www.google.com"
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print("[DEBUG] Internetforbindelse OK.")
                return True
        except requests.RequestException:
            pass
        time.sleep(5)
    print("[DEBUG] Ingen internetforbindelse efter 1 minut.")
    return False

def enable_wifi():
    print("[DEBUG] Søger efter Wi-Fi adapter for at aktivere den...")
    try:
        # Først kontrollér om Wi-Fi allerede er aktiveret
        result = subprocess.run("netsh interface show interface", capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            interfaces = result.stdout.splitlines()
            wifi_interface = None
            for line in interfaces:
                if 'Wi-Fi' in line or 'Wireless' in line:
                    wifi_interface = line.split()[-1]
                    if "Enabled" in line:  # Tjek om det allerede er aktiveret
                        print(f"[DEBUG] Wi-Fi adapter '{wifi_interface}' er allerede aktiveret.")
                        return  # Ingen grund til at aktivere igen
                    break

            if wifi_interface:
                print(f"[DEBUG] Aktiverer Wi-Fi adapter: {wifi_interface}")
                enable_result = subprocess.run(f"netsh interface set interface \"{wifi_interface}\" admin=enable", capture_output=True, text=True, shell=True)
                if enable_result.returncode == 0:
                    print(f"[DEBUG] Wi-Fi adapteren '{wifi_interface}' er nu aktiveret.")
                else:
                    print(f"[ERROR] Fejl ved aktivering af Wi-Fi: {enable_result.stderr}")
            else:
                print("[DEBUG] Wi-Fi adapter ikke fundet.")
        else:
            print(f"[ERROR] Fejl ved visning af netværksinterface: {result.stderr}")
    except Exception as e:
        print(f"[ERROR] Fejl ved forsøg på at aktivere Wi-Fi: {e}")


def disable_wifi():
    print("[DEBUG] Deaktiverer Wi-Fi adapter...")
    try:
        result = subprocess.run("netsh interface set interface \"Wi-Fi\" admin=disable", capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            print("[DEBUG] Wi-Fi adapter er deaktiveret.")
        else:
            print(f"[ERROR] Fejl ved deaktivering af Wi-Fi: {result.stderr}")
    except Exception as e:
        print(f"[ERROR] Fejl ved deaktivering af Wi-Fi: {e}")

def connect_wifi(ssid, password):
    print(f"[DEBUG] Forsøger at oprette forbindelse til Wi-Fi: {ssid}")
    
    # Forsøg at aktivere Wi-Fi-adapteren først
    enable_wifi()

    wifi = PyWiFi()
    interfaces = wifi.interfaces()

    if len(interfaces) == 0:
        print("[DEBUG] Ingen Wi-Fi-interface fundet. Sørg for, at din Wi-Fi-adapter er aktiv.")
        return False

    iface = interfaces[0]
    iface.disconnect()  # Afbryd fra ethvert eksisterende netværk
    time.sleep(1)  # Vent lidt

    profile = Profile()
    profile.ssid = ssid
    profile.auth = const.AUTH_ALG_OPEN
    profile.akm.append(const.AKM_TYPE_WPA2PSK)
    profile.cipher = const.CIPHER_TYPE_CCMP
    profile.key = password

    iface.remove_all_network_profiles()
    tmp_profile = iface.add_network_profile(profile)

    iface.connect(tmp_profile)  # Forsøg at forbinde
    for i in range(30):  # Giv det 30 sekunder
        if iface.status() == const.IFACE_CONNECTED:
            print(f"[DEBUG] Forbundet til Wi-Fi: {ssid}")
            return True
        time.sleep(1)

    print(f"[DEBUG] Kunne ikke oprette forbindelse til Wi-Fi: {ssid}")
    return False


def activate_wifi_if_disabled():
    if not is_wifi_enabled():
        print("[DEBUG] Wi-Fi er ikke aktiveret, forsøger at aktivere...")
        enable_wifi()
        time.sleep(5)  # Giv det lidt tid til at aktivere
    else:
        print("[DEBUG] Wi-Fi adapteren er allerede aktiveret.")


def test_wifi_with_retries(band, ssid, wifi_password, expected_download_speed, expected_upload_speed, maximum_attempts):
    enable_wifi()
    print(f"[DEBUG] Tester Wi-Fi: {ssid} ({band.upper()})")
    success = False
    attempts = 0

    while attempts < maximum_attempts and not success:
        print(f"[DEBUG] Forsøg {attempts + 1} af {maximum_attempts} for {band.upper()} Wi-Fi...")
        if connect_wifi(ssid, wifi_password):
            if check_internet(60):  # 1 minut timeout for internetforbindelse
                download_speed, upload_speed = speedtest()
                print(f"[DEBUG] {band.upper()} Download: {download_speed} Mbps, Upload: {upload_speed} Mbps")

                if download_speed >= expected_download_speed and upload_speed >= expected_upload_speed:
                    print(f"[DEBUG] {band.upper()} Wi-Fi hastigheder er acceptable.")
                    success = True
                else:
                    print(f"[DEBUG] {band.upper()} Wi-Fi hastigheder er ikke acceptable. Forsøger igen...")
            else:
                print(f"[DEBUG] {band.upper()} Wi-Fi internetforbindelse fejlede. Forsøger igen...")
        else:
            print(f"[DEBUG] Kunne ikke forbinde til {band.upper()} Wi-Fi. Forsøger igen...")

        attempts += 1
        time.sleep(5)

    if not success:
        print(f"[DEBUG] Opnåede ikke acceptable hastigheder efter {maximum_attempts} forsøg for {band.upper()} Wi-Fi.")

def speedtest():
    """
    Udfører en hastighedstest via speedtest-cli og returnerer download- og uploadhastigheder med en nedtælling.
    """
  print("[DEBUG] Udfører hastighedstest via speedtest-modul...")
    try:
        st = spd.Speedtest()
        st.get_best_server()
        download = st.download() / 1_000_000
        upload = st.upload() / 1_000_000
        print(f"[DEBUG] Download: {download:.2f} Mbps, Upload: {upload:.2f} Mbps")
        return download, upload
    except Exception as e:
        print(f"[ERROR] Speedtest fejlede: {e}")
        return 0, 0


def save_to_json(model_name, device_results, filename="test_results.json"):
    try:
        # Læs eksisterende data fra JSON-filen
        with open(filename, "r") as file:
            current_data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        current_data = []

    # Tjek om entry for den aktuelle model og router allerede findes
    existing_entry = None
    for entry in current_data:
        if model_name in entry and entry[model_name]["router_number"] == device_results["router_number"]:
            existing_entry = entry
            break

    if existing_entry:
        # Opdater eksisterende entry med nye resultater
        existing_entry[model_name].update(device_results)
    else:
        # Tilføj en ny entry for denne model og router
        current_data.append({model_name: device_results})

    # Gem resultaterne tilbage til JSON-filen
    with open(filename, "w") as file:
        json.dump(current_data, file, indent=4)
    print(f"[DEBUG] Resultater gemt i {filename}.")




def clear_results_file(filename="test_results.json"):
    """
    Rydder JSON-filen ved at skrive en tom liste.
    """
    with open(filename, "w") as file:
        json.dump([], file, indent=4)
    print(f"[DEBUG] JSON-filen '{filename}' er blevet ryddet.")



def shutdown_ports_on_switch(hostname, username, password, switchname):
    try:
        set_static_ip_on_ethernet(ip_address, subnet_mask, gateway, dns_servers)
        print(f"[DEBUG] SSH'er ind i switchen ({hostname}) for at lukke portene 2-49...")
        ssh_conn = ssh_to_switch(hostname, username, password, 30, {switchname: (2, 49)}, 3, switchname)

        # Brug interface range-kommandoen til at lukke alle porte på én gang
        send_command(ssh_conn, 'conf t')
        send_command(ssh_conn, 'interface range GigabitEthernet1/0/2-49')
        send_command(ssh_conn, 'shutdown')
        print("[DEBUG] Portene 2-49 er lukket.")

        send_command(ssh_conn, 'exit')
        ssh_conn.close()
        print("[DEBUG] SSH-forbindelsen til switchen er lukket.")
    except Exception as e:
        print(f"[ERROR] Fejl ved lukning af porte: {e}")
        
    finally:
        set_dhcp()


def send_command(ssh_conn, command):
    ssh_conn.send(command + '\n')
    time.sleep(1)  # Vent for at sikre, at kommandoen bliver eksekveret
    output = ssh_conn.recv(65535).decode('utf-8')  # Modtag output fra kommandoen
    print(f"[DEBUG] Output for '{command}':\n{output}")
    return output


# Funktion der oversætter switchporte til routerporte baseret på routernummer
def translate_switch_to_router_port(switch_port, router_number):
    """
    Oversætter switchport til routerport baseret på routernummeret.
    """
    base_port = 2 + (router_number - 1) * 6  # Beregn den første switchport for denne router
    router_port = switch_port - base_port + 1  # Beregn routerport
    return router_port




def calculate_ports_for_devices(devices, total_devices):
    base_ports = {
        1: 2,   # Enhed 1 starter fra port 2
        2: 8,   # Enhed 2 starter fra port 8
        3: 14,  # Enhed 3 starter fra port 14
        4: 20,  # Enhed 4 starter fra port 20
        5: 26,  # Enhed 5 starter fra port 26
        6: 32,  # Enhed 6 starter fra port 32
        7: 38,  # Enhed 7 starter fra port 38
        8: 44   # Enhed 8 starter fra port 44
    }

    port_ranges = {}
    
    # Loop gennem enhederne fra JSON-fil og beregn portintervaller
    for device_index, device_name in enumerate(devices.keys(), start=1):
        if device_index > total_devices:
            break  # Begræns til det angivne antal enheder
        
        device_details = devices[device_name]  # Hent detaljer fra JSON
        number_of_ports = device_details.get("ethernet_ports", 4)  # Default til 4 porte for en router
        
        # Find startporten fra base_ports for den aktuelle enhed
        start_port = base_ports.get(device_index, 2)  # Default til startport 2, hvis ikke fundet
        end_port = start_port + number_of_ports - 1  # Beregn slutport

        # Tilføj portinterval for denne enhed
        port_ranges[device_name] = (start_port, end_port)

    return port_ranges


def get_device_speeds(devices, device_name):
    if device_name in devices:
        return devices[device_name]["speeds"]
    else:
        print(f"[DEBUG] Enheden '{device_name}' blev ikke fundet i devices_db.json.")
        return None

def shutdown_ports_on_switch(hostname, username, password, switchname):
    try:
        print(f"[DEBUG] SSH'er ind i switchen ({hostname}) for at lukke portene 2-49...")
        ssh_conn = ssh_to_switch(hostname, username, password, 30, {switchname: (2, 49)}, 3, switchname)

        # Brug interface range-kommandoen til at lukke alle porte på én gang
        send_command(ssh_conn, 'conf t')
        send_command(ssh_conn, 'interface range GigabitEthernet1/0/2-49')
        send_command(ssh_conn, 'shutdown')
        print("[DEBUG] Portene 2-49 er lukket.")

        send_command(ssh_conn, 'exit')
        ssh_conn.close()
        print("[DEBUG] SSH-forbindelsen til switchen er lukket.")
    except Exception as e:
        print(f"[ERROR] Fejl ved lukning af porte: {e}")

# Skift til DHCP for Ethernet-forbindelse
def set_dhcp():
    print("[DEBUG] Skifter til DHCP...")
    c = wmi.WMI()
    adapters = c.Win32_NetworkAdapterConfiguration(IPEnabled=True)

    ethernet_adapter = None
    for adapter in adapters:
        if "Ethernet" in adapter.Description:
            ethernet_adapter = adapter
            break
    
    if ethernet_adapter:
        ethernet_adapter.EnableDHCP()
        ethernet_adapter.SetDNSServerSearchOrder()
        print("[DEBUG] DHCP aktiveret på Ethernet.")
    else:
        print("[DEBUG] Ingen Ethernet-interface fundet.")


def initialize_test_results(model_name, num_devices, wifi_bands, ethernet_ports):
    """
    Initialiser JSON-filen med status 'Afventer test' for alle tests (Wi-Fi og Ethernet).
    """
    # Start med en tom liste
    test_data = []

    for router_number in range(1, num_devices + 1):
        router_entry = {
            model_name: {
                "router_number": router_number,
                "wifi_results": {},
                "ethernet_results": {}
            }
        }

        # Tilføj "Afventer test" for Wi-Fi-bånd
        for band, _, _, _ in wifi_bands:
            router_entry[model_name]["wifi_results"][band] = "Afventer test"

        # Tilføj "Afventer test" for Ethernet-porte
        for port in range(1, ethernet_ports + 1):
            router_entry[model_name]["ethernet_results"][str(port)] = "Afventer test"

        test_data.append(router_entry)

    # Overskriv JSON-filen med den initialiserede data
    with open("test_results.json", "w") as file:
        json.dump(test_data, file, indent=4)
    print("[DEBUG] Testresultater initialiseret i test_results.json.")




def ssh_to_switch(hostname, username, password, internet_timeout, port_ranges, maximum_attempts, switchname):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    retries = 3  # Antal forsøg på at oprette forbindelse
    retry_delay = 5  # Vent 5 sekunder mellem forsøg
    
    ssh_conn = None
    for attempt in range(retries):
        print(f"[DEBUG] Forsøger at oprette SSH-forbindelse til {hostname}, forsøg {attempt + 1} af {retries}...")
        try:
            client.connect(hostname, username=username, password=password, look_for_keys=False, allow_agent=False)
            print("[DEBUG] Forbundet til switchen!")
            ssh_conn = client.invoke_shell()
            time.sleep(1)  # Vent lidt for at sikre, at shell'en er klar
            return ssh_conn  # Returner forbindelsen
        except paramiko.ssh_exception.NoValidConnectionsError as e:
            print(f"[DEBUG] Kunne ikke forbinde til switchen: {e}. Forsøger igen om {retry_delay} sekunder.")
        except Exception as e:
            print(f"[DEBUG] Fejl ved forbindelse til switchen: {e}. Forsøger igen om {retry_delay} sekunder.")
        
        time.sleep(retry_delay)  # Vent før næste forsøg
    
    print("[ERROR] Kunne ikke oprette SSH-forbindelse efter flere forsøg.")
    return None  # Returner None, hvis forbindelsen ikke kunne oprettes

def run_wifi_test_and_save(device_results, model_name, wifi_bands, wifi_password, maximum_attempts):
    for band, ssid, expected_download, expected_upload in wifi_bands:
        if device_results.get("wifi_results") is None:
            device_results["wifi_results"] = {}

        print(f"[DEBUG] Tester Wi-Fi for {band} med SSID {ssid}")
        success = False
        attempts = 0
        download_speed = 0
        upload_speed = 0

        while attempts < maximum_attempts and not success:
            print(f"[DEBUG] Forsøg {attempts + 1} af {maximum_attempts} for {band.upper()} Wi-Fi...")

            # Forsøg at forbinde til Wi-Fi
            if connect_wifi(ssid, wifi_password):
                print(f"[DEBUG] Forbundet til {band.upper()} Wi-Fi")

                # Internettjek med max forsøg fra konfigurationsfilen
                internet_success = False
                for _ in range(maximum_attempts):
                    if check_internet(60):  # 1 minut timeout for internetforbindelse
                        print(f"[DEBUG] Internetforbindelse OK på {band.upper()} Wi-Fi.")
                        internet_success = True
                        break
                    else:
                        print(f"[DEBUG] Ingen internetforbindelse for {band.upper()}. Forsøger igen...")

                if not internet_success:
                    attempts += 1  # Opdater attempts, da internettjek fejlede
                    device_results["wifi_results"][band] = "Ingen internetforbindelse"
                    continue  # Fortsæt til næste forsøg

                # Hastighedstest med max forsøg fra konfigurationsfilen
                speedtest_success = False
                for _ in range(maximum_attempts):
                    download_speed, upload_speed = speedtest()
                    print(f"[DEBUG] {band.upper()} Download: {download_speed} Mbps, Upload: {upload_speed} Mbps")

                    if download_speed >= expected_download and upload_speed >= expected_upload:
                        print(f"[DEBUG] {band.upper()} Wi-Fi hastigheder er acceptable.")
                        device_results["wifi_results"][band] = "Godkendt"
                        success = True
                        speedtest_success = True
                        break  # Hvis hastigheden er OK, stopper vi her
                    else:
                        print(f"[DEBUG] {band.upper()} hastigheder ikke acceptable. Forsøger igen...")
                        attempts += 1  # Opdater attempts, da hastighedstesten fejlede

            else:
                print(f"[DEBUG] Mislykket forbindelse til {band.upper()}")
                device_results["wifi_results"][band] = "Mislykket forbindelse"
                attempts += 1  # Opdater attempts, da Wi-Fi-forbindelse fejlede

            time.sleep(5)  # Vent lidt før næste forsøg

        # Hvis ingen succes efter alle forsøg
        if not success:
            print(f"[DEBUG] Opnåede ikke acceptable hastigheder efter {maximum_attempts} forsøg for {band.upper()} Wi-Fi.")
            device_results["wifi_results"][band] = f"Fejlet ({download_speed}/{upload_speed})"

        # Gem resultaterne løbende efter hver Wi-Fi-test
        save_to_json(model_name, device_results)

# Funktion til at finde det korrekte ethernet-interface og sætte statisk IP
def set_static_ip_on_ethernet(ip_address, subnet_mask, gateway, dns_servers):
    print(f"[DEBUG] Søger efter Ethernet-interface for at sætte statisk IP...")
    c = wmi.WMI()
    adapters = c.Win32_NetworkAdapterConfiguration(IPEnabled=True)

    ethernet_adapter = None
    for adapter in adapters:
        if "Ethernet" in adapter.Description:
            ethernet_adapter = adapter
            break
    
    if ethernet_adapter:
        print(f"[DEBUG] Sætter statisk IP på Ethernet: {ethernet_adapter.Description}")
        ethernet_adapter.EnableStatic(IPAddress=[ip_address], SubnetMask=[subnet_mask])
        ethernet_adapter.SetGateways(DefaultIPGateway=[gateway])
        ethernet_adapter.SetDNSServerSearchOrder(DNSServerSearchOrder=dns_servers)
        print(f"[DEBUG] Statisk IP sat til {ip_address}.")
    else:
        print("[DEBUG] Ingen Ethernet-interface fundet.")


def run_test(model_name, num_devices, recipient_email):
    global test_running, stop_flag

    print(f"[DEBUG] Kører tests for {model_name} med {num_devices} enheder og sender resultater til {recipient_email}")
    test_running = True
    print("[DEBUG] test_running sat til True.")

    try:
        clear_results_file("test_results.json")
        print("[DEBUG] JSON-filen 'test_results.json' er blevet ryddet.")

        ip_address, subnet_mask, gateway, dns_servers, hostname, username, password, wifi_password, number_of_routers, maximum_attempts, internet_timeout, switchname = load_config()

        wifi_settings = configparser.ConfigParser()
        wifi_settings.read("config.ini")
        wifi_prefix = wifi_settings["WifiSettings"].get("wifi_prefix")

        devices = load_devices()
        if model_name not in devices:
            print(f"[ERROR] Ingen {model_name} enheder fundet.")
            test_running = False
            return

        device_info = devices[model_name]

        # Loop gennem hver router
        for router_number in range(1, num_devices + 1):
            if stop_flag:
                print("[DEBUG] Testen blev stoppet af brugeren.")
                test_running = False
                break

            print(f"[INFO] Tester enhed {router_number}...")

            # Initialiser resultater for denne router i JSON
            save_to_json(model_name, {
                "router_number": router_number,
                "status": "Kører",
                "wifi_results": {},
                "ethernet_results": {}
            })
            print(f"[DEBUG] Initialiserede resultater for router {router_number} som 'Kører'.")

            device_results = {"router_number": router_number, "wifi_results": {}, "ethernet_results": {}}

            # Antag, at du allerede har hentet wifi_prefix fra din config:
            # wifi_settings = configparser.ConfigParser()
            # wifi_settings.read("config.ini")
            # wifi_prefix = wifi_settings["WifiSettings"].get("wifi_prefix")

            for band, ssid, exp_dl, exp_ul in [
                ("2.4ghz", f"{wifi_prefix}{router_number}", device_info["speeds"].get("wifi_24ghz_download"), device_info["speeds"].get("wifi_24ghz_upload")),
                ("5ghz", f"{wifi_prefix}{router_number}-5", device_info["speeds"].get("wifi_5ghz_download"), device_info["speeds"].get("wifi_5ghz_upload")),
                ("6ghz", f"{wifi_prefix}{router_number}-6", device_info["speeds"].get("wifi_6ghz_download"), device_info["speeds"].get("wifi_6ghz_upload"))
            ]:
                # Hvis båndet ikke er aktivt i device_info, spring over
                if not device_info.get(band):
                    print(f"[DEBUG] {band} er ikke aktiv – springer over.")
                    continue

                attempts = 0
                download_speed = 0
                upload_speed = 0
                success = False

                while attempts < maximum_attempts and not success:
                    print(f"[DEBUG] Forsøg {attempts + 1} af {maximum_attempts} for {band.upper()} Wi-Fi...")
                    if connect_wifi(ssid, wifi_password):
                        if check_internet(60):
                            download_speed, upload_speed = speedtest()
                            print(f"[DEBUG] {band.upper()} Download: {download_speed} Mbps, Upload: {upload_speed} Mbps")
                            if download_speed >= exp_dl and upload_speed >= exp_ul:
                                device_results["wifi_results"][band] = "Godkendt"
                                success = True
                            else:
                                print(f"[DEBUG] {band.upper()} Wi-Fi hastigheder ikke acceptable. Forsøger igen...")
                                attempts += 1
                        else:
                            print(f"[DEBUG] {band.upper()} Wi-Fi internetforbindelse fejlede. Forsøger igen...")
                            attempts += 1
                    else:
                        print(f"[DEBUG] Mislykket forbindelse til {band.upper()} Wi-Fi. Forsøger igen...")
                        attempts += 1

                    time.sleep(5)

                if attempts == maximum_attempts:
                    if download_speed == 0 and upload_speed == 0:
                        device_results["wifi_results"][band] = "Fejlet (kunne ikke forbinde)"
                    else:
                        device_results["wifi_results"][band] = f"Fejlet ({download_speed}/{upload_speed})"
                    save_to_json(model_name, device_results)


            # Deaktiver Wi-Fi før Ethernet-test
            disable_wifi()
            print("[DEBUG] Wi-Fi deaktiveret.")

            # Kald Ethernet-testfunktionen
            number_of_ports = device_info.get("ethernet_ports", 1)
            start_port = 2 + (router_number - 1) * 6
            end_port = start_port + number_of_ports - 1
            run_ethernet_test_and_save(
                device_results, model_name, start_port, end_port,
                hostname, username, password, internet_timeout,
                maximum_attempts, switchname, router_number,
                ip_address, subnet_mask, gateway, dns_servers
            )

            # Marker testen som afsluttet for denne router
            save_to_json(model_name, {"router_number": router_number, "status": "Afsluttet"})
            print(f"[INFO] Test for enhed {router_number} afsluttet.")

        enable_wifi()
        print("[DEBUG] Wi-Fi genaktiveret efter tests.")

    except Exception as e:
        print(f"[ERROR] En fejl opstod under testen: {e}")
    finally:
        test_running = False
        print("[DEBUG] test_running sat til False.")

    print("[INFO] Alle tests afsluttet. Sender e-mail...")
    send_email_using_script(recipient_email)
    print(f"[INFO] Test afsluttet og e-mail sendt til {recipient_email}")



def send_email_using_script(recipient_email):
    """
    Kør E_mail.py som et separat script med e-mailen som argument.
    """
    try:
        print(f"[DEBUG] Kører E_mail.py for at sende e-mail til {recipient_email}")
        subprocess.run(["python", "E_mail.py", recipient_email], check=True)
        print("[INFO] E-mail sendt succesfuldt.")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Fejl ved kørsel af E_mail.py: {e}")


        
        
def run_ethernet_test_and_save(device_results, model_name, start_port, end_port, hostname, username, password, internet_timeout, maximum_attempts, switchname, router_number, ip_address, subnet_mask, gateway, dns_servers):
    print(f"[DEBUG] Starter run_ethernet_test_and_save for {model_name} på {hostname} med startport {start_port} til endport {end_port}")

    # Sæt statisk IP før vi starter SSH-forbindelsen
    set_static_ip_on_ethernet(ip_address, subnet_mask, gateway, dns_servers)

    for switch_port in range(start_port, end_port + 1):
        router_port = translate_switch_to_router_port(switch_port, router_number)
        print(f"[DEBUG] Tester switch port {switch_port}, router port {router_port} via SSH")

        # Åbn SSH-forbindelse
        ssh_conn = ssh_to_switch(hostname, username, password, internet_timeout, {}, maximum_attempts, switchname)
        if ssh_conn is None:
            print("[ERROR] Kunne ikke oprette SSH-forbindelse til switchen.")
            return

        try:
            # Åbn porten
            send_command(ssh_conn, 'configure terminal')
            send_command(ssh_conn, f'interface GigabitEthernet1/0/{switch_port}')
            send_command(ssh_conn, 'no shutdown')
            set_dhcp()

            # Udfør internet- og hastighedstest
            for attempt in range(maximum_attempts):
                if not check_internet(internet_timeout):
                    print(f"[DEBUG] Ingen internetforbindelse på router port {router_port} under forsøg {attempt + 1}")
                    device_results["ethernet_results"][str(router_port)] = "Offline"
                    save_to_json(model_name, device_results)
                    continue

                download_speed, upload_speed = speedtest()
                print(f"[DEBUG] Router port {router_port}: Download: {download_speed} Mbps, Upload: {upload_speed} Mbps")

                speeds = get_device_speeds(load_devices(), model_name)
                if download_speed >= speeds.get("cable_download", 0) and upload_speed >= speeds.get("cable_upload", 0):
                    device_results["ethernet_results"][str(router_port)] = "Godkendt"
                    break
                else:
                    device_results["ethernet_results"][str(router_port)] = f"Fejlet ({download_speed}/{upload_speed})"
                    save_to_json(model_name, device_results)

            save_to_json(model_name, device_results)
        except Exception as e:
            print(f"[ERROR] Fejl ved test af port {switch_port}: {e}")
        finally:
            try:
                ssh_conn.close()
                print("[DEBUG] SSH-forbindelse til switchen lukket.")
            except Exception as e:
                print(f"[WARNING] Ignorerer fejl ved lukning af SSH-forbindelse: {e}")

        # Luk porten ved at følge disse trin:
        # 1. Skift til statisk IP uden en aktiv SSH-forbindelse.
        # 2. Genopret SSH-forbindelsen.
        # 3. Luk porten.
        set_static_ip_on_ethernet(ip_address, subnet_mask, gateway, dns_servers)

        for attempt in range(maximum_attempts):
            print(f"[DEBUG] Forsøger at lukke port {switch_port}, forsøg {attempt + 1} af {maximum_attempts}")
            ssh_conn = ssh_to_switch(hostname, username, password, internet_timeout, {}, maximum_attempts, switchname)
            if ssh_conn is None:
                print("[ERROR] Kunne ikke genoprette SSH-forbindelse til switchen.")
                continue

            try:
                send_command(ssh_conn, 'configure terminal')
                send_command(ssh_conn, f'interface GigabitEthernet1/0/{switch_port}')
                send_command(ssh_conn, 'shutdown')
                send_command(ssh_conn, 'exit')
                set_dhcp()
                print(f"[DEBUG] Port {switch_port} lukket via SSH.")
                break
            except Exception as e:
                print(f"[WARNING] Fejl ved lukning af port {switch_port}: {e}")
            finally:
                try:
                    ssh_conn.close()
                except:
                    pass


def parse_arguments():
    parser = argparse.ArgumentParser(description='Kør tests for specifikke routermodeller.')
    parser.add_argument('model_name', type=str, help='Routermodellen der skal testes.')
    parser.add_argument('number_of_devices', type=int, help='Antal routere der skal testes.')
    parser.add_argument('recipient_email', type=str, help='E-mailadresse til modtagelse af testresultater.')
    args = parser.parse_args()
    print(f"Kører tests for {args.model_name} med {args.number_of_devices} enheder, og sender resultater til {args.recipient_email}")
    return args.model_name, args.number_of_devices, args.recipient_email




def disable_ipv6():
    try:
        result = subprocess.run(
            'powershell -Command "Get-NetAdapter | ForEach-Object { Disable-NetAdapterBinding -Name $_.Name -ComponentID ms_tcpip6 }"',
            check=True, capture_output=True, shell=True, text=True
        )
        print("[INFO] IPv6 deaktiveret på alle interfaces.")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Fejl ved deaktivering af IPv6: {e.stderr}")

def enable_ipv6():
    try:
        result = subprocess.run(
            'powershell -Command "Get-NetAdapter | ForEach-Object { Enable-NetAdapterBinding -Name $_.Name -ComponentID ms_tcpip6 }"',
            check=True, capture_output=True, shell=True, text=True
        )
        print("[INFO] IPv6 aktiveret på alle interfaces.")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Fejl ved aktivering af IPv6: {e.stderr}")



if __name__ == "__main__":
    model_name, number_of_devices, recipient_email = parse_arguments()
    run_test(model_name, number_of_devices, recipient_email)
