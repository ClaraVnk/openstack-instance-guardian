import logging
import os
import sys
import time
from typing import Optional

import openstack
import requests
from dotenv import load_dotenv

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("openstack-guardian.log"),
    ],
)
logger = logging.getLogger("OpenStackGuardian")

# Charge le fichier .env
load_dotenv()


def validate_env_vars():
    """Valide que toutes les variables d'environnement requises sont présentes."""
    required_vars = ["INSTANCE_IDS", "PUSHOVER_USER_KEY", "PUSHOVER_API_TOKEN"]

    missing_vars = [var for var in required_vars if not os.environ.get(var)]

    if missing_vars:
        logger.error(f"Variables d'environnement manquantes: {', '.join(missing_vars)}")
        sys.exit(1)

    # Validation des INSTANCE_IDS
    try:
        instance_ids = [id_.strip() for id_ in os.environ["INSTANCE_IDS"].split(",")]
        if not instance_ids or any(not id_ for id_ in instance_ids):
            raise ValueError("INSTANCE_IDS ne peut pas être vide")
        logger.info(f"Surveillance de {len(instance_ids)} instance(s)")
    except Exception as e:
        logger.error(f"Erreur validation INSTANCE_IDS: {e}")
        sys.exit(1)

    # Validation CHECK_INTERVAL
    try:
        check_interval = int(os.environ.get("CHECK_INTERVAL", "60"))
        if check_interval < 10:
            logger.warning("CHECK_INTERVAL < 10s, utilisation de 10s minimum")
            check_interval = 10
    except ValueError:
        logger.error("CHECK_INTERVAL doit être un entier")
        sys.exit(1)


validate_env_vars()

INSTANCE_IDS = [id_.strip() for id_ in os.environ["INSTANCE_IDS"].split(",")]
CHECK_INTERVAL = max(10, int(os.environ.get("CHECK_INTERVAL", "60")))
PUSHOVER_USER_KEY = os.environ["PUSHOVER_USER_KEY"]
PUSHOVER_API_TOKEN = os.environ["PUSHOVER_API_TOKEN"]

# (For DNS API update; optional)
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_ZONE_ID = os.environ.get("CLOUDFLARE_ZONE_ID")
CLOUDFLARE_RECORD_ID = os.environ.get("CLOUDFLARE_RECORD_ID")
DNS_RECORD_NAME = os.environ.get("DNS_RECORD_NAME")

# Cache de connexions OpenStack
_openstack_connections = {}


def pushover_notify(title: str, message: str, priority: int = 0) -> bool:
    """Envoie une notification Pushover.

    Args:
        title: Titre de la notification
        message: Message de la notification
        priority: Priorité (-2 à 2, défaut 0)

    Returns:
        True si succès, False sinon
    """
    try:
        data = {
            "token": PUSHOVER_API_TOKEN,
            "user": PUSHOVER_USER_KEY,
            "title": title,
            "message": message,
            "priority": priority,
        }
        resp = requests.post(
            "https://api.pushover.net/1/messages.json", data=data, timeout=10
        )
        if resp.status_code == 200:
            logger.info(f"Notification Pushover envoyée: {title}")
            return True
        else:
            logger.error(
                f"Erreur notification Pushover ({resp.status_code}): {resp.text}"
            )
            return False
    except Exception as e:
        logger.error(f"Exception lors de l'envoi Pushover: {e}")
        return False


def get_openstack_connection(region_name: Optional[str] = None):
    """Obtient ou crée une connexion OpenStack avec cache.

    Args:
        region_name: Nom de la région (None pour région par défaut)

    Returns:
        Connexion OpenStack
    """
    cache_key = region_name or "default"

    if cache_key not in _openstack_connections:
        try:
            if region_name:
                logger.debug(f"Création connexion OpenStack pour région: {region_name}")
                _openstack_connections[cache_key] = openstack.connect(
                    region_name=region_name
                )
            else:
                logger.debug("Création connexion OpenStack par défaut")
                _openstack_connections[cache_key] = openstack.connect()
        except Exception as e:
            logger.error(f"Erreur création connexion OpenStack ({cache_key}): {e}")
            raise

    return _openstack_connections[cache_key]


def get_region_param(
    param_name: str, region_name: str, default: Optional[str] = None
) -> Optional[str]:
    """Récupère un paramètre spécifique à une région."""
    env_key = f"{param_name}_{region_name}"
    return os.environ.get(env_key, default)


def get_network_id_for_region(region_name: str) -> Optional[str]:
    """Récupère l'ID réseau pour une région."""
    env_key = f"NETWORK_ID_{region_name}"
    return os.environ.get(env_key)


