import tkinter as tk
from tkinter import ttk
from tkinter import messagebox, Canvas, Frame
from PIL import Image, ImageTk  # Import for at arbejde med billeder
import threading
import json
import time
import subprocess
import smtplib
from samletscript import shutdown_ports_on_switch, load_config, run_test
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import configparser
import os
import ctypes
import pythoncom
import wmi
import psutil
import signal
import sys
from samletscript import shutdown_ports_on_switch, load_config

# --- Tooltip-klassen ---
class CreateToolTip:
    """
    Opretter en tooltip for et widget, der kan opdateres med ny tekst.
    """
    def __init__(self, widget, text='Info'):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        widget.bind("<Enter>", self.enter)
        widget.bind("<Leave>", self.leave)

    def update_text(self, text):
        """Opdaterer tooltip-teksten; hvis tooltip'en er vist, lukkes den og vises med den nye tekst."""
        self.text = text
        if self.tipwindow:
            self.hidetip()
            self.showtip()

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(500, self.showtip)

    def unschedule(self):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None

    def showtip(self, event=None):
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hidetip(self):
        if self.tipwindow:
            self.tipwindow.destroy()
        self.tipwindow = None

# --- Globale variabler og initialisering ---
test_running = True
wifi_table = {}
ethernet_table = {}

root = tk.Tk()
root.title("Modem/Router Test GUI")
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
root.state('zoomed')  # Dette virker på Windows og Linux
images = {}
test_thread = None

def toggle_button():
    """
    Skifter mellem 'Stop Test'-knappen og 'Gå til Start'-knappen.
    """
    for widget in root.winfo_children():
        if isinstance(widget, tk.Button):
            widget.destroy()
    if test_running:
        stop_button = tk.Button(root, text="Stop Test", font=("Arial", 16), command=stop_test)
        stop_button.place(relx=1.0, rely=0.0, anchor="ne")
    else:
        start_button = tk.Button(root, text="Gå til Startskærm", font=("Arial", 16), command=show_initial_screen)
        start_button.place(relx=1.0, rely=0.0, anchor="ne")
    root.update_idletasks()

def add_logo_to_window(root):
    try:
        logo_image = Image.open("logo.png").resize((200, 176), Image.LANCZOS)
        logo_photo = ImageTk.PhotoImage(logo_image)
        logo_label = tk.Label(root, image=logo_photo, bg=root["bg"])
        logo_label.image = logo_photo
        logo_label.place(relx=1.0, rely=1.0, anchor="se")
    except Exception as e:
        print(f"[ERROR] Kunne ikke indlæse logo: {e}")

def load_images():
    """Indlæs billeder og gem dem som globale variabler."""
    try:
        images["WifiWait"] = ImageTk.PhotoImage(Image.open("WifiWait.png").resize((50, 50)))
        images["WifiOk"] = ImageTk.PhotoImage(Image.open("WifiOk.png").resize((50, 50)))
        images["WifiFail"] = ImageTk.PhotoImage(Image.open("WifiFail.png").resize((50, 50)))
        images["EthernetWait"] = ImageTk.PhotoImage(Image.open("EthernetWait.png").resize((50, 50)))
        images["EthernetOk"] = ImageTk.PhotoImage(Image.open("EthernetOk.png").resize((50, 50)))
        images["EthernetFail"] = ImageTk.PhotoImage(Image.open("EthernetFail.png").resize((50, 50)))
    except Exception as e:
        print(f"[ERROR] Fejl ved indlæsning af billeder: {e}")

def update_buttons():
    """
    Opdater knapper baseret på teststatus.
    """
    for widget in root.winfo_children():
        if isinstance(widget, tk.Button):
            widget.destroy()
    if test_running:
        stop_button = tk.Button(root, text="Stop Test", font=("Arial", 16), command=stop_test)
        stop_button.place(relx=1.0, rely=0.0, anchor="ne")
    else:
        start_button = tk.Button(root, text="Gå til Startskærm", font=("Arial", 16), command=show_initial_screen)
        start_button.place(relx=1.0, rely=0.0, anchor="ne")

def restart_script():
    """
    Genstarter hele scriptet.
    """
    try:
        print("[DEBUG] Genstarter scriptet...")
        python_exe = sys.executable
        os.execv(python_exe, [python_exe] + sys.argv)
    except Exception as e:
        print(f"[ERROR] Fejl ved genstart: {e}")

def stop_test():
    global test_running
    print("[DEBUG] Stopper testen...")
    test_running = False
    try:
        config_values = load_config()
        hostname, username, password, switchname = config_values[4], config_values[5], config_values[6], config_values[11]
        shutdown_ports_on_switch(hostname, username, password, switchname)
        print("[DEBUG] Alle porte er nu lukkede.")
    except Exception as e:
        print(f"[ERROR] Fejl i lukning af porte: {e}")
    toggle_button()
    restart_script()

def load_devices(device_type=None):
    try:
        with open("devices_db.json", "r") as file:
            data = json.load(file)
            if device_type:
                data = {name: info for name, info in data.items() if info["type"] == device_type}
            return data
    except Exception as e:
        print(f"[ERROR] Fejl ved indlæsning af devices_db.json: {e}")
        return {}

# Her følger funktioner til håndtering af enheder (show_device_list, confirm_remove_device, device_form, save_device) 
# – behold dem som i din originale version.

def show_device_list(action, device_type):
    clear_window()
    action_title = "Rediger" if action == "edit" else "Fjern" if action == "remove" else "Tilføj"
    tk.Label(root, text=f"Vælg enhed til {action_title}:", font=("Arial", 18)).pack(pady=10)
    devices = load_devices()
    filtered_devices = {name: info for name, info in devices.items() if info["type"] == device_type}
    if not filtered_devices and action != "add":
        tk.Label(root, text="Ingen enheder fundet.", font=("Arial", 14)).pack()
        tk.Button(root, text="Tilbage", font=("Arial", 14), command=lambda: select_device_type(action)).pack(pady=20)
        return
    if action == "add":
        device_form("add", device_type)
    else:
        for device_name, device_info in filtered_devices.items():
            if action == "remove":
                tk.Button(root, text=device_name, font=("Arial", 14),
                          command=lambda name=device_name: confirm_remove_device(name)).pack(pady=5)
            elif action == "edit":
                tk.Button(root, text=device_name, font=("Arial", 14),
                          command=lambda name=device_name, info=device_info: device_form("edit", device_type, name, info)).pack(pady=5)
    tk.Button(root, text="Tilbage", font=("Arial", 14), command=lambda: select_device_type(action)).pack(pady=20)
    add_logo_to_window(root)

