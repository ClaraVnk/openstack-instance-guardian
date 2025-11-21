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

- **Multi-instance monitoring** with concurrent support
- **Automatic region detection** and failover
- **Dynamic creation** of a backup instance from the original image/snapshot
- **Assignment of a new Floating IP** in the target region
- **Automatic DNS update** (Cloudflare, can be adapted for other DNS providers)
- **Instant Pushover notifications** with priority levels
- **Structured logging** to file and console
- **Environment variables validation** at startup
- **Connection pooling** for OpenStack API (performance optimization)
- **Enhanced error handling** with detailed notifications
- **Fully configurable** via a `.env` file

## Prerequisites

- **Python 3.8+** (tested with 3.11+)
- **Dependencies**:
  - `openstacksdk>=1.3.0` - OpenStack cloud management
  - `python-dotenv>=1.0.0` - Environment variables
  - `requests>=2.31.0` - HTTP requests (Pushover, Cloudflare)
- **OpenStack account** (tested with Infomaniak)
- The images/snapshots/flavors used by the original instances must be available in all target regions
- SSH keys must exist in all regions
- A new Floating IP will be created in the failover region
- **Pushover account** for notifications
- **Cloudflare account** (optional, for automatic DNS updates)

## Installation

### Option 1: Docker (Recommended)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ClaraVnk/openstack-instance-guardian.git
   cd openstack-instance-guardian
   ```

2. **Create a `.env` file at the root of the project:**
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

3. **Run with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

4. **Check logs:**
   ```bash
   docker-compose logs -f
   ```

5. **Stop the container:**
   ```bash
   docker-compose down
   ```

**Using pre-built image from GitHub Container Registry:**
```bash
docker run -d \
  --name openstack-guardian \
  --env-file .env \
  -v $(pwd)/logs:/logs \
  --restart unless-stopped \
  ghcr.io/claravnk/openstack-instance-guardian:latest
```

### Option 2: Manual Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ClaraVnk/openstack-instance-guardian.git
   cd openstack-instance-guardian
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create a `.env` file** (same as Docker option above)

4. **Run the script:**
   ```bash
   python openstack-instance-guardian.py
   ```

## Usage

The script will:
- Validate all required environment variables at startup
- Send a Pushover notification confirming the service has started
- Continuously monitor the listed instances
- Log all activities to `openstack-guardian.log` and console
- If a failure is detected, automatically launch a backup instance in another region
- Assign a new Floating IP and update DNS records (if configured)
- Send detailed Pushover notifications for all events (success, errors, warnings)

### Logs

The script generates structured logs in two places:
- **Console output**: Real-time monitoring information
- **Log file** (`openstack-guardian.log`): Complete history with timestamps

Log levels:
- `INFO`: Normal operations (instance checks, successful failovers)
- `WARNING`: Non-critical issues (missing optional config)
- `ERROR`: Failures that don't stop the service
- `CRITICAL`: Fatal errors requiring intervention

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

## Docker & CI/CD

### Docker Image

The project includes a multi-stage Dockerfile optimized for production:
- **Base image**: Python 3.11-slim
- **Non-root user**: Runs as user `guardian` (UID 1000)
- **Multi-architecture**: Supports `linux/amd64` and `linux/arm64`
- **Healthcheck**: Automatic container health monitoring
- **Volume**: `/logs` for persistent log storage

### GitHub Actions Workflow

The repository includes a GitHub Actions workflow (`.github/workflows/docker-build.yml`) that automatically:
- **Builds** the Docker image on every push to main/master
- **Tags** images with:
  - `latest` for the default branch
  - Semantic version tags (e.g., `v1.0.0`, `1.0`, `1`)
  - Branch names for feature branches
  - SHA for specific commits
- **Publishes** to GitHub Container Registry (`ghcr.io`)
- **Supports** multi-platform builds (amd64, arm64)
- **Caches** layers for faster builds

### Pulling the Image

```bash
# Latest version
docker pull ghcr.io/claravnk/openstack-instance-guardian:latest

