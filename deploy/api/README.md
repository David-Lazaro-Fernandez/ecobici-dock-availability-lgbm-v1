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

The web app is on HTTPS, so browsers block calls to an `http://` API. Caddy gets a free
certificate, but only for a host name, not for a bare IP address.

Get a host name. Without a domain, use a free subdomain from <https://www.duckdns.org>, for
example `ecobici-api.duckdns.org`, and set it to the public IP of this machine. In OCI, make
the public IP reserved, so it does not change if you re-create the instance.

Install Caddy:

```sh
sudo dnf install -y dnf-plugins-core
sudo dnf copr enable @caddy/caddy && sudo dnf install -y caddy
```

If the COPR repository fails, install the release binary from
<https://github.com/caddyserver/caddy/releases> and its systemd unit.

Copy `Caddyfile` to `/etc/caddy/Caddyfile` and set your host name. Then:

```sh
sudo systemctl enable --now caddy
sudo firewall-cmd --permanent --add-service=http --add-service=https && sudo firewall-cmd --reload
curl https://ecobici-api.duckdns.org/v1/stations
```

If `getenforce` prints `Enforcing`, let Caddy connect to the API:

```sh
sudo setsebool -P httpd_can_network_connect 1
```

Also open ports 80 and 443 in the OCI security list of the subnet. Caddy needs port 80 to
get the certificate.

### Alternative: Cloudflare Tunnel

With a domain in Cloudflare, a tunnel needs no open ports. Install
`cloudflared-linux-aarch64.rpm` from <https://github.com/cloudflare/cloudflared/releases>.
In the dashboard (Zero Trust, Networks, Tunnels), create a tunnel with the service
`http://127.0.0.1:8000`, then run the `cloudflared service install <TOKEN>` command it shows.
Do not commit the token.

## 5. Vercel

Root directory `web/`. Environment variable `NEXT_PUBLIC_API_URL=https://your-api-domain`.

## Updating

`setup.sh` enables the `ecobici-autodeploy` timer. Every 5 minutes it fetches the branch that
the server checkout tracks. If there are new commits, it fast-forwards and runs `setup.sh`.
Thus a push to that branch is a deploy to prod. To deploy another branch, switch the
checkout to it.

```sh
systemctl list-timers ecobici-autodeploy.timer
journalctl -u ecobici-autodeploy -n 50
sudo systemctl start ecobici-autodeploy
```

The last command deploys now. The timer does not update the model files. After a new model
or bundle, copy the model files again (step 2), then run `sudo systemctl restart ecobici-api`.