def confirm_remove_device(device_name):
    answer = messagebox.askyesno("Bekræft Sletning", f"Er du sikker på, at du vil slette '{device_name}'?")
    if answer:
        devices = load_devices()
        if device_name in devices:
            del devices[device_name]
            save_devices(devices)
            messagebox.showinfo("Succes", f"Enheden '{device_name}' er blevet fjernet.")
        show_device_list("remove", "router")
    else:
        show_device_list("remove", "router")

def device_form(action, device_type, device_name=None, device_info=None):
    clear_window()
    title_action = "Rediger" if action == "edit" else "Tilføj"
    tk.Label(root, text=f"{title_action} {device_type.capitalize()} Detaljer:", font=("Arial", 18)).pack(pady=10)
    tk.Label(root, text="Producent:").pack()
    producent_entry = tk.Entry(root)
    producent_entry.pack()
    if device_info:
        producent_entry.insert(0, device_info.get("producent", ""))
    tk.Label(root, text="Model:").pack()
    model_entry = tk.Entry(root)
    model_entry.pack()
    if device_info:
        model_entry.insert(0, device_info.get("model", ""))
    tk.Label(root, text="Antal Ethernet-porte:").pack()
    ethernet_ports_var = tk.StringVar(value=str(device_info.get("ethernet_ports", "0")) if device_info else "0")
    ethernet_ports_menu = tk.OptionMenu(root, ethernet_ports_var, *[str(i) for i in range(7)])
    ethernet_ports_menu.pack()
    tk.Label(root, text="Kabel Downloadhastighed (Mbps):").pack()
    cable_download_entry = tk.Entry(root)
    cable_download_entry.pack()
    if device_info:
        cable_download_entry.insert(0, device_info["speeds"].get("cable_download", ""))
    tk.Label(root, text="Kabel Uploadhastighed (Mbps):").pack()
    cable_upload_entry = tk.Entry(root)
    cable_upload_entry.pack()
    if device_info:
        cable_upload_entry.insert(0, device_info["speeds"].get("cable_upload", ""))
    if device_type == "router":
        def toggle_field(entry_widget, label_widget, enabled):
            state = "normal" if enabled else "disabled"
            entry_widget.config(state=state)
            label_widget.config(state=state)
        has_24ghz = tk.BooleanVar(value=device_info.get("2.4ghz", False) if device_info else False)
        tk.Checkbutton(root, text="2.4 GHz Wi-Fi", variable=has_24ghz).pack()
        wifi_24ghz_download_label = tk.Label(root, text="2.4 GHz Download (Mbps):")
        wifi_24ghz_download_entry = tk.Entry(root)
        wifi_24ghz_upload_label = tk.Label(root, text="2.4 GHz Upload (Mbps):")
        wifi_24ghz_upload_entry = tk.Entry(root)
        wifi_24ghz_download_label.pack()
        wifi_24ghz_download_entry.pack()
        wifi_24ghz_upload_label.pack()
        wifi_24ghz_upload_entry.pack()
        if device_info:
            wifi_24ghz_download_entry.insert(0, device_info["speeds"].get("wifi_24ghz_download", ""))
            wifi_24ghz_upload_entry.insert(0, device_info["speeds"].get("wifi_24ghz_upload", ""))
        toggle_field(wifi_24ghz_download_entry, wifi_24ghz_download_label, has_24ghz.get())
        toggle_field(wifi_24ghz_upload_entry, wifi_24ghz_upload_label, has_24ghz.get())
        has_24ghz.trace("w", lambda *args: toggle_field(wifi_24ghz_download_entry, wifi_24ghz_download_label, has_24ghz.get()))
        has_24ghz.trace("w", lambda *args: toggle_field(wifi_24ghz_upload_entry, wifi_24ghz_upload_label, has_24ghz.get()))
        has_5ghz = tk.BooleanVar(value=device_info.get("5ghz", False) if device_info else False)
        tk.Checkbutton(root, text="5 GHz Wi-Fi", variable=has_5ghz).pack()
        wifi_5ghz_download_label = tk.Label(root, text="5 GHz Download (Mbps):")
        wifi_5ghz_download_entry = tk.Entry(root)
        wifi_5ghz_upload_label = tk.Label(root, text="5 GHz Upload (Mbps):")
        wifi_5ghz_upload_entry = tk.Entry(root)
        wifi_5ghz_download_label.pack()
        wifi_5ghz_download_entry.pack()
        wifi_5ghz_upload_label.pack()
        wifi_5ghz_upload_entry.pack()
        if device_info:
            wifi_5ghz_download_entry.insert(0, device_info["speeds"].get("wifi_5ghz_download", ""))
            wifi_5ghz_upload_entry.insert(0, device_info["speeds"].get("wifi_5ghz_upload", ""))
        toggle_field(wifi_5ghz_download_entry, wifi_5ghz_download_label, has_5ghz.get())
        toggle_field(wifi_5ghz_upload_entry, wifi_5ghz_upload_label, has_5ghz.get())
        has_5ghz.trace("w", lambda *args: toggle_field(wifi_5ghz_download_entry, wifi_5ghz_download_label, has_5ghz.get()))
        has_5ghz.trace("w", lambda *args: toggle_field(wifi_5ghz_upload_entry, wifi_5ghz_upload_label, has_5ghz.get()))
        has_6ghz = tk.BooleanVar(value=device_info.get("6ghz", False) if device_info else False)
        tk.Checkbutton(root, text="6 GHz Wi-Fi", variable=has_6ghz).pack()
        wifi_6ghz_download_label = tk.Label(root, text="6 GHz Download (Mbps):")
        wifi_6ghz_download_entry = tk.Entry(root)
        wifi_6ghz_upload_label = tk.Label(root, text="6 GHz Upload (Mbps):")
        wifi_6ghz_upload_entry = tk.Entry(root)
        wifi_6ghz_download_label.pack()
        wifi_6ghz_download_entry.pack()
        wifi_6ghz_upload_label.pack()
        wifi_6ghz_upload_entry.pack()
        if device_info:
            wifi_6ghz_download_entry.insert(0, device_info["speeds"].get("wifi_6ghz_download", ""))
            wifi_6ghz_upload_entry.insert(0, device_info["speeds"].get("wifi_6ghz_upload", ""))
        toggle_field(wifi_6ghz_download_entry, wifi_6ghz_download_label, has_6ghz.get())
        toggle_field(wifi_6ghz_upload_entry, wifi_6ghz_upload_label, has_6ghz.get())
        has_6ghz.trace("w", lambda *args: toggle_field(wifi_6ghz_download_entry, wifi_6ghz_download_label, has_6ghz.get()))
        has_6ghz.trace("w", lambda *args: toggle_field(wifi_6ghz_upload_entry, wifi_6ghz_upload_label, has_6ghz.get()))
    confirm_btn = tk.Button(root, text="Gem Ændringer" if action == "edit" else "Tilføj",
                            command=lambda: save_device(
                                action, device_type, producent_entry.get(), model_entry.get(),
                                ethernet_ports_var.get(), cable_download_entry.get(), cable_upload_entry.get(),
                                wifi_24ghz_download_entry.get() if has_24ghz.get() else None,
                                wifi_24ghz_upload_entry.get() if has_24ghz.get() else None,
                                wifi_5ghz_download_entry.get() if has_5ghz.get() else None,
                                wifi_5ghz_upload_entry.get() if has_5ghz.get() else None,
                                wifi_6ghz_download_entry.get() if has_6ghz.get() else None,
                                wifi_6ghz_upload_entry.get() if has_6ghz.get() else None,
                                has_24ghz.get(), has_5ghz.get(), has_6ghz.get(),
                                device_name))
    confirm_btn.pack(pady=20)
    if action == "edit":
        back_button = tk.Button(root, text="Tilbage", font=("Arial", 14),
                                command=lambda: show_device_list("edit", device_type))
        back_button.pack(pady=10)

