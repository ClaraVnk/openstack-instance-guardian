# OpenStack Instance Guardian 👼

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54) 
![Infomaniak](https://img.shields.io/badge/infomaniak-0098FF?style=for-the-badge&logo=infomaniak&logoColor=white) 
![OpenStack](https://img.shields.io/badge/OpenStack-%23f01742.svg?style=for-the-badge&logo=openstack&logoColor=white)

Monitors multiple OpenStack instances across different Infomaniak datacenters/regions and automatically performs failover:
- If an instance goes down (error or stopped), the script launches a new backup instance in another region,
- Automatically assigns the Floating IP to the new instance,
- Gracefully shuts down the failed instance,
- Sends a notification via [Pushover](https://pushover.net/).

## Features

- Multi-instance monitoring
- Automatic region detection
- Dynamic creation of a backup instance from the original image/snapshot
- Floating IP migration
- Instant Pushover notifications
- Fully configurable via a `.env` file

## Prerequisites

- Python 3.8+
- An OpenStack account (tested with Infomaniak)
- The images/snapshots/flavors used by the original instances must be available in all target regions
- SSH keys must exist in all regions
- Floating IPs must be valid and portable between regions

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/openstack-ha-failover.git
   cd openstack-ha-failover

2. **Install dependencies:**
       ```bash
   pip install -r requirements.txt
(adapt if you want to provide the requirements.txt)

3. **Create a .env file at the root of the project:**
    ```bash
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

4.	**(Optional) Prepare a clouds.yaml file if you prefer authentication via file.**

## Usage

Run the script:
    ```bash
    python openstack_ha_failover.py

The script will continuously monitor the listed instances.
If a failure is detected, it will automatically launch a backup instance in another region, reassign the floating IP, and send you a Pushover notification.

## How it works

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
   Assign Floating IP                      |
        |                                   |
   Shutdown failed instance                 |
        |                                   |
 Pushover notification <-------------------+

 ## Important notes

	•	Images & Snapshots: They must be available in all regions, otherwise the creation will fail.
	•	Floating IP: IP migration assumes your public IP can be moved between regions on your cloud provider.
	•	Security: Never expose your .env or credentials!
	•	Customization: Adapt network/SSH logic if needed for your infrastructure.