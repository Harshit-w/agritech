# AgriTech v3 — Deployment Guide

## Local Development

```bash
# Clone / extract project
cd agritech_final

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac / Linux

# Install
pip install -r requirements.txt

# Run (development server)
python app.py

# Open
# http://127.0.0.1:5000
```

---

## Environment Variables

Copy `.env.example` to `.env` and edit:

```env
SECRET_KEY=your-random-secret-key-here
DEFAULT_LAT=29.500667
DEFAULT_LON=79.542889
DEFAULT_CITY=Bageshwar, Uttarakhand, India
FLASK_DEBUG=0
PORT=5000
```

---

## Docker

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Rebuild after code changes
docker-compose up -d --build
```

**Docker health check** hits `/api/health` every 30 seconds.

---

## Production with Gunicorn

```bash
pip install gunicorn
gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 60 wsgi:application
```

---

## AWS — Elastic Beanstalk

```bash
pip install awsebcli
eb init -p python-3.11 agritech --region ap-south-1
eb create agritech-prod --instance-type t3.medium
eb deploy
eb open
```

Add a `Procfile`:
```
web: gunicorn --workers 4 --timeout 60 wsgi:application
```

---

## GCP — Cloud Run

```bash
gcloud run deploy agritech \
  --source . \
  --platform managed \
  --region asia-south1 \
  --allow-unauthenticated \
  --memory 1Gi \
  --set-env-vars DEFAULT_LAT=29.500667,DEFAULT_LON=79.542889
```

---

## Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    client_max_body_size 50M;

    location / {
        proxy_pass         http://127.0.0.1:5000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_read_timeout 60s;
    }
}
```

---

## SSL with Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

---

## Health Monitoring

```bash
# Quick check
curl http://localhost:5000/api/health

# Full status
curl http://localhost:5000/api/status
```

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError: flask` | Wrong Python / venv not active | Run `venv\Scripts\activate` then `pip install flask` |
| Dashboard shows `--` | Browser cache | Press `Ctrl+Shift+R` or open in Incognito |
| Weather shows "simulated" | No internet / API down | Check internet; app auto-falls back |
| `Port 5000 in use` | Another process | Change `PORT=5001` in `.env` |
| Disease model not loading | TensorFlow not installed | `pip install tensorflow==2.13.0` |
