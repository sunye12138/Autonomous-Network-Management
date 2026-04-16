# Linux Onebox Package (10.250.30.114)

This package is prepared for Linux server **10.250.30.114**.

## Preset notes
- Artifact store path: `/mnt/dockerContainerSave/image`
- Preset servers: `10.250.30.101` ~ `10.250.30.106`
- Ping check is enabled so you can distinguish host reachability from Agent availability.

## Included content
- Backend API
- Customer portal `portal.html`
- Admin page `index.html`
- onebox start / stop / status / rebuild scripts

## Start
```bash
cd /root/server-manager/release-onebox-10.250.30.114
chmod +x start.sh stop.sh status.sh rebuild.sh ./deploy/onebox/*.sh
HOST_DOCKER_BIN=$(which docker) ./start.sh
```

## Rebuild
```bash
cd /root/server-manager/release-onebox-10.250.30.114
chmod +x start.sh stop.sh status.sh rebuild.sh ./deploy/onebox/*.sh
HOST_DOCKER_BIN=$(which docker) ./rebuild.sh
```

## URLs
- Portal: `http://10.250.30.114:14173/portal.html`
- Admin: `http://10.250.30.114:14173/index.html`
- Health: `http://10.250.30.114:18000/api/health`
