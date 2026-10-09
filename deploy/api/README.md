# API on Oracle Linux

Runs `ecobici.api` with uvicorn behind Caddy (HTTPS). The web app runs on Vercel and calls
this API.

## 1. AWS access

Create an IAM user with `iam-policy.json` (replace `YOUR-BUCKET`). Create an access key.
The API reads captures from `raw/`. It writes feedback to `feedback/` and the plans that
people ask for to `plans/`.

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

## 4. HTTPS with Caddy and DuckDNS

Caddy gets and renews the HTTPS certificate by itself.

1. Reserved IP: in OCI, check that the public IP of the instance is reserved. A reserved IP
   does not change, so the DNS record stays valid.
2. DuckDNS: create a subdomain, for example `ecobici-docks.duckdns.org`. Point it to the
   reserved IP.
3. Ports: open ports 80 and 443 in the OCI security list of the subnet and in firewalld.
   Caddy needs port 80 to get the certificate.

   ```sh
   sudo firewall-cmd --permanent --add-service=http --add-service=https
   sudo firewall-cmd --reload
   ```

4. Caddy: install it (`sudo dnf install -y dnf-plugins-core && sudo dnf copr enable
   @caddy/caddy && sudo dnf install -y caddy`, or the release binary from
   <https://github.com/caddyserver/caddy/releases>). Copy `Caddyfile` to
   `/etc/caddy/Caddyfile`, put your subdomain in it, then start Caddy:

   ```sh
   sudo cp deploy/api/Caddyfile /etc/caddy/Caddyfile
   sudo nano /etc/caddy/Caddyfile
   sudo systemctl enable --now caddy
   curl https://ecobici-docks.duckdns.org/v1/stations
   ```

5. SELinux: if `getenforce` prints `Enforcing`, run
   `sudo setsebool -P httpd_can_network_connect 1`. Without it, Caddy cannot connect to
   uvicorn.

### Alternative: Cloudflare Tunnel

The tunnel connects out to Cloudflare, so the machine needs no open ports and no
certificate. You need a domain in Cloudflare.

```sh
sudo dnf install -y https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-aarch64.rpm
```

In the Cloudflare dashboard (Zero Trust, Networks, Tunnels), create a tunnel. Add a public
hostname, for example `api.your-domain`, with the service `http://127.0.0.1:8000`. Run the
install command that the dashboard shows. It contains the tunnel token, so do not commit it:

```sh
sudo cloudflared service install <TOKEN>
curl https://api.your-domain/v1/stations
```

## 5. Vercel

Root directory `web/`. Environment variable `NEXT_PUBLIC_API_URL=https://your-api-domain`.

## Updating

`setup.sh` enables the `ecobici-autodeploy` timer. Every 5 minutes it fetches the branch that
the server checkout tracks. If the branch is not the commit in `/opt/ecobici/DEPLOYED`, it
fast-forwards and runs `setup.sh`. Thus a push to that branch is a deploy to prod. A failed
deploy runs again 5 minutes later. To deploy another branch, switch the checkout to it.

With SELinux, `rsync` started by systemd changes to the `rsync_t` domain, which cannot read
`/home` or write `/opt`. `setup.sh` runs it with `runcon` in the context of the script.

```sh
systemctl list-timers ecobici-autodeploy.timer
journalctl -u ecobici-autodeploy -n 50
sudo systemctl start ecobici-autodeploy
```

The last command deploys now. The timer does not update the model files. After a new model
or bundle, copy the model files again (step 2), then run `sudo systemctl restart ecobici-api`.
