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

            networks = list(conn_other.network.networks())
            network_id = networks[0].id

            new_server = conn_other.compute.create_server(
                name=f"Relais_{instance.name}",
                image_id=image_id,
                flavor_id=flavor_id,
                networks=[{"uuid": network_id}],
                key_name=key_name,
            )

            conn_other.compute.wait_for_server(new_server, status="ACTIVE", failures=["ERROR"], interval=5, wait=300)

            floating_ip = get_floating_ip(conn, instance)
            if floating_ip:
                try:
                    conn.compute.remove_floating_ip_from_server(instance_id, floating_ip)
                except Exception as e:
                    print(f"[{instance.name}] Erreur détachement floating IP :", e)
                try:
                    conn_other.compute.add_floating_ip_to_server(new_server.id, floating_ip)
                except Exception as e:
                    print(f"[{instance.name}] Erreur attachement floating IP :", e)
            else:
                print(f"[{instance.name}] Aucune floating IP trouvée à migrer.")

            try:
                conn.compute.stop_server(instance_id)
            except Exception as e:
                print(f"[{instance.name}] Erreur arrêt instance :", e)

            pushover_notify(
                f"Bascule OpenStack [{instance.name}]",
                f"Instance {instance.name} ({region}) DOWN → Nouvelle instance démarrée sur {target_region} ({new_server.id})\nFloating IP migrée : {floating_ip or 'non'}"
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