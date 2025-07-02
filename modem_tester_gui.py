import tkinter as tk
from tkinter import messagebox, simpledialog
import speedtest
import paramiko
import time
import os
import json
import csv

MODEM_FILE = "modems.json"
RESULT_FILE = "testresultater.csv"

# --- Datahåndtering ---
def load_modems():
    if os.path.exists(MODEM_FILE):
        with open(MODEM_FILE, "r") as f:
            return json.load(f)
    return []

def save_modems(modems):
    with open(MODEM_FILE, "w") as f:
        json.dump(modems, f, indent=2)

def log_result(modem, download, upload, ping):
    file_exists = os.path.exists(RESULT_FILE)
    with open(RESULT_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Navn", "IP", "Port", "Download (Mbps)", "Upload (Mbps)", "Ping (ms)"])
        writer.writerow([modem['name'], modem['ip'], modem['port'], download, upload, ping])

# --- SSH og test ---
def ssh_enable_port(switch_ip, username, password, port):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(switch_ip, username=username, password=password)
        shell = client.invoke_shell()
        shell.send("enable\n")
        time.sleep(1)
        shell.send("configure terminal\n")
        time.sleep(1)
        shell.send(f"interface ethernet {port}\n")
        time.sleep(1)
        shell.send("no shutdown\n")
        time.sleep(1)
        shell.send("exit\nexit\n")
        client.close()
        return True
    except Exception as e:
        print(f"SSH-fejl: {e}")
        return False

def run_speedtest():
    st = speedtest.Speedtest()
    st.get_best_server()
    download = st.download() / 1_000_000
    upload = st.upload() / 1_000_000
    ping = st.results.ping
    return round(download, 2), round(upload, 2), round(ping, 2)

# --- GUI funktioner ---
def start_test():
    selected = [modems[i] for i in range(len(modems)) if var_list[i].get()]
    if not selected:
        messagebox.showwarning("Ingen valgt", "Vælg mindst ét modem.")
        return

    switch_ip = simpledialog.askstring("Switch IP", "Indtast switch IP:")
    username = simpledialog.askstring("Brugernavn", "Brugernavn:")
    password = simpledialog.askstring("Kodeord", "Kodeord:", show="*")

    for modem in selected:
        log.insert(tk.END, f"\n==> Tester {modem['name']} ({modem['ip']}) på port {modem['port']}\n")
        log.see(tk.END)
        root.update()

        success = ssh_enable_port(switch_ip, username, password, modem["port"])
        if not success:
            log.insert(tk.END, "  [FEJL] Kunne ikke aktivere port via SSH.\n")
            continue

        log.insert(tk.END, "  [OK] Port aktiveret. Venter på modem...\n")
        root.update()
        time.sleep(10)

        try:
            download, upload, ping = run_speedtest()
            log.insert(tk.END, f"  Download: {download} Mbps | Upload: {upload} Mbps | Ping: {ping} ms\n")
            log_result(modem, download, upload, ping)
        except Exception as e:
            log.insert(tk.END, f"  [FEJL] Speedtest fejlede: {e}\n")

        log.see(tk.END)
        root.update()

def refresh_gui():
    for widget in frame.winfo_children():
        widget.destroy()
    var_list.clear()

    for modem in modems:
        var = tk.IntVar()
        cb = tk.Checkbutton(frame, text=f"{modem['name']} ({modem['ip']}, Port {modem['port']})", variable=var)
        cb.pack(anchor="w")
        var_list.append(var)

def add_modem():
    name = simpledialog.askstring("Modem navn", "Navn på modem:")
    ip = simpledialog.askstring("Modem IP", "IP-adresse:")
    port = simpledialog.askstring("Switch port", "Port (fx 1/0/5):")
    if name and ip and port:
        modems.append({"name": name, "ip": ip, "port": port})
        save_modems(modems)
        refresh_gui()
        messagebox.showinfo("Tilføjet", f"{name} tilføjet.")

# --- GUI opsætning ---
root = tk.Tk()
root.title("Modem Test via Switch")

modems = load_modems()

tk.Label(root, text="Vælg modems til test:").pack()
frame = tk.Frame(root)
frame.pack()
var_list = []
refresh_gui()

btn_frame = tk.Frame(root)
btn_frame.pack(pady=10)

tk.Button(btn_frame, text="Start test", command=start_test).grid(row=0, column=0, padx=10)
tk.Button(btn_frame, text="Tilføj modem", command=add_modem).grid(row=0, column=1, padx=10)

log = tk.Text(root, height=20, width=80)
log.pack()

root.mainloop()