def find_other_region(conn, instance) -> Optional[str]:
    """Trouve une région différente de celle de l'instance.

    Args:
        conn: Connexion OpenStack
        instance: Instance OpenStack

    Returns:
        Nom de la région cible ou None
    """
    try:
        regions = [r.id for r in conn.identity.regions()]
        current_region = instance.location.region_name
        logger.debug(
            f"Régions disponibles: {regions}, région actuelle: {current_region}"
        )

        for r in regions:
            if r != current_region:
                logger.info(f"Région cible sélectionnée: {r}")
                return r

        logger.warning("Aucune autre région disponible")
        return None
    except Exception as e:
        logger.error(f"Erreur lors de la recherche de région: {e}")
        return None


def get_floating_ip(conn, instance) -> Optional[str]:
    """Récupère l'IP flottante d'une instance.

    Args:
        conn: Connexion OpenStack
        instance: Instance OpenStack

    Returns:
        Adresse IP flottante ou None
    """
    try:
        for net in instance.addresses.values():
            for addr in net:
                if addr.get("OS-EXT-IPS:type") == "floating":
                    return addr.get("addr")
        return None
    except Exception as e:
        logger.error(f"Erreur récupération IP flottante: {e}")
        return None


def update_cloudflare_dns(ip_address: str) -> bool:
    """Met à jour un enregistrement DNS Cloudflare.

    Args:
        ip_address: Nouvelle adresse IP

    Returns:
        True si succès, False sinon
    """
    if not all(
        [
            CLOUDFLARE_API_TOKEN,
            CLOUDFLARE_ZONE_ID,
            CLOUDFLARE_RECORD_ID,
            DNS_RECORD_NAME,
        ]
    ):
        logger.info("Variables Cloudflare non configurées, mise à jour DNS ignorée")
        return False

    try:
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
        resp = requests.put(url, headers=headers, json=data, timeout=10)

        if resp.status_code == 200 and resp.json().get("success"):
            logger.info(
                f"Enregistrement DNS mis à jour: {DNS_RECORD_NAME} -> {ip_address}"
            )
            return True
        else:
            logger.error(f"Échec mise à jour DNS ({resp.status_code}): {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Exception lors de la mise à jour DNS: {e}")
        return False


