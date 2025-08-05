import requests
from colorama import Fore, Style, init
import os
import time
import concurrent.futures
from threading import Lock
from fake_useragent import UserAgent
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed

# ========================
# CONFIGURATION VARIABLES (moved to top)
# ========================
# Proxy settings
PROXY_SOURCES = {
    "http": [
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-https.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/archive/txt/proxies-https.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/archive/txt/proxies-http.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://www.proxy-list.download/api/v1/get?type=http",
        "https://www.proxy-list.download/api/v1/get?type=https",
        "https://www.proxyscan.io/download?type=http",
        "https://www.proxyscan.io/download?type=https",
        "https://api.openproxylist.xyz/http.txt"
    ],
    "socks4": [
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks4.txt",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks4&timeout=10000&country=all",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/archive/txt/proxies-socks4.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS4_RAW.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
        "https://www.proxy-list.download/api/v1/get?type=socks4",
        "https://www.proxyscan.io/download?type=socks4",
        "https://api.openproxylist.xyz/socks4.txt"
    ],
    "socks5": [
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=10000&country=all",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/archive/txt/proxies-socks5.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt",
        "https://github.com/jetkai/proxy-list/blob/main/archive/txt/proxies-socks5.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        "https://www.proxy-list.download/api/v1/get?type=socks5",
        "https://api.openproxylist.xyz/socks5.txt"
    ]
}

# Files
input_file = "raw_proxies.txt"
output_file = "proxies_active.txt"
temp_file = "temp_active_proxies.txt"

# Test parameters
test_url = "http://httpbin.org/ip"
max_threads = 100  # Maximum number of threads
request_timeout = 10 # Request timeout for speed
socket_timeout = 1 # Fast socket check timeout
batch_size = 50  # Batch size for saving

# ========================
# INITIALIZATION
# ========================
init()
ua = UserAgent()
headers = {
    'User-Agent': ua.random,
    'Connection': 'close',
    'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-US,en;q=0.9'
}

# ========================
# GLOBAL COUNTERS AND LOCKS
# ========================
total_checked = 0
total_active = 0
start_time = None
stats_lock = Lock()
active_proxies_lock = Lock()
active_proxies = []

# ========================
# FUNCTIONS
# ========================

def clear_terminal():
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')

def read_proxies(file_path):
    with open(file_path, "r") as file:
        proxies = file.read().splitlines()
    return proxies

def fetch_proxies_from_all_sources():
    all_proxies = []
    for proxy_type, urls in PROXY_SOURCES.items():
        print(f"Fetching {proxy_type} proxies...")
        for url in urls:
            try:
                response = requests.get(url, timeout=request_timeout, headers=headers)
                if response.status_code == 200:
                    proxies = response.text.splitlines()
                    for proxy in proxies:
                        if proxy.strip():
                            all_proxies.append(f"{proxy_type}://{proxy.strip()}")
                    print(Fore.GREEN + f"✓ {len(proxies)} {proxy_type} proxies from {url}" + Style.RESET_ALL)
                else:
                    print(Fore.YELLOW + f"⚠ Failed to fetch from {url} (Status: {response.status_code})" + Style.RESET_ALL)
            except Exception as e:
                print(Fore.RED + f"✗ Error fetching from {url}: {str(e)}" + Style.RESET_ALL)
    unique_proxies = list(set(all_proxies))
    print(Fore.CYAN + f"Total unique proxies collected: {len(unique_proxies)}" + Style.RESET_ALL)
    return unique_proxies

def test_proxy_socket(proxy_address, proxy_type):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(socket_timeout)
        if ":" in proxy_address:
            host, port = proxy_address.split(":")
            port = int(port)
        else:
            host = proxy_address
            port = 80
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False

def test_proxy_http(proxy_address, proxy_type):
    try:
        proxies = {}
        if proxy_type == "http":
            proxies = {"http": f"http://{proxy_address}", "https": f"http://{proxy_address}"}
        elif proxy_type == "socks4":
            proxies = {"http": f"socks4://{proxy_address}", "https": f"socks4://{proxy_address}"}
        elif proxy_type == "socks5":
            proxies = {"http": f"socks5://{proxy_address}", "https": f"socks5://{proxy_address}"}
        response = requests.get(test_url, proxies=proxies, timeout=request_timeout, headers=headers)
        return response.status_code == 200
    except:
        return False

def save_active_proxies(active_proxies, output_file):
    with open(output_file, "w") as file:
        for proxy_type, proxy_address in active_proxies:
            file.write(f"{proxy_type}://{proxy_address}\n")

def save_temp_proxies(proxy_data):
    with open(temp_file, "a") as file:
        proxy_type, proxy_address = proxy_data
        file.write(f"{proxy_type}://{proxy_address}\n")

def update_stats(is_active=False):
    global total_checked, total_active
    with stats_lock:
        total_checked += 1
        if is_active:
            total_active += 1
        if total_checked % 1000 == 0:
            elapsed_time = time.time() - start_time
            speed = total_checked / elapsed_time if elapsed_time > 0 else 0
            print(f"\r{Fore.CYAN}Checked: {total_checked:,} | Active: {total_active:,} | Speed: {speed:.1f} proxy/sec{Style.RESET_ALL}", end="", flush=True)