def save_device(action, device_type, producent, model, ethernet_ports, cable_download, cable_upload,
                wifi_24ghz_download=None, wifi_24ghz_upload=None, 
                wifi_5ghz_download=None, wifi_5ghz_upload=None,
                wifi_6ghz_download=None, wifi_6ghz_upload=None,
                has_24ghz=False, has_5ghz=False, has_6ghz=False, device_name=None):
    devices = load_devices()
    if action == "edit" and device_name:
        device_key = device_name
    else:
        device_key = f"{model}_{int(time.time())}"
    devices[device_key] = {
        "producent": producent,
        "model": model,
        "ethernet_ports": int(ethernet_ports) if ethernet_ports else 0,
        "speeds": {
            "cable_download": int(cable_download) if cable_download else 0,
            "cable_upload": int(cable_upload) if cable_upload else 0,
            "wifi_24ghz_download": int(wifi_24ghz_download) if wifi_24ghz_download else 0,
            "wifi_24ghz_upload": int(wifi_24ghz_upload) if wifi_24ghz_upload else 0,
            "wifi_5ghz_download": int(wifi_5ghz_download) if wifi_5ghz_download else 0,
            "wifi_5ghz_upload": int(wifi_5ghz_upload) if wifi_5ghz_upload else 0,
            "wifi_6ghz_download": int(wifi_6ghz_download) if wifi_6ghz_download else 0,
            "wifi_6ghz_upload": int(wifi_6ghz_upload) if wifi_6ghz_upload else 0
        },
        "2.4ghz": has_24ghz,
        "5ghz": has_5ghz,
        "6ghz": has_6ghz,
        "type": device_type
    }
    try:
        with open("devices_db.json", "w") as file:
            json.dump(devices, file, indent=4)
        print(f"[INFO] {model} gemt succesfuldt under nøglen {device_key}.")
    except Exception as e:
        print(f"[ERROR] Fejl ved gemning af enhed: {e}")
    clear_window()
    if action == "edit":
        show_device_list("edit", device_type)
    else:
        modify_router()
    for process in psutil.process_iter(attrs=['pid', 'name']):
        if model in process.info['name']:
            print(f"[DEBUG] Dræber proces: {process.info['name']} (PID: {process.info['pid']})")
            psutil.Process(process.info['pid']).terminate()

def clear_window():
    for widget in root.winfo_children():
        widget.destroy()

