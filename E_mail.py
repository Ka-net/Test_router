import paramiko
import time
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
import wmi
import configparser
import sys
import socket
import os

import subprocess



# Load config data from config.ini
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

    email_settings = config["EmailSettings"]
    sender_email = email_settings.get("sender_email")
    sender_password = email_settings.get("sender_password")
    smtp_server = email_settings.get("smtp_server")
    smtp_port = email_settings.getint("smtp_port")

    return (ip_address, subnet_mask, gateway, dns_servers, hostname, username, password, 
            switchname, sender_email, sender_password, smtp_server, smtp_port)

def load_recipients(file_path="emails.json"):
    try:
        with open(file_path, "r") as file:
            data = json.load(file)
        return data.get("recipients", [])
    except FileNotFoundError:
        print("[ERROR] emails.json file not found.")
        return []


def generate_failure_report(file_path="test_results.json"):
    try:
        with open(file_path, "r", encoding="utf-8-sig") as file:
            test_results = json.load(file)

        report = []
        for entry in test_results:
            for model, data in entry.items():
                router_number = data.get("router_number", "Ukendt")
                router_report = f"Router {router_number} ({model}):"
                
                # Check Wi-Fi results
                wifi_issues = []
                for band, status in data.get("wifi_results", {}).items():
                    if status != "Godkendt":
                        wifi_issues.append(f"Wi-Fi {band}: {status}")
                
                # Check Ethernet results
                ethernet_issues = []
                for port, status in data.get("ethernet_results", {}).items():
                    if status != "Godkendt":
                        ethernet_issues.append(f"Ethernet port {port}: {status}")
                
                # Saml rapporten for denne router
                if wifi_issues or ethernet_issues:
                    report.append(router_report)
                    report.extend(wifi_issues)
                    report.extend(ethernet_issues)
                    report.append("")  # Ekstra linje mellem routere
        
        return "\n".join(report) if report else "Alle tests bestået."
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSONDecodeError: {e}")
        return "[ERROR] Fejl ved indlæsning af test_results.json"
    except FileNotFoundError:
        return "[ERROR] test_results.json file not found."


# SMTP server check function
def check_smtp_server(smtp_server, smtp_port, max_attempts):
    print("[DEBUG] Tjekker SMTP-server...")
    attempt = 0
    while attempt < max_attempts:
        try:
            # Forsøg at oprette forbindelse til SMTP-serveren
            with socket.create_connection((smtp_server, smtp_port), timeout=10):
                print("[INFO] SMTP-server er tilgængelig.")
                return True
        except (socket.timeout, ConnectionRefusedError) as e:
            print(f"[WARNING] SMTP-server ikke tilgængelig, forsøg {attempt + 1}/{max_attempts}. Prøver igen...")
        except Exception as e:
            print(f"[ERROR] Fejl ved forbindelse til SMTP-server: {e}")
        time.sleep(5)
        attempt += 1
    print("[ERROR] Kunne ikke oprette forbindelse til SMTP-server efter flere forsøg.")
    return False


# Set static IP
def set_static_ip_on_ethernet(ip_address, subnet_mask, gateway, dns_servers):
    print(f"[DEBUG] Setting static IP {ip_address} on Ethernet...")
    c = wmi.WMI()
    adapters = c.Win32_NetworkAdapterConfiguration(IPEnabled=True)

    ethernet_adapter = None
    for adapter in adapters:
        if "Ethernet" in adapter.Description:
            ethernet_adapter = adapter
            break
    
    if ethernet_adapter:
        ethernet_adapter.EnableStatic(IPAddress=[ip_address], SubnetMask=[subnet_mask])
        ethernet_adapter.SetGateways(DefaultIPGateway=[gateway])
        ethernet_adapter.SetDNSServerSearchOrder(DNSServerSearchOrder=dns_servers)
        print(f"[DEBUG] Static IP set to {ip_address}.")
    else:
        print("[ERROR] No Ethernet adapter found.")

# SSH function that works for establishing a connection to the switch
def ssh_to_switch(hostname, username, password):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    retries = 3
    retry_delay = 5
    
    for attempt in range(retries):
        time.sleep(1)
        print(f"[DEBUG] Attempting SSH connection to {hostname}, attempt {attempt + 1} of {retries}...")
        try:
            client.connect(hostname, username=username, password=password, look_for_keys=False, allow_agent=False)
            print("[DEBUG] Connected to the switch!")
            ssh_conn = client.invoke_shell()
            time.sleep(1)
            return ssh_conn
        except paramiko.ssh_exception.NoValidConnectionsError as e:
            print(f"[ERROR] Could not connect to switch: {e}. Retrying in {retry_delay} seconds.")
        except Exception as e:
            print(f"[ERROR] Connection error: {e}. Retrying in {retry_delay} seconds.")
        
        time.sleep(retry_delay)
    
    print("[ERROR] Failed to establish SSH connection after multiple attempts.")
    return None


# Internet check function using HTTP request
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
            print("[WARNING] Ingen forbindelse. Prøver igen...")
        time.sleep(5)
    print("[DEBUG] Ingen internetforbindelse efter 1 minut.")
    return False

