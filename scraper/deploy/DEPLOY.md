# RT Scraper — Hetzner Deploy

Step-by-step guide for deploying the scraper as a systemd-timer cron worker on a fresh Ubuntu 22.04+ Hetzner box.

## 1. Prerequisites

- Ubuntu 22.04+ (or any systemd-based Linux)
- Python 3.11+ available as `python3.11`
- Network access to Supabase + Google Maps
- Sudo access

Install system-level Chromium dependencies (Playwright pulls down its own Chromium, but the OS-level libs are needed):

```bash
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3-pip git
```

## 2. Create scraper user + directories

```bash
sudo useradd -r -s /usr/sbin/nologin -m -d /opt/rt-scraper scraper
sudo install -d -o scraper -g scraper /opt/rt-scraper
sudo touch /var/log/rt-scraper.log
sudo chown scraper:scraper /var/log/rt-scraper.log
```

## 3. Clone repo + install package

Use the production branch (currently `feat/lead-scraper-system` until merged to `main`).

```bash
sudo -u scraper -H git clone -b feat/lead-scraper-system \
  https://github.com/stefanroman22/cms-platform.git /opt/rt-scraper/src
sudo -u scraper -H python3.11 -m venv /opt/rt-scraper/.venv
sudo -u scraper -H /opt/rt-scraper/.venv/bin/pip install --upgrade pip
sudo -u scraper -H /opt/rt-scraper/.venv/bin/pip install -e "/opt/rt-scraper/src/scraper"
sudo -u scraper -H /opt/rt-scraper/.venv/bin/python -m playwright install --with-deps chromium
```

## 4. Place secrets

Create `/etc/scraper.env` from the template at `/opt/rt-scraper/src/scraper/.env.example`. Populate every variable. Then lock it down:

```bash
sudo cp /opt/rt-scraper/src/scraper/.env.example /etc/scraper.env
sudo $EDITOR /etc/scraper.env   # fill in real values
sudo chmod 640 /etc/scraper.env
sudo chown root:scraper /etc/scraper.env
```

## 5. Install systemd units

```bash
sudo cp /opt/rt-scraper/src/scraper/deploy/scraper.service /etc/systemd/system/
sudo cp /opt/rt-scraper/src/scraper/deploy/scraper.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now scraper.timer
```

## 6. Verify

Status checks:

```bash
systemctl status scraper.timer
systemctl list-timers scraper.timer
sudo journalctl -u scraper.service -n 50
```

Force a manual run (don't wait for the next timer tick):

```bash
sudo -u scraper -H /opt/rt-scraper/.venv/bin/python -m scraper.cli run-pending
tail -f /var/log/rt-scraper.log
```

If the log shows `no pending jobs`, the scraper is healthy — just needs a job from the CMS dashboard (or `INSERT INTO scrape_jobs ...` directly).

## 7. Log rotation

Create `/etc/logrotate.d/rt-scraper`:

```
/var/log/rt-scraper.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 640 scraper scraper
}
```

## 8. Updating

```bash
sudo -u scraper -H git -C /opt/rt-scraper/src pull
sudo -u scraper -H /opt/rt-scraper/.venv/bin/pip install -e "/opt/rt-scraper/src/scraper"
sudo systemctl restart scraper.timer
```

If the scraper package's dependencies changed, repeat the `playwright install` step too.

## 9. Smoke test from CMS

After deploy, submit a tiny scrape from the CMS dashboard (or via curl against `/admin/scrape-jobs`):

```bash
curl -X POST https://cms-backend-roman.vercel.app/admin/scrape-jobs \
  -H "Authorization: Bearer $CMS_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "category": "restaurants",
      "country": "NL",
      "cities": ["Lelystad"],
      "max_results_per_area": 5
    }
  }'
```

Then wait for the next 30-min tick (or run `run-pending` manually). Verify:

- Job transitions `pending` → `running` → `done` in the dashboard / via `GET /admin/scrape-jobs`
- `results_inserted > 0`
- Leads appear in Supabase `leads` table