def open_settings():
    settings_window = tk.Toplevel(root)
    settings_window.title("Rediger Indstillinger")
    settings_window.geometry("700x600")
    canvas = Canvas(settings_window)
    scrollbar = tk.Scrollbar(settings_window, orient="vertical", command=canvas.yview)
    scrollable_frame = Frame(canvas)
    scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    config = configparser.ConfigParser()
    config.read("config.ini")
    sections_needed = ["NetworkSettings", "SSH", "InternetCheck", "WifiSettings", "WifiRouterSettings", "EmailSettings"]
    for section in sections_needed:
        if section not in config:
            messagebox.showerror("Fejl", f"Sektionen '{section}' findes ikke i config.ini.")
            return
    def save_settings():
        config["NetworkSettings"]["ip_address"] = static_ip_entry.get()
        config["NetworkSettings"]["subnet_mask"] = subnet_mask_entry.get()
        config["NetworkSettings"]["gateway"] = gateway_entry.get()
        config["NetworkSettings"]["dns_servers"] = dns_entry.get()
        config["SSH"]["hostname"] = ssh_ip_entry.get()
        config["SSH"]["username"] = ssh_user_entry.get()
        config["SSH"]["password"] = ssh_password_entry.get()
        config["SSH"]["switchname"] = ssh_switch_entry.get()
        config["InternetCheck"]["timeout"] = timeout_entry.get()
        config["WifiSettings"]["wifi_interface"] = wifi_interface_entry.get()
        config["WifiSettings"]["wifi_prefix"] = wifi_prefix_entry.get()
        config["WifiSettings"]["wifi_password"] = wifi_password_entry.get()
        config["WifiSettings"]["ip_prefix"] = wifi_ip_prefix_entry.get()
        config["WifiRouterSettings"]["maximum_attempts"] = attempts_entry.get()
        config["EmailSettings"]["sender_email"] = email_entry.get()
        config["EmailSettings"]["sender_password"] = email_password_entry.get()
        config["EmailSettings"]["smtp_server"] = smtp_server_entry.get()
        config["EmailSettings"]["smtp_port"] = smtp_port_entry.get()
        with open("config.ini", "w") as configfile:
            config.write(configfile)
        messagebox.showinfo("Gem Indstillinger", "Indstillingerne er gemt.")
        settings_window.destroy()
    tk.Label(scrollable_frame, text="Netværk", font=("Arial", 14)).grid(row=0, column=0, pady=5, sticky="w")
    tk.Label(scrollable_frame, text="IP-adresse").grid(row=1, column=0, sticky="e")
    static_ip_entry = tk.Entry(scrollable_frame)
    static_ip_entry.insert(0, config.get("NetworkSettings", "ip_address", fallback=""))
    static_ip_entry.grid(row=1, column=1, sticky="w")
    tk.Label(scrollable_frame, text="Subnetmaske").grid(row=2, column=0, sticky="e")
    subnet_mask_entry = tk.Entry(scrollable_frame)
    subnet_mask_entry.insert(0, config.get("NetworkSettings", "subnet_mask", fallback=""))
    subnet_mask_entry.grid(row=2, column=1, sticky="w")
    tk.Label(scrollable_frame, text="Gateway").grid(row=3, column=0, sticky="e")
    gateway_entry = tk.Entry(scrollable_frame)
    gateway_entry.insert(0, config.get("NetworkSettings", "gateway", fallback=""))
    gateway_entry.grid(row=3, column=1, sticky="w")
    tk.Label(scrollable_frame, text="DNS-servere").grid(row=4, column=0, sticky="e")
    dns_entry = tk.Entry(scrollable_frame)
    dns_entry.insert(0, config.get("NetworkSettings", "dns_servers", fallback=""))
    dns_entry.grid(row=4, column=1, sticky="w")
    tk.Label(scrollable_frame, text="Internet Timeout", font=("Arial", 14)).grid(row=5, column=0, pady=5, sticky="w")
    tk.Label(scrollable_frame, text="Timeout i sekunder").grid(row=6, column=0, sticky="e")
    timeout_entry = tk.Entry(scrollable_frame)
    timeout_entry.insert(0, config.get("InternetCheck", "timeout", fallback="60"))
    timeout_entry.grid(row=6, column=1, sticky="w")
    tk.Label(scrollable_frame, text="WiFi", font=("Arial", 14)).grid(row=7, column=0, pady=5, sticky="w")
    tk.Label(scrollable_frame, text="Interface").grid(row=8, column=0, sticky="e")
    wifi_interface_entry = tk.Entry(scrollable_frame)
    wifi_interface_entry.insert(0, config.get("WifiSettings", "wifi_interface", fallback=""))
    wifi_interface_entry.grid(row=8, column=1, sticky="w")
    tk.Label(scrollable_frame, text="Navnepræfiks").grid(row=9, column=0, sticky="e")
    wifi_prefix_entry = tk.Entry(scrollable_frame)
    wifi_prefix_entry.insert(0, config.get("WifiSettings", "wifi_prefix", fallback=""))
    wifi_prefix_entry.grid(row=9, column=1, sticky="w")
    tk.Label(scrollable_frame, text="WiFi Kodeord").grid(row=10, column=0, sticky="e")
    wifi_password_entry = tk.Entry(scrollable_frame, show="*")
    wifi_password_entry.insert(0, config.get("WifiSettings", "wifi_password", fallback=""))
    wifi_password_entry.grid(row=10, column=1, sticky="w")
    tk.Label(scrollable_frame, text="IP-præfiks").grid(row=11, column=0, sticky="e")
    wifi_ip_prefix_entry = tk.Entry(scrollable_frame)
    wifi_ip_prefix_entry.insert(0, config.get("WifiSettings", "ip_prefix", fallback=""))
    wifi_ip_prefix_entry.grid(row=11, column=1, sticky="w")
    tk.Label(scrollable_frame, text="SSH", font=("Arial", 14)).grid(row=0, column=2, pady=5, sticky="w")
    tk.Label(scrollable_frame, text="IP-adresse").grid(row=1, column=2, sticky="e")
    ssh_ip_entry = tk.Entry(scrollable_frame)
    ssh_ip_entry.insert(0, config.get("SSH", "hostname", fallback=""))
    ssh_ip_entry.grid(row=1, column=3, sticky="w")
    tk.Label(scrollable_frame, text="Brugernavn").grid(row=2, column=2, sticky="e")
    ssh_user_entry = tk.Entry(scrollable_frame)
    ssh_user_entry.insert(0, config.get("SSH", "username", fallback=""))
    ssh_user_entry.grid(row=2, column=3, sticky="w")
    tk.Label(scrollable_frame, text="Kodeord").grid(row=3, column=2, sticky="e")
    ssh_password_entry = tk.Entry(scrollable_frame, show="*")
    ssh_password_entry.insert(0, config.get("SSH", "password", fallback=""))
    ssh_password_entry.grid(row=3, column=3, sticky="w")
    tk.Label(scrollable_frame, text="Switch Navn").grid(row=4, column=2, sticky="e")
    ssh_switch_entry = tk.Entry(scrollable_frame)
    ssh_switch_entry.insert(0, config.get("SSH", "switchname", fallback=""))
    ssh_switch_entry.grid(row=4, column=3, sticky="w")
    tk.Label(scrollable_frame, text="Router Indstillinger", font=("Arial", 14)).grid(row=5, column=2, pady=5, sticky="w")
    tk.Label(scrollable_frame, text="Max Forsøg").grid(row=6, column=2, sticky="e")
    attempts_entry = tk.Entry(scrollable_frame)
    attempts_entry.insert(0, config.get("WifiRouterSettings", "maximum_attempts", fallback=""))
    attempts_entry.grid(row=6, column=3, sticky="w")
    tk.Label(scrollable_frame, text="E-mail Indstillinger", font=("Arial", 14)).grid(row=7, column=2, pady=5, sticky="w")
    tk.Label(scrollable_frame, text="Afsender E-mail").grid(row=8, column=2, sticky="e")
    email_entry = tk.Entry(scrollable_frame)
    email_entry.insert(0, config.get("EmailSettings", "sender_email", fallback=""))
    email_entry.grid(row=8, column=3, sticky="w")
    tk.Label(scrollable_frame, text="SMTP Kodeord").grid(row=9, column=2, sticky="e")
    email_password_entry = tk.Entry(scrollable_frame, show="*")
    email_password_entry.insert(0, config.get("EmailSettings", "sender_password", fallback=""))
    email_password_entry.grid(row=9, column=3, sticky="w")
    tk.Label(scrollable_frame, text="SMTP Server").grid(row=10, column=2, sticky="e")
    smtp_server_entry = tk.Entry(scrollable_frame)
    smtp_server_entry.insert(0, config.get("EmailSettings", "smtp_server", fallback=""))
    smtp_server_entry.grid(row=10, column=3, sticky="w")
    tk.Label(scrollable_frame, text="SMTP Port").grid(row=11, column=2, sticky="e")
    smtp_port_entry = tk.Entry(scrollable_frame)
    smtp_port_entry.insert(0, config.get("EmailSettings", "smtp_port", fallback="587"))
    smtp_port_entry.grid(row=11, column=3, sticky="w")
    save_button = tk.Button(scrollable_frame, text="Gem Ændringer", command=save_settings)
    save_button.grid(row=12, column=0, columnspan=4, pady=20)