def check_single_proxy(proxy):
    global active_proxies
    if "://" in proxy:
        proxy_type, proxy_address = proxy.split("://")
    else:
        proxy_type = "http"
        proxy_address = proxy
    
    # Step 1: Fast socket check (port open?)
    if test_proxy_socket(proxy_address, proxy_type):
        # Step 2: If socket passed, check HTTP
        if test_proxy_http(proxy_address, proxy_type):
            with active_proxies_lock:
                active_proxies.append((proxy_type, proxy_address))
                if len(active_proxies) % batch_size == 0:
                    save_temp_proxies((proxy_type, proxy_address))
            update_stats(is_active=True)
        else:
            update_stats(is_active=False)
    else:
        update_stats(is_active=False)

def check_proxies(proxies_list):
    global start_time, total_checked, total_active, active_proxies
    start_time = time.time()
    total_checked = 0
    total_active = 0
    active_proxies = []
    
    print(f"{Fore.YELLOW}Starting proxy check with {len(proxies_list):,} proxies...{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Configuration: {max_threads:,} concurrent threads{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Logic: Socket check ({socket_timeout}s) → HTTP check ({request_timeout}s){Style.RESET_ALL}")
    print(f"{Fore.CYAN}Expected speed: ~{max_threads / (socket_timeout + request_timeout):.0f} proxy/sec{Style.RESET_ALL}\n")
    
    with ThreadPoolExecutor(max_threads=max_threads) as executor:
        futures = [executor.submit(check_single_proxy, proxy) for proxy in proxies_list]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                pass
    
    elapsed_time = time.time() - start_time
    final_speed = total_checked / elapsed_time if elapsed_time > 0 else 0
    
    print(f"\n{Fore.GREEN}=== FINAL STATISTICS ==={Style.RESET_ALL}")
    print(f"{Fore.CYAN}Total checked: {total_checked:,}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}Total active: {total_active:,}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Success rate: {(total_active/total_checked*100):.2f}%{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Total time: {elapsed_time:.2f} seconds{Style.RESET_ALL}")
    print(f"{Fore.GREEN}Average speed: {final_speed:.1f} proxy/sec{Style.RESET_ALL}")
    
    if active_proxies:
        print(f"\n{Fore.GREEN}=== ACTIVE PROXIES FOUND ==={Style.RESET_ALL}")
        for i, (proxy_type, proxy_address) in enumerate(active_proxies[:10], 1):
            print(f"{i}. {proxy_type}://{proxy_address}")
        if len(active_proxies) > 10:
            print(f"... and {len(active_proxies) - 10} more")
    
    save_active_proxies(active_proxies, output_file)
    print(f"\n{Fore.GREEN}Active proxies saved to {output_file}{Style.RESET_ALL}")

def main():
    clear_terminal()
    print(Fore.CYAN + """
░██                                                     
░██                                                     
░██         ░██    ░██ ░██    ░██ ░████████   ░███████  
░██         ░██    ░██ ░██    ░██ ░██    ░██ ░██        
░██         ░██    ░██ ░██    ░██ ░██    ░██  ░███████  
░██         ░██   ░███ ░██   ░███ ░███   ░██        ░██ 
░██████████  ░█████░██  ░█████░██ ░██░█████   ░███████  
                   ░██            ░██                   
             ░███████             ░██""" + Fore.YELLOW + """  Proxy Parser and Checker v0.1 (MAY BE BUGS)""" + Style.RESET_ALL + """
""")
    print(f"{Fore.CYAN}NOW: {max_threads:,} concurrent threads{Style.RESET_ALL}")
    print("Select mode:")
    print("1. Get proxies from list and save to raw_proxies.txt")
    print("2. Check proxies from raw_proxies.txt")
    print("3. Get proxies from list and check immediately")
    mode = input("Enter mode (1/2/3): ")
    proxies_list = []
    
    if mode == "1":
        print("Fetching proxies from list and saving...")
        proxies_list = fetch_proxies_from_all_sources()
        if proxies_list:
            with open(input_file, "w") as f:
                for proxy in proxies_list:
                    f.write(proxy + "\n")
            print(Fore.GREEN + f"Successfully saved {len(proxies_list)} proxies to {input_file}" + Style.RESET_ALL)
        else:
            print(Fore.RED + "No proxies fetched from list." + Style.RESET_ALL)
        return
    elif mode == "2":
        print("Reading proxies from raw_proxies.txt and checking...")
        try:
            proxies_list = read_proxies(input_file)
        except FileNotFoundError:
            print(Fore.RED + f"File {input_file} not found! Please run mode 1 first." + Style.RESET_ALL)
            return
    elif mode == "3":
        print("Fetching proxies from list and checking immediately...")
        proxies_list = fetch_proxies_from_all_sources()
    else:
        print(Fore.RED + "Invalid mode selected" + Style.RESET_ALL)
        return
    
    if proxies_list:
        check_proxies(proxies_list)
    else:
        print(Fore.RED + "No proxies to check" + Style.RESET_ALL)

if __name__ == "__main__":
    main()