def open_port_and_send_email(ssh_conn, switch_port, router_number, sender_email, sender_password, smtp_server, smtp_port, max_attempts, recipient):
    try:
        def send_command(command):
            ssh_conn.send(command + "\n")
            time.sleep(1)
            output = ssh_conn.recv(65535).decode('utf-8')
            print(f"[SSH OUTPUT] {command}:\n{output}")

        # Åbn porten
        send_command('configure terminal')
        send_command(f'interface GigabitEthernet1/0/{switch_port}')
        send_command('no shutdown')
        print(f"[INFO] Port {switch_port} åbnet for Router {router_number}.")

        # Tjek internetforbindelse
        if not check_internet(60):
            print("[ERROR] Ingen internetforbindelse efter flere forsøg.")
            return

        # Send e-mail til den valgte modtager med resultaterne
        send_email_with_results(sender_email, sender_password, smtp_server, smtp_port, recipient['email'])
        
        # Luk porten efter 1 minut
        time.sleep(60)
        send_command('shutdown')
        print(f"[INFO] Port {switch_port} lukket efter 1 minut.")
        
        ssh_conn.close()
    except Exception as e:
        print(f"[ERROR] SSH command error: {e}")


def send_email_with_results(sender_email, sender_password, smtp_server, smtp_port, recipient_email):
    # Generer testfejlrapporten
    report = generate_failure_report()

    if not report:
        print("[INFO] Ingen fejl fundet i testresultaterne.")
        return

    # Opretter MIME-objekt for e-mailen
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = recipient_email
    message["Subject"] = "Test Resultater"

    # Tilføj rapporten til e-mailen
    message.attach(MIMEText(report, "plain"))

    try:
        # Send e-mailen
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # Brug TLS kryptering
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, message.as_string())
            print(f"[INFO] E-mail sendt til {recipient_email}")
    except Exception as e:
        print(f"[ERROR] Fejl ved sending af e-mail: {e}")



def send_email(sender_email, sender_password, smtp_server, smtp_port, recipient_email, subject, message):
    try:
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = recipient_email
        msg["Subject"] = subject
        msg.attach(MIMEText(message, "plain"))
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()
        
        print(f"[INFO] Email sent to: {recipient_email}")
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")

# Identify first approved port from test results
def find_first_approved_port():
    with open("test_results.json", "r") as file:
        test_results = json.load(file)
    
    for entry in test_results:
        for model, data in entry.items():
            for port, status in data.get("ethernet_results", {}).items():
                if status == "Godkendt":
                    return data["router_number"], port
    return None, None

def start_test_with_email(model_name, num_devices, recipient_name):
    print(f"[DEBUG] Starter test for {model_name} med {num_devices} enheder og sender til {recipient_name}")
    subprocess.run(["python", "samletscript.py", model_name, str(num_devices), recipient_name], check=True)


def generate_failure_report(file_path="test_results.json"):
    try:
        with open(file_path, "r", encoding="utf-8-sig") as file:
            test_results = json.load(file)

        report = []
        for entry in test_results:
            for model, data in entry.items():
                router_number = data.get("router_number", "Ukendt")
                router_report = f"Router {router_number} ({model}):"
                
                # Check Wi-Fi results
                wifi_issues = []
                for band, status in data.get("wifi_results", {}).items():
                    if status != "Godkendt":
                        wifi_issues.append(f"Wi-Fi {band}: {status}")
                
                # Check Ethernet results
                ethernet_issues = []
                for port, status in data.get("ethernet_results", {}).items():
                    if status != "Godkendt":
                        ethernet_issues.append(f"Ethernet port {port}: {status}")
                
                # Saml rapporten for denne router
                if wifi_issues or ethernet_issues:
                    report.append(router_report)
                    report.extend(wifi_issues)
                    report.extend(ethernet_issues)
                    report.append("")  # Ekstra linje mellem routere
        
        return "\n".join(report) if report else "Alle tests bestået."
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSONDecodeError: {e}")
        return "[ERROR] Fejl ved indlæsning af test_results.json"
    except FileNotFoundError:
        return "[ERROR] test_results.json file not found."



def main():
    if len(sys.argv) < 2:
        print("[ERROR] Ingen e-mail modtager angivet.")
        return
    
    # Hent modtagerens e-mail fra kommandolinjeargumentet
    recipient_email = sys.argv[1]
    recipients = load_recipients()
    
    # Find modtageren baseret på e-mail
    recipient = next((r for r in recipients if r['email'] == recipient_email), None)
    if not recipient:
        print(f"[ERROR] Modtager '{recipient_email}' ikke fundet.")
        return
    
    # Hent konfigurationen fra config.ini
    ip_address, subnet_mask, gateway, dns_servers, hostname, username, password, switchname, \
    sender_email, sender_password, smtp_server, smtp_port = load_config()

    max_attempts = 5  # Standardværdi, eller hent fra config, hvis nødvendigt

    # Set statisk IP
    set_static_ip_on_ethernet(ip_address, subnet_mask, gateway, dns_servers)

    # Find første godkendte port
    router_number, router_port = find_first_approved_port()
    if router_number and router_port:
        switch_port = 2 + (int(router_number) - 1) * 6 + int(router_port) - 1
        print(f"[INFO] Godkendt port fundet for Router {router_number}: Switchport {switch_port}")
        
        # Etabler SSH-forbindelse
        ssh_conn = ssh_to_switch(hostname, username, password)
        if ssh_conn:
            open_port_and_send_email(
                ssh_conn, switch_port, router_number, 
                sender_email, sender_password, smtp_server, smtp_port, max_attempts, recipient
            )
    else:
        print("[INFO] Ingen godkendt port fundet.")

# Sørg for, at denne del er i bunden af dit script:
if __name__ == "__main__":
    print("[DEBUG] Kører E_mail.py direkte som et script.")
    main()
