# API on Oracle Linux

Runs `ecobici.api` with uvicorn behind Caddy (HTTPS). The web app runs on Vercel and calls
this API.

## 1. AWS access

Create an IAM user with `iam-policy.json` (replace `YOUR-BUCKET`). Create an access key.
The API reads captures from `raw/` and writes feedback to `feedback/`.

## 2. Model files

The API needs the frozen models (`artifacts/lgbm_*.txt`, `isotonic_*.json`,
`platt_sub_*.json`), the empty-station models (`artifacts/empty/`) and the serving bundle
(`artifacts/serving/`). The bundle needs about 12 GB of RAM to build. Build it on a laptop,
then copy everything to the server:

```sh
uv run --extra api --extra model python -m ecobici.bundle
ssh opc@SERVER mkdir -p /tmp/artifacts
scp -r artifacts/serving artifacts/empty artifacts/lgbm_*.txt artifacts/isotonic_*.json \
  artifacts/platt_sub_*.json opc@SERVER:/tmp/artifacts/
```

On the server:

```sh
sudo mkdir -p /opt/ecobici/artifacts
sudo cp -r /tmp/artifacts/. /opt/ecobici/artifacts/
```

## 3. Install

The first run of `setup.sh` stops and asks you to edit `/etc/ecobici/api.env`.

```sh
sudo ./deploy/api/setup.sh
sudo nano /etc/ecobici/api.env
sudo ./deploy/api/setup.sh
curl http://127.0.0.1:8000/docs
```

Set `ECOBICI_API_ORIGINS` to the exact Vercel URL, without a trailing slash.

## 4. HTTPS with Caddy

Point a DNS A record at this machine. Install Caddy:

```sh
sudo dnf install -y dnf-plugins-core
sudo dnf copr enable @caddy/caddy && sudo dnf install -y caddy
```

If the COPR repository fails, install the release binary from
<https://github.com/caddyserver/caddy/releases> and its systemd unit.

Copy `Caddyfile` to `/etc/caddy/Caddyfile` and set your domain. Then:

```sh
sudo systemctl enable --now caddy
sudo firewall-cmd --permanent --add-service=http --add-service=https && sudo firewall-cmd --reload
```

If `getenforce` prints `Enforcing`, let Caddy connect to the API:

```sh
sudo setsebool -P httpd_can_network_connect 1
```

Also open ports 80 and 443 in the OCI security list of the subnet.
Without a domain, use a Cloudflare Tunnel to `http://127.0.0.1:8000` instead of Caddy.

## 5. Vercel

Root directory `web/`. Environment variable `NEXT_PUBLIC_API_URL=https://your-api-domain`.

## Updating

```sh
git pull && sudo ./deploy/api/setup.sh
```

After a new model or bundle, copy the model files again (step 2), then run
`sudo systemctl restart ecobici-api`.