def modify_router():
    clear_window()
    tk.Label(root, text="Vil du tilføje, fjerne eller redigere en enhed?", font=("Arial", 18)).pack(pady=10)
    tk.Button(root, text="Tilføj", font=("Arial", 14), command=lambda: select_device_type("add")).pack(pady=10)
    tk.Button(root, text="Fjern", font=("Arial", 14), command=lambda: select_device_type("remove")).pack(pady=10)
    tk.Button(root, text="Rediger", font=("Arial", 14), command=lambda: select_device_type("edit")).pack(pady=10)
    tk.Button(root, text="Tilbage", font=("Arial", 14), command=show_initial_screen).pack(pady=20)
    add_logo_to_window(root)

def send_email_with_results(recipient_email):
    results = "Testresultaterne..."  # Placeholder for faktiske resultater
    config = configparser.ConfigParser()
    config.read('config.ini')
    sender_email = config.get("EmailSettings", "sender_email")
    sender_password = config.get("EmailSettings", "sender_password")
    smtp_server = config.get("EmailSettings", "smtp_server")
    smtp_port = config.get("EmailSettings", "smtp_port")
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = recipient_email
    message["Subject"] = "Test Resultater"
    message.attach(MIMEText(results, "plain"))
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, message.as_string())
            print("[INFO] Email sendt til", recipient_email)
    except Exception as e:
        print(f"[ERROR] Fejl ved sending af email: {e}")

def select_recipient(model_name, num_devices, device_type):
    clear_window()
    tk.Label(root, text="Vælg Modtager", font=("Arial", 24)).pack(pady=20)
    recipients = load_recipients()
    if not recipients:
        tk.Label(root, text="Ingen modtagere fundet.", font=("Arial", 16)).pack(pady=20)
        tk.Button(root, text="Tilbage", font=("Arial", 14), 
                  command=lambda: choose_number_of_devices(model_name, device_type)).pack(pady=20)
        return
    for recipient in recipients:
        btn = tk.Button(root, text=f"{recipient['name']} ({recipient['email']})", font=("Arial", 18),
                        command=lambda r=recipient: show_waiting_screen(model_name, num_devices, r['email']))
        btn.pack(pady=10)
    add_logo_to_window(root)
    tk.Button(root, text="Tilbage", font=("Arial", 14), 
              command=lambda: choose_number_of_devices(model_name, device_type)).pack(pady=20)

def start_test(model_name, num_devices, recipient_email):
    global test_running
    test_running = True
    toggle_button()
    test_thread = threading.Thread(target=run_script_in_thread, args=(model_name, num_devices, recipient_email), daemon=True)
    test_thread.start()
    threading.Thread(target=monitor_results_file, daemon=True).start()
    test_running = False
    show_status_screen(model_name, num_devices)

def finish_test():
    global test_running
    test_running = False
    toggle_button()
    print("[DEBUG] Testen er færdig.")

def show_waiting_screen(model_name, num_devices, recipient_email, wait_time=30*60):
    clear_window()
    tk.Label(root, text="Forberedelse før testen starter", font=("Arial", 24)).pack(pady=20)
    countdown_label = tk.Label(root, text="", font=("Arial", 18))
    countdown_label.pack(pady=20)
    def countdown(remaining_time, label_ref):
        if remaining_time > 0:
            minutes, seconds = divmod(remaining_time, 60)
            try:
                label_ref.config(text=f"Testen starter om {minutes:02}:{seconds:02}")
                root.after(1000, countdown, remaining_time - 1, label_ref)
            except tk.TclError:
                print("[DEBUG] Nedtællingen blev afbrudt.")
        else:
            start_test(model_name, num_devices, recipient_email)
    countdown(wait_time, countdown_label)
    tk.Button(root, text="Spring Over", font=("Arial", 16), 
              command=lambda: start_test(model_name, num_devices, recipient_email)).pack(pady=20)
    tk.Button(root, text="Annuller", font=("Arial", 16), command=show_initial_screen).pack(pady=20)