def handle_instance(instance_id: str) -> None:
    """Gère la surveillance et le basculement d'une instance.

    Args:
        instance_id: ID de l'instance à surveiller
    """
    instance_name = instance_id  # Fallback si on ne peut pas récupérer le nom

    try:
        conn = get_openstack_connection()
        instance = conn.compute.get_server(instance_id)

        if not instance:
            logger.error(f"Instance {instance_id} introuvable")
            pushover_notify(
                "Erreur OpenStack Guardian",
                f"Instance {instance_id} introuvable",
                priority=1,
            )
            return

        instance_name = instance.name
        state = instance.status.lower()
        logger.info(f"[{instance_name}] État: {state}")

        if state not in ("active", "building"):
            logger.warning(
                f"[{instance_name}] Instance DOWN (état: {state}). Démarrage basculement..."
            )
            region = instance.location.region_name

            target_region = find_other_region(conn, instance)
            if not target_region:
                error_msg = f"[{instance_name}] Aucune région cible disponible pour le basculement"
                logger.error(error_msg)
                pushover_notify(
                    f"Échec basculement [{instance_name}]", error_msg, priority=1
                )
                return

            try:
                conn_other = get_openstack_connection(region_name=target_region)
                image_id = instance.image["id"]
                flavor_id = instance.flavor["id"]
                key_name = instance.key_name

                # Configuration réseau
                network_id = get_region_param("NETWORK_ID", target_region)
                if not network_id:
                    logger.warning(
                        f"NETWORK_ID non configuré pour {target_region}, utilisation du réseau par défaut"
                    )
                    networks = list(conn_other.network.networks())
                    if not networks:
                        raise Exception(f"Aucun réseau disponible dans {target_region}")
                    network_id = networks[0].id
                    logger.info(f"Réseau par défaut sélectionné: {network_id}")

                security_groups_str = get_region_param("SECURITY_GROUPS", target_region)
                security_groups = (
                    [sg.strip() for sg in security_groups_str.split(",")]
                    if security_groups_str
                    else None
                )

                key_name = get_region_param("KEYPAIR", target_region, key_name)
                logger.info(
                    f"Configuration: network={network_id}, keypair={key_name}, security_groups={security_groups}"
                )

                # Création du serveur de secours
                create_server_kwargs = {
                    "name": f"Relais_{instance.name}",
                    "image_id": image_id,
                    "flavor_id": flavor_id,
                    "networks": [{"uuid": network_id}],
                    "key_name": key_name,
                }
                if security_groups:
                    create_server_kwargs["security_groups"] = security_groups

                logger.info(
                    f"[{instance_name}] Création serveur de secours dans {target_region}..."
                )
                new_server = conn_other.compute.create_server(**create_server_kwargs)
                logger.info(
                    f"[{instance_name}] Serveur créé: {new_server.id}, attente activation..."
                )

                conn_other.compute.wait_for_server(
                    new_server,
                    status="ACTIVE",
                    failures=["ERROR"],
                    interval=5,
                    wait=300,
                )
                logger.info(f"[{instance_name}] Serveur actif")

                # Attribution d'une nouvelle IP flottante
                logger.info(
                    f"[{instance_name}] Création et attribution IP flottante..."
                )
                new_fip = conn_other.network.create_ip()
                conn_other.compute.add_floating_ip_to_server(
                    new_server.id, new_fip.floating_ip_address
                )
                logger.info(
                    f"[{instance_name}] IP flottante attribuée: {new_fip.floating_ip_address}"
                )

                # Mise à jour DNS
                dns_updated = update_cloudflare_dns(new_fip.floating_ip_address)
                dns_status = "DNS mis à jour" if dns_updated else "DNS non mis à jour"

                # Arrêt de l'instance défaillante
                try:
                    logger.info(f"[{instance_name}] Arrêt de l'instance défaillante...")
                    conn.compute.stop_server(instance_id)
                    logger.info(f"[{instance_name}] Instance défaillante arrêtée")
                except Exception as e:
                    logger.error(
                        f"[{instance_name}] Erreur lors de l'arrêt de l'instance: {e}"
                    )

                # Notification de succès
                success_msg = (
                    f"Instance {instance_name} ({region}) DOWN\n"
                    f"→ Nouveau serveur démarré dans {target_region}\n"
                    f"ID: {new_server.id}\n"
                    f"IP flottante: {new_fip.floating_ip_address}\n"
                    f"{dns_status}"
                )
                pushover_notify(
                    f"✓ Basculement réussi [{instance_name}]", success_msg, priority=1
                )
                logger.info(f"[{instance_name}] Basculement terminé avec succès")

            except Exception as e:
                error_msg = f"Erreur lors du basculement: {str(e)}"
                logger.error(f"[{instance_name}] {error_msg}", exc_info=True)
                pushover_notify(
                    f"✗ Échec basculement [{instance_name}]",
                    f"{error_msg}\nRégion source: {region}\nRégion cible: {target_region}",
                    priority=1,
                )
                raise
        else:
            logger.debug(f"[{instance_name}] Instance opérationnelle")

    except openstack.exceptions.ResourceNotFound:
        logger.error(f"[{instance_name}] Instance non trouvée: {instance_id}")
        pushover_notify(
            "Erreur OpenStack Guardian",
            f"Instance {instance_id} non trouvée",
            priority=1,
        )
    except openstack.exceptions.HttpException as e:
        logger.error(f"[{instance_name}] Erreur HTTP OpenStack: {e}", exc_info=True)
        pushover_notify(
            f"Erreur OpenStack [{instance_name}]", f"Erreur HTTP: {str(e)}", priority=1
        )
    except Exception as e:
        logger.error(f"[{instance_name}] Erreur inattendue: {e}", exc_info=True)
        pushover_notify(
            f"Erreur critique [{instance_name}]", f"Erreur: {str(e)}", priority=1
        )


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Démarrage OpenStack Instance Guardian")
    logger.info(f"Surveillance de {len(INSTANCE_IDS)} instance(s)")
    logger.info(f"Intervalle de vérification: {CHECK_INTERVAL}s")
    logger.info("=" * 60)

    pushover_notify(
        "OpenStack Guardian démarré",
        f"Surveillance de {len(INSTANCE_IDS)} instance(s)\nIntervalle: {CHECK_INTERVAL}s",
    )

    try:
        while True:
            for instance_id in INSTANCE_IDS:
                try:
                    handle_instance(instance_id)
                except Exception as e:
                    logger.error(
                        f"Erreur non gérée pour {instance_id}: {e}", exc_info=True
                    )

            logger.debug(f"Attente de {CHECK_INTERVAL}s avant prochaine vérification")
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        logger.info("Arrêt demandé par l'utilisateur")
        pushover_notify("OpenStack Guardian arrêté", "Service arrêté manuellement")
    except Exception as e:
        logger.critical(f"Erreur critique, arrêt du service: {e}", exc_info=True)
        pushover_notify(
            "OpenStack Guardian CRASH", f"Erreur critique: {str(e)}", priority=2
        )
        sys.exit(1)
