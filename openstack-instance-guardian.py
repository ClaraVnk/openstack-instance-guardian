import openstack
import time
import requests
import os
from dotenv import load_dotenv

# Charge le fichier .env
load_dotenv()

INSTANCE_IDS = [id_.strip() for id_ in os.environ["INSTANCE_IDS"].split(",")]
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "60"))
PUSHOVER_USER_KEY = os.environ["PUSHOVER_USER_KEY"]
PUSHOVER_API_TOKEN = os.environ["PUSHOVER_API_TOKEN"]

# (For DNS API update; optional)
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_ZONE_ID = os.environ.get("CLOUDFLARE_ZONE_ID")
CLOUDFLARE_RECORD_ID = os.environ.get("CLOUDFLARE_RECORD_ID")
DNS_RECORD_NAME = os.environ.get("DNS_RECORD_NAME")

def pushover_notify(title, message):
    data = {
        "token": PUSHOVER_API_TOKEN,
        "user": PUSHOVER_USER_KEY,
        "title": title,
        "message": message
    }
    resp = requests.post("https://api.pushover.net/1/messages.json", data=data)
    if resp.status_code != 200:
        print("Erreur notification Pushover :", resp.text)

def get_region_param(param_name, region_name, default=None):
    env_key = f"{param_name}_{region_name}"
    return os.environ.get(env_key, default)

def get_network_id_for_region(region_name):
    env_key = f"NETWORK_ID_{region_name}"
    return os.environ.get(env_key)

def find_other_region(conn, instance):
    regions = [r.id for r in conn.identity.regions()]
    current_region = instance.location.region_name
    for r in regions:
        if r != current_region:
            return r
    return None

def get_floating_ip(conn, instance):
    for net in instance.addresses.values():
        for addr in net:
            if addr.get("OS-EXT-IPS:type") == "floating":
                return addr.get("addr")
    return None

def handle_instance(instance_id):
    try:
        conn = openstack.connect()
        instance = conn.compute.get_server(instance_id)
        state = instance.status.lower()
        print(f"[{instance.name}] Instance état: {state}")

        if state not in ("active", "building"):
            print(f"[{instance.name}] Instance down. Bascule...")
            region = instance.location.region_name
            target_region = find_other_region(conn, instance)
            if not target_region:
                print(f"[{instance.name}] Pas d'autre région trouvée !")
                return

            conn_other = openstack.connect(region_name=target_region)
            image_id = instance.image["id"]
            flavor_id = instance.flavor["id"]
            key_name = instance.key_name

            network_id = get_region_param("NETWORK_ID", target_region)
            if not network_id:
                networks = list(conn_other.network.networks())
                network_id = networks[0].id

            security_groups_str = get_region_param("SECURITY_GROUPS", target_region)
            security_groups = [sg.strip() for sg in security_groups_str.split(",")] if security_groups_str else None

            key_name = get_region_param("KEYPAIR", target_region, key_name)  

            create_server_kwargs = {
                "name": f"Relais_{instance.name}",
                "image_id": image_id,
                "flavor_id": flavor_id,
                "networks": [{"uuid": network_id}],
                "key_name": key_name,
            }
            if security_groups:
                create_server_kwargs["security_groups"] = security_groups

            new_server = conn_other.compute.create_server(**create_server_kwargs)

            conn_other.compute.wait_for_server(new_server, status="ACTIVE", failures=["ERROR"], interval=5, wait=300)

            # Floating IPs cannot be migrated between regions on Infomaniak.
            # A new Floating IP will be created and attached in the target region.
            new_fip = conn_other.network.create_ip()
            conn_other.compute.add_floating_ip_to_server(new_server.id, new_fip.floating_ip_address)
            print(f"[{instance.name}] New Floating IP assigned: {new_fip.floating_ip_address}")

            # === BONUS : DNS AUTOMATIC UPDATE SECTION ===
            # Example: update a DNS A record via Cloudflare API (adapt to your DNS provider)
            def update_cloudflare_dns(ip_address):
                if not all([CLOUDFLARE_API_TOKEN, CLOUDFLARE_ZONE_ID, CLOUDFLARE_RECORD_ID, DNS_RECORD_NAME]):
                    print("[DNS] Cloudflare env vars not set, skipping DNS update.")
                    return False
                url = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records/{CLOUDFLARE_RECORD_ID}"
                headers = {
                    "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
                    "Content-Type": "application/json",
                }
                data = {
                    "type": "A",
                    "name": DNS_RECORD_NAME,
                    "content": ip_address,
                    "ttl": 60,
                    "proxied": False,
                }
                resp = requests.put(url, headers=headers, json=data)
                if resp.status_code == 200 and resp.json().get("success"):
                    print(f"[DNS] DNS record updated to {ip_address}")
                    return True
                else:
                    print(f"[DNS] Failed to update DNS: {resp.text}")
                    return False

            update_cloudflare_dns(new_fip.floating_ip_address)
            # === END DNS AUTOMATIC UPDATE SECTION ===

            try:
                conn.compute.stop_server(instance_id)
            except Exception as e:
                print(f"[{instance.name}] Erreur arrêt instance :", e)

            pushover_notify(
                f"Bascule OpenStack [{instance.name}]",
                f"Instance {instance.name} ({region}) DOWN → New instance started in {target_region} ({new_server.id})\nNew Floating IP: {new_fip.floating_ip_address}\n(DNS record updated automatically)"
            )
            print(f"[{instance.name}] Bascule et notification faites.")
        else:
            print(f"[{instance.name}] Instance OK.")
    except Exception as exc:
        print(f"[{instance_id}] Erreur script :", exc)

if __name__ == "__main__":
    while True:
        for instance_id in INSTANCE_IDS:
            handle_instance(instance_id)
        time.sleep(CHECK_INTERVAL)