# Specific version
docker pull ghcr.io/claravnk/openstack-instance-guardian:v2.0.0
```

### Building Locally

```bash
# Simple build
docker build -t openstack-guardian:local .

# Multi-platform build
docker buildx build --platform linux/amd64,linux/arm64 -t openstack-guardian:multiarch .
```

### Resource Limits

The `docker-compose.yml` includes resource limits:
- **CPU**: 0.5 cores max, 0.1 cores reserved
- **Memory**: 256MB max, 128MB reserved

Adjust in `docker-compose.yml` or use `docker run` flags:
```bash
docker run -d --cpus="0.5" --memory="256m" ...
```

### Healthcheck

Check container health:
```bash
docker inspect --format='{{.State.Health.Status}}' openstack-guardian
```

States: `starting`, `healthy`, `unhealthy`

### Production Deployment

**Systemd service** (Linux):
```bash
# Create /etc/systemd/system/openstack-guardian.service
[Unit]
Description=OpenStack Instance Guardian
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/openstack-guardian
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl enable openstack-guardian
sudo systemctl start openstack-guardian
```

### Updating

```bash
# With docker-compose
docker-compose pull
docker-compose up -d

# With docker run
docker pull ghcr.io/claravnk/openstack-instance-guardian:latest
docker stop openstack-guardian && docker rm openstack-guardian
docker run -d --name openstack-guardian --env-file .env -v $(pwd)/logs:/logs --restart unless-stopped ghcr.io/claravnk/openstack-instance-guardian:latest
```

## Troubleshooting

### Container exits immediately
Check logs: `docker logs openstack-guardian`

Common issues:
- Missing required environment variables
- Invalid INSTANCE_IDS format
- Incorrect OpenStack credentials

### Cannot connect to OpenStack
1. Verify credentials in `.env`
2. Test network: `docker exec openstack-guardian ping -c 3 pubcloud.infomaniak.com`
3. Check OpenStack API accessibility

### Logs not persisting
Ensure logs directory exists:
```bash
mkdir -p logs
chmod 755 logs
```

### High memory usage
Monitor: `docker stats openstack-guardian`

Adjust limits in `docker-compose.yml` if needed.

## Important notes

- **Images & Snapshots:** They must be available in all regions, otherwise the creation will fail.
- **Floating IP:** Floating IPs cannot be moved between regions (Infomaniak limitation). A new IP is always created.
- **DNS auto-update:** Only supported with Cloudflare out-of-the-box, but you can adapt the script for other DNS APIs.
- **Security:** 
  - Never expose your `.env` or credentials!
  - A `.gitignore` file is included to protect sensitive files
  - Logs may contain instance IDs and IPs - secure the log file appropriately
- **Error handling:** All errors trigger Pushover notifications with appropriate priority levels
- **Connection pooling:** OpenStack connections are cached for better performance
- **Customization:** Adapt network/SSH logic if needed for your infrastructure.

## Project Structure

```
openstack-instance-guardian/
├── .github/
│   └── workflows/
│       └── docker-build.yml      # CI/CD workflow for Docker builds
├── openstack-instance-guardian.py # Main application
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment variables template
├── Dockerfile                     # Multi-stage Docker image
├── docker-compose.yml             # Docker Compose configuration
├── .dockerignore                  # Docker build exclusions
├── .gitignore                     # Git exclusions
├── README.md                      # This file
├── CHANGELOG.md                   # Version history
└── LICENSE                        # Apache 2.0 License
```

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with Docker
5. Submit a pull request

## License

Apache License 2.0 - See [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/ClaraVnk/openstack-instance-guardian/issues)
- **Docker Images**: [GitHub Container Registry](https://github.com/ClaraVnk/openstack-instance-guardian/pkgs/container/openstack-instance-guardian)