def run_script_in_thread(model_name, num_devices, recipient_email=None):
    pythoncom.CoInitialize()
    try:
        run_test(model_name, num_devices, recipient_email)
    except Exception as e:
        print(f"[ERROR] Fejl under kørsel af test i tråd: {e}")
    finally:
        pythoncom.CoUninitialize()
        root.after(0, finish_test)

def show_status_screen(model_name, num_devices):
    global wifi_table, ethernet_table, test_running
    clear_window()
    test_running = True
    tk.Label(root, text=f"Status for {model_name}", font=("Arial", 24)).pack(pady=20)
    table_frame = tk.Frame(root)
    table_frame.pack(pady=20)
    wifi_table, ethernet_table = {}, {}
    devices = load_devices()
    device_info = devices.get(model_name, {})
    for device_num in range(1, num_devices + 1):
        router_key = f"Router {device_num}"
        tk.Label(table_frame, text=router_key, font=("Arial", 16)).grid(row=(device_num - 1) * 2, column=0, sticky="w", padx=10, pady=10)
        # Wi-Fi ikoner med tooltip
        wifi_frequencies = [freq for freq in ['2.4ghz', '5ghz', '6ghz'] if device_info.get(freq)]
        wifi_table[router_key] = []
        column_offset = 1
        for freq in wifi_frequencies:
            tk.Label(table_frame, text=f"{freq}", font=("Arial", 10)).grid(row=(device_num - 1) * 2, column=column_offset, padx=5)
            wifi_label = tk.Label(table_frame, image=images["WifiWait"])
            wifi_label.grid(row=(device_num - 1) * 2 + 1, column=column_offset, padx=5)
            wifi_label.tooltip = CreateToolTip(wifi_label, text="Status: N/A")
            wifi_table[router_key].append(wifi_label)
            column_offset += 1
        # Ethernet ikoner med tooltip
        ethernet_ports = device_info.get("ethernet_ports", 1)
        ethernet_table[router_key] = []
        for port in range(1, ethernet_ports + 1):
            tk.Label(table_frame, text=f"Port {port}", font=("Arial", 10)).grid(row=(device_num - 1) * 2, column=column_offset, padx=5)
            eth_label = tk.Label(table_frame, image=images["EthernetWait"])
            eth_label.grid(row=(device_num - 1) * 2 + 1, column=column_offset, padx=5)
            eth_label.tooltip = CreateToolTip(eth_label, text="Status: N/A")
            ethernet_table[router_key].append(eth_label)
            column_offset += 1
    add_logo_to_window(root)
    update_buttons()

def update_test_statuses(router_key, wifi_results, ethernet_results):
    if router_key not in wifi_table or router_key not in ethernet_table:
        print(f"[ERROR] Router '{router_key}' ikke fundet i wifi_table eller ethernet_table.")
        return
    # Opdater Wi-Fi-status
    for freq, status in wifi_results.items():
        if freq in ['2.4ghz', '5ghz', '6ghz']:
            index = ['2.4ghz', '5ghz', '6ghz'].index(freq)
            if index < len(wifi_table[router_key]):
                if status == "Godkendt":
                    wifi_table[router_key][index].config(image=images["WifiOk"])
                    wifi_table[router_key][index].image = images["WifiOk"]
                elif "Fejlet" in status:
                    wifi_table[router_key][index].config(image=images["WifiFail"])
                    wifi_table[router_key][index].image = images["WifiFail"]
                else:
                    wifi_table[router_key][index].config(image=images["WifiWait"])
                    wifi_table[router_key][index].image = images["WifiWait"]
                wifi_table[router_key][index].tooltip.update_text(status)
    # Opdater Ethernet-status
    for port, status in ethernet_results.items():
        port_index = int(port) - 1
        if port_index < len(ethernet_table[router_key]):
            if status == "Godkendt":
                ethernet_table[router_key][port_index].config(image=images["EthernetOk"])
                ethernet_table[router_key][port_index].image = images["EthernetOk"]
            elif "Offline" in status or status.strip() == "Offline":
                ethernet_table[router_key][port_index].config(image=images["EthernetFail"])
                ethernet_table[router_key][port_index].image = images["EthernetFail"]
            elif "Fejlet" in status or status.startswith("Fejlet"):
                ethernet_table[router_key][port_index].config(image=images["EthernetFail"])
                ethernet_table[router_key][port_index].image = images["EthernetFail"]
            else:
                ethernet_table[router_key][port_index].config(image=images["EthernetWait"])
                ethernet_table[router_key][port_index].image = images["EthernetWait"]
            ethernet_table[router_key][port_index].tooltip.update_text(status)

def test_update_images():
    router_key = "Router 1"
    if router_key in wifi_table:
        wifi_table[router_key][0].config(image=images["WifiOk"])
        wifi_table[router_key][0].image = images["WifiOk"]
    if router_key in ethernet_table:
        ethernet_table[router_key][0].config(image=images["EthernetOk"])
        ethernet_table[router_key][0].image = images["EthernetOk"]

def load_device_models(device_type):
    try:
        with open('devices_db.json', 'r') as file:
            data = json.load(file)
        return {key: value for key, value in data.items() if value['type'] == device_type}
    except FileNotFoundError:
        print("[ERROR] JSON-filen devices_db.json blev ikke fundet.")
        return {}

def save_devices(devices):
    with open("devices_db.json", "w") as file:
        json.dump(devices, file, indent=4)

def load_recipients(file_path="emails.json"):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data.get("recipients", [])
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[ERROR] Fejl ved indlæsning af {file_path}: {e}")
        return []

def save_recipients(recipients, file_path="emails.json"):
    try:
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump({"recipients": recipients}, file, indent=4)
    except Exception as e:
        print(f"[ERROR] Fejl ved gemning af emails.json: {e}")

def modify_recipient():
    clear_window()
    tk.Label(root, text="Administrer Modtagere", font=("Arial", 18)).pack(pady=20)
    add_button = tk.Button(root, text="Tilføj Modtager", font=("Arial", 14), command=add_recipient)
    add_button.pack(pady=10)
    delete_button = tk.Button(root, text="Fjern Modtager", font=("Arial", 14), command=remove_recipient_list)
    delete_button.pack(pady=10)
    edit_button = tk.Button(root, text="Rediger Modtager", font=("Arial", 14), command=edit_recipient_list)
    edit_button.pack(pady=10)
    add_logo_to_window(root)
    tk.Button(root, text="Tilbage", font=("Arial", 14), command=show_initial_screen).pack(pady=20)

def add_recipient():
    clear_window()
    tk.Label(root, text="Tilføj Ny Modtager", font=("Arial", 18)).pack(pady=20)
    tk.Label(root, text="Navn:", font=("Arial", 14)).pack()
    name_entry = tk.Entry(root, font=("Arial", 14))
    name_entry.pack(pady=5)
    tk.Label(root, text="E-mail:", font=("Arial", 14)).pack()
    email_entry = tk.Entry(root, font=("Arial", 14))
    email_entry.pack(pady=5)
    def save_new_recipient():
        name = name_entry.get().strip()
        email = email_entry.get().strip()
        if not name or not email:
            messagebox.showerror("Fejl", "Navn og e-mail må ikke være tomme.")
            return
        recipients = load_recipients()
        recipients.append({"name": name, "email": email})
        save_recipients(recipients)
        messagebox.showinfo("Succes", "Modtager tilføjet.")
        modify_recipient()
    add_logo_to_window(root)
    tk.Button(root, text="Gem", font=("Arial", 14), command=save_new_recipient).pack(pady=20)
    tk.Button(root, text="Tilbage", font=("Arial", 14), command=modify_recipient).pack(pady=10)

def edit_recipient_list():
    clear_window()
    tk.Label(root, text="Rediger Modtager", font=("Arial", 18)).pack(pady=20)
    recipients = load_recipients()
    if not recipients:
        tk.Label(root, text="Ingen modtagere fundet.", font=("Arial", 14)).pack(pady=20)
        tk.Button(root, text="Tilbage", font=("Arial", 14), command=modify_recipient).pack(pady=10)
        return
    for recipient in recipients:
        btn = tk.Button(root, text=f"{recipient['name']} - {recipient['email']}", font=("Arial", 14),
                        command=lambda r=recipient: edit_recipient(r))
        btn.pack(pady=5)
    add_logo_to_window(root)
    tk.Button(root, text="Tilbage", font=("Arial", 14), command=modify_recipient).pack(pady=20)

def edit_recipient(recipient):
    clear_window()
    tk.Label(root, text="Rediger Modtager", font=("Arial", 18)).pack(pady=20)
    tk.Label(root, text="Navn:", font=("Arial", 14)).pack()
    name_entry = tk.Entry(root, font=("Arial", 14))
    name_entry.insert(0, recipient['name'])
    name_entry.pack(pady=5)
    tk.Label(root, text="E-mail:", font=("Arial", 14)).pack()
    email_entry = tk.Entry(root, font=("Arial", 14))
    email_entry.insert(0, recipient['email'])
    email_entry.pack(pady=5)
    def save_edited_recipient():
        new_name = name_entry.get().strip()
        new_email = email_entry.get().strip()
        if not new_name or not new_email:
            messagebox.showerror("Fejl", "Navn og e-mail må ikke være tomme.")
            return
        recipients = load_recipients()
        for r in recipients:
            if r['email'] == recipient['email']:
                r['name'] = new_name
                r['email'] = new_email
                break
        save_recipients(recipients)
        messagebox.showinfo("Succes", "Modtager opdateret.")
        modify_recipient()
    add_logo_to_window(root)
    tk.Button(root, text="Gem", font=("Arial", 14), command=save_edited_recipient).pack(pady=20)
    tk.Button(root, text="Tilbage", font=("Arial", 14), command=modify_recipient).pack(pady=10)

def remove_recipient_list():
    clear_window()
    tk.Label(root, text="Fjern Modtager", font=("Arial", 18)).pack(pady=20)
    recipients = load_recipients()
    if not recipients:
        tk.Label(root, text="Ingen modtagere fundet.", font=("Arial", 14)).pack(pady=20)
        tk.Button(root, text="Tilbage", font=("Arial", 14), command=modify_recipient).pack(pady=10)
        return
    for recipient in recipients:
        btn = tk.Button(root, text=f"{recipient['name']} - {recipient['email']}", font=("Arial", 14),
                        command=lambda r=recipient: remove_recipient(r))
        btn.pack(pady=5)
    add_logo_to_window(root)
    tk.Button(root, text="Tilbage", font=("Arial", 14), command=modify_recipient).pack(pady=20)

def remove_recipient(recipient):
    answer = messagebox.askyesno("Bekræft Sletning", f"Er du sikker på, at du vil slette '{recipient['name']}'?")
    if answer:
        recipients = load_recipients()
        recipients = [r for r in recipients if r['email'] != recipient['email']]
        save_recipients(recipients)
        messagebox.showinfo("Succes", "Modtager fjernet.")
        remove_recipient_list()
    add_logo_to_window(root)

