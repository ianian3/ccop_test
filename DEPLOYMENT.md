# CCOP v1.0 Deployment Guide

Complete guide for deploying CCOP graph analysis platform to production.

## Prerequisites

- Docker & Docker Compose installed
- VPS or cloud server (2GB RAM minimum, 4GB recommended)
- Domain name (optional, for HTTPS)
- Git installed

## Quick Start (Local Testing)

### 1. Clone Repository

```bash
git clone https://github.com/ianian3/ccop_test.git
cd ccop_test
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
nano .env
```

Required environment variables:
```env
DB_PASSWORD=your_secure_password
OPENAI_API_KEY=sk-your-key-here
SECRET_KEY=your-flask-secret-key
```

### 3. Start with Docker Compose

```bash
# Build and start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f app
```

Access the application at `http://localhost:5001`

### 4. Stop Services

```bash
docker-compose down
# To remove volumes as well:
docker-compose down -v
```

---

## Production Deployment (VPS)

### Option 1: DigitalOcean / AWS EC2 / Google Cloud Compute

#### Step 1: Server Setup

```bash
# SSH into your server
ssh root@your-server-ip

# Update system
apt-get update && apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt-get install docker-compose-plugin -y

# Create non-root user (recommended)
adduser ccop
usermod -aG docker ccop
su - ccop
```

#### Step 2: Deploy Application

```bash
# Clone repository
git clone https://github.com/ianian3/ccop_test.git
cd ccop_test

# Configure environment
cp .env.example .env
nano .env
```

Set production values:
```env
DB_NAME=ccopdb
DB_USER=ccop
DB_PASSWORD=STRONG_PASSWORD_HERE
DB_HOST=agensgraph
DB_PORT=5432
OPENAI_API_KEY=sk-your-key
FLASK_ENV=production
SECRET_KEY=GENERATE_RANDOM_SECRET_KEY
```

**Generate secure secret key:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

#### Step 3: Start Services

```bash
# Build and start
docker-compose up -d

# Verify all containers are running
docker-compose ps

# Check logs
docker-compose logs -f
```

#### Step 4: Configure Firewall

```bash
# Allow HTTP/HTTPS
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

#### Step 5: Domain & SSL (Optional)

**Using Nginx and Let's Encrypt:**

```bash
# Install certbot
apt-get install certbot python3-certbot-nginx -y

# Stop nginx container temporarily
docker-compose stop nginx

# Get SSL certificate
certbot certonly --standalone -d your-domain.com

# Copy certificates
mkdir -p deploy/ssl
cp /etc/letsencrypt/live/your-domain.com/fullchain.pem deploy/ssl/
cp /etc/letsencrypt/live/your-domain.com/privkey.pem deploy/ssl/

# Update nginx.conf to use HTTPS (uncomment SSL section)
nano deploy/nginx.conf

# Restart services
docker-compose up -d
```

---

## Database Management

### Backup Database

```bash
# Manual backup
./scripts/backup_db.sh

# Schedule automatic backups (cron)
crontab -e
# Add this line for daily backups at 2 AM:
0 2 * * * /path/to/ccop_test/scripts/backup_db.sh
```

### Restore Database

```bash
# Stop app container
docker-compose stop app

# Restore from backup
gunzip -c /var/backups/agensgraph/ccopdb_backup_TIMESTAMP.sql.gz | \
docker-compose exec -T agensgraph psql -U ccop -d ccopdb

# Restart app
docker-compose start app
```

### Access Database Shell

```bash
docker-compose exec agensgraph psql -U ccop -d ccopdb
```

---

## Monitoring & Maintenance

### View Application Logs

```bash
# Follow all logs
docker-compose logs -f

# App logs only
docker-compose logs -f app

# Last 100 lines
docker-compose logs --tail=100 app
```

### Check Resource Usage

```bash
# Container stats
docker stats

# Disk usage
docker system df
```

### Update Application

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose up -d --build

# Clean up old images
docker image prune -a
```

### Health Checks

```bash
# Check app health
curl http://localhost:5001/

# Check database connection
docker-compose exec agensgraph pg_isready -U ccop
```

---

## Scaling & Performance

### Increase Gunicorn Workers

Edit `deploy/gunicorn_config.py`:
```python
workers = 8  # Adjust based on CPU cores
```

### Enable Nginx Caching

Add to `deploy/nginx.conf`:
```nginx
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=my_cache:10m max_size=1g;

location / {
    proxy_cache my_cache;
    proxy_cache_valid 200 1m;
    # ... rest of config
}
```

---

## Troubleshooting

### App won't start

```bash
# Check logs
docker-compose logs app

# Common issues:
# 1. Database not ready - wait 30 seconds and retry
# 2. Missing .env file - copy from .env.example
# 3. Port 5001 already in use - change port in docker-compose.yml
```

### Database connection errors

```bash
# Verify database is running
docker-compose ps agensgraph

# Check database logs
docker-compose logs agensgraph

# Test connection
docker-compose exec app python -c "from app.database import get_db; print(get_db())"
```

### Out of memory

```bash
# Check memory usage
free -h

# Reduce Gunicorn workers in deploy/gunicorn_config.py
# Or upgrade server RAM
```

---

## Security Checklist

- [ ] Change default passwords in `.env`
- [ ] Generate strong `SECRET_KEY`
- [ ] Enable firewall (ufw)
- [ ] Set up HTTPS with SSL certificate
- [ ] Restrict database access to localhost only
- [ ] Keep Docker images updated
- [ ] Enable automatic security updates
- [ ] Set up monitoring/alerting
- [ ] Regular database backups
- [ ] Review nginx access logs for suspicious activity

---

## Cost Estimation

### DigitalOcean Droplet
- Basic: $12/month (2GB RAM, 1 CPU)
- Standard: $24/month (4GB RAM, 2 CPU) **Recommended**
- Premium: $48/month (8GB RAM, 4 CPU)

### AWS EC2
- t3.small: ~$15/month (2GB RAM)
- t3.medium: ~$30/month (4GB RAM) **Recommended**

### GCP Compute Engine
- e2-small: ~$13/month (2GB RAM)
- e2-medium: ~$27/month (4GB RAM) **Recommended**

**Additional costs:**
- Domain: $10-15/year
- SSL: Free (Let's Encrypt)

---

## Support & Contributing

- **Issues**: https://github.com/ianian3/ccop_test/issues
- **Discussions**: Contact maintainer
- **Documentation**: See README.md

---

## Next Steps

After successful deployment:
1. ✅ Test all features (search, expand, CSV upload, AI query)
2. ✅ Set up monitoring (consider UptimeRobot or Datadog)
3. ✅ Configure automated backups
4. ✅ Set up domain and SSL
5. ✅ Create user documentation
6. ✅ Plan for scaling if needed
