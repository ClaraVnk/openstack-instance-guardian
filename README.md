# OpenStack Instance Guardian 👼

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54) 
![Infomaniak](https://img.shields.io/badge/infomaniak-0098FF?style=for-the-badge&logo=infomaniak&logoColor=white) 
![OpenStack](https://img.shields.io/badge/OpenStack-%23f01742.svg?style=for-the-badge&logo=openstack&logoColor=white)

Monitors multiple OpenStack instances across different Infomaniak datacenters/regions and automatically performs failover:
- If an instance goes down (error or stopped), the script launches a new backup instance in another region,
- Creates and assigns a new Floating IP in the target region (migration between regions is not supported by Infomaniak),
- Automatically updates your DNS record (Cloudflare supported, others possible),
- Gracefully shuts down the failed instance,
- Sends a notification via [Pushover](https://pushover.net/).

## Features

- Multi-instance monitoring
- Automatic region detection
- Dynamic creation of a backup instance from the original image/snapshot
- Assignment of a new Floating IP in the target region
- Automatic DNS update (Cloudflare, can be adapted for other DNS providers)
- Instant Pushover notifications
- Fully configurable via a `.env` file

## Prerequisites

- Python 3.8+
- An OpenStack account (tested with Infomaniak)
- The images/snapshots/flavors used by the original instances must be available in all target regions
- SSH keys must exist in all regions
- A new Floating IP will be created in the failover region
- Cloudflare account and API token (if you want automatic DNS updates, or adapt for another DNS provider)

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/openstack-instance-guardian.git
   cd openstack-instance-guardian
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create a `.env` file at the root of the project:**
   ```env
   # List of instance IDs to monitor (comma-separated)
   INSTANCE_IDS=xxxx-xxxx-xxxx-xxxx,yyyy-yyyy-yyyy-yyyy

   # Check frequency (in seconds)
   CHECK_INTERVAL=60

   # OpenStack credentials
   OS_AUTH_URL=https://pubcloud.infomaniak.com/identity/v3
   OS_PROJECT_ID=...
   OS_PROJECT_NAME=...
   OS_USERNAME=...
   OS_PASSWORD=...
   OS_REGION_NAME=...
   OS_USER_DOMAIN_NAME=Default
   OS_PROJECT_DOMAIN_NAME=Default

   # Pushover credentials
   PUSHOVER_USER_KEY=xxxxxx
   PUSHOVER_API_TOKEN=xxxxxx

   # Cloudflare DNS auto-update (optional, only if you want automatic DNS failover)
   CLOUDFLARE_API_TOKEN=your-api-token
   CLOUDFLARE_ZONE_ID=your-zone-id
   CLOUDFLARE_RECORD_ID=your-dns-record-id
   DNS_RECORD_NAME=your.subdomain.domain.tld
   ```

4. **(Optional) Prepare a clouds.yaml file if you prefer authentication via file.**

## Usage

Run the script:
   ```bash
   python openstack_instance_guardian.py
   ```

The script will continuously monitor the listed instances.
If a failure is detected, it will automatically launch a backup instance in another region, assign a new Floating IP, update the DNS record (if configured), and send you a Pushover notification.

## How it works

```
+--------------------+         (monitoring)
|  Primary Instance  | <-------------------+
+--------------------+                     |
        |                                   |
   [down/error]                             |
        v                                   |
+--------------------------+                |
|  Create backup instance  |                |
+--------------------------+                |
        |                                   |
   Assign new Floating IP                   |
        |                                   |
   Update DNS record (Cloudflare API)       |
        |                                   |
   Shutdown failed instance                 |
        |                                   |
 Pushover notification <-------------------+
```

## Important notes

- **Images & Snapshots:** They must be available in all regions, otherwise the creation will fail.
- **Floating IP:** Floating IPs cannot be moved between regions (Infomaniak limitation). A new IP is always created.
- **DNS auto-update:** Only supported with Cloudflare out-of-the-box, but you can adapt the script for other DNS APIs.
- **Security:** Never expose your `.env` or credentials!
- **Customization:** Adapt network/SSH logic if needed for your infrastructure.