def show_initial_screen():
    global test_running
    test_running = True
    clear_window()
    tk.Label(root, text="Vælg enhedstype", font=("Arial", 24)).pack(pady=20)
    router_btn = tk.Button(root, text="Router", font=("Arial", 18), width=15, height=3, 
                           command=lambda: show_router_selection("router"))
    modem_btn = tk.Button(root, text="Modem", font=("Arial", 18), width=15, height=3, 
                          command=lambda: show_router_selection("modem"))
    add_logo_to_window(root)
    router_btn.pack(pady=10)
    modem_btn.pack(pady=10)
    settings_button = tk.Button(root, text="⚙️ Indstillinger", font=("Arial", 14), command=open_settings)
    settings_button.place(relx=0.95, rely=0.05, anchor="ne")
    bottom_frame = tk.Frame(root)
    bottom_frame.pack(side="bottom", pady=20)
    modify_router_button = tk.Button(bottom_frame, text="Tilføj/Fjern Router", font=("Arial", 16), command=modify_router)
    modify_router_button.pack(side="left", padx=20)
    modify_recipient_button = tk.Button(bottom_frame, text="Tilføj/Fjern Modtager", font=("Arial", 16), command=modify_recipient)
    modify_recipient_button.pack(side="left", padx=20)

def show_router_selection(device_type):
    clear_window()
    tk.Label(root, text="Vælg en model", font=("Arial", 24)).pack(pady=20)
    device_models = load_device_models(device_type)
    for model in device_models.keys():
        btn = tk.Button(root, text=model, font=("Arial", 18), width=30, height=2,
                        command=lambda m=model: choose_number_of_devices(m, device_type))
        btn.pack(pady=10)
    tk.Button(root, text="Tilbage", font=("Arial", 14), command=show_initial_screen).pack(pady=20)
    add_logo_to_window(root)

def choose_number_of_devices(model_name, device_type):
    clear_window()
    tk.Label(root, text=f"Vælg antal enheder for {model_name}", font=("Arial", 24)).pack(pady=20)
    button_frame = tk.Frame(root)
    button_frame.pack()
    for i in range(1, 9):
        btn = tk.Button(button_frame, text=f"{i}", font=("Arial", 18), width=10, height=3,
                        command=lambda num=i: select_recipient(model_name, num, device_type))
        btn.grid(row=(i-1)//4, column=(i-1)%4, padx=10, pady=10)
    tk.Button(root, text="Tilbage", font=("Arial", 14), command=lambda: show_router_selection(device_type)).pack(pady=20)
    add_logo_to_window(root)

def select_device_type(action):
    clear_window()
    tk.Label(root, text="Vælg enhedstype:", font=("Arial", 18)).pack(pady=10)
    tk.Button(root, text="Router", font=("Arial", 14), command=lambda: show_device_list(action, "router")).pack(pady=10)
    tk.Button(root, text="Modem", font=("Arial", 14), command=lambda: show_device_list(action, "modem")).pack(pady=10)
    tk.Button(root, text="Tilbage", font=("Arial", 14), command=modify_router).pack(pady=20)
    add_logo_to_window(root)

def run_tests_for_device(model_name, num_devices):
    global test_running
    test_running = True
    clear_window()
    table_frame = tk.Frame(root)
    table_frame.pack(pady=20)
    global wifi_table, ethernet_table
    wifi_table, ethernet_table = {}, {}
    with open('devices_db.json', 'r') as file:
        devices_data = json.load(file)
    device_info = devices_data.get(model_name)
    for device_num in range(1, num_devices + 1):
        router_name = f"Router {device_num}"
        tk.Label(table_frame, text=router_name, font=("Arial", 16)).grid(row=(device_num-1)*2, column=0, sticky="w", padx=10, pady=10)
        wifi_frequencies = [freq for freq in ['2.4ghz', '5ghz', '6ghz'] if device_info.get(freq)]
        wifi_table[router_name] = []
        column_offset = 1
        for i, freq in enumerate(wifi_frequencies):
            tk.Label(table_frame, text=f"{freq}", font=("Arial", 10)).grid(row=(device_num-1)*2, column=column_offset, padx=5)
            wifi_label = tk.Label(table_frame, image=images["WifiWait"])
            wifi_label.grid(row=(device_num-1)*2+1, column=column_offset, padx=5)
            wifi_table[router_name].append(wifi_label)
            column_offset += 1
        ethernet_ports = device_info.get("ethernet_ports", 1)
        ethernet_table[router_name] = []
        for port in range(1, ethernet_ports + 1):
            tk.Label(table_frame, text=f"Port {port}", font=("Arial", 10)).grid(row=(device_num-1)*2, column=column_offset, padx=5)
            eth_label = tk.Label(table_frame, image=images["EthernetWait"])
            eth_label.grid(row=(device_num-1)*2+1, column=column_offset, padx=5)
            ethernet_table[router_name].append(eth_label)
            column_offset += 1
    threading.Thread(target=lambda: start_test(model_name, num_devices, recipient_email)).start()
    threading.Thread(target=monitor_results_file).start()
    add_logo_to_window(root)
    stop_button = tk.Button(root, text="Stop Test", font=("Arial", 16), command=stop_test)
    stop_button.place(relx=1.0, rely=0.0, anchor="ne")

def on_start_button_click():
    model_name = "Technicolor CGA2121"
    num_devices = 3
    recipient_email = "Rasmus.b@kadmin.dk"
    start_test(model_name, num_devices, recipient_email)

def monitor_results_file(filename="test_results.json"):
    global test_running
    def update_gui():
        try:
            with open(filename, "r") as file:
                test_data = json.load(file)
            for router in test_data:
                for model_name, results in router.items():
                    router_number = results["router_number"]
                    router_key = f"Router {router_number}"
                    wifi_results = results.get("wifi_results", {})
                    ethernet_results = results.get("ethernet_results", {})
                    update_test_statuses(router_key, wifi_results, ethernet_results)
        except FileNotFoundError:
            print(f"[ERROR] Filen '{filename}' blev ikke fundet.")
        except json.JSONDecodeError as e:
            print(f"[ERROR] Fejl i JSON-formatet: {e}")
        except Exception as e:
            print(f"[ERROR] Ukendt fejl ved læsning af JSON: {e}")
        if test_running:
            root.after(1000, update_gui)
        else:
            print("[DEBUG] Test ikke længere aktiv, stopper overvågning.")
    update_gui()

def main():
    load_images()
    show_initial_screen()
    threading.Thread(target=monitor_results_file, daemon=True).start()
    root.mainloop()

if __name__ == "__main__":
    main()
