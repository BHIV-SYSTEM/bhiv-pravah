# Pravah Deployment - Quick Reference Guide

## 🚀 Quick Start

### Initial VM Setup (Run Once)

```bash
# Clone repo and run setup script
git clone https://github.com/your-org/your-repo.git
cd your-repo/backend
bash scripts/setup-vm.sh https://github.com/your-org/your-repo.git

# Edit environment
nano /opt/pravah/.env

# Start services
sudo systemctl start pravah-compose
```

---

## 📋 Common Commands

### Check Service Status

```bash
# All services
docker compose ps

# Specific service
docker compose ps control-plane

# With resource usage
docker stats

# Systemd status
sudo systemctl status pravah-compose
```

### View Logs

```bash
# Recent logs
docker compose logs --tail=50

# Follow logs (real-time)
docker compose logs -f control-plane

# Last 1 hour
docker compose logs --since=1h decision-brain

# Systemd logs
journalctl -u pravah-compose -f
```

### Manual Restart

```bash
# Restart specific service
docker compose restart control-plane

# Restart all services
docker compose down && docker compose up -d

# Restart via systemd
sudo systemctl restart pravah-compose
```

### Pull Latest Images

```bash
cd /opt/pravah
docker compose pull
docker compose down
docker compose --profile prod up -d
```

---

## 🔄 Rollback Process

### Automatic Rollback (If Deployed Wrong)

```bash
# Triggered if health checks fail
# Runs automatically via systemd

# Manual trigger if needed
sudo systemctl start pravah-compose-rollback
```

### Manual Rollback (To Specific Date)

```bash
# View available backups
ls -lh /opt/pravah-backup/

# Restore specific backup
BACKUP_DATE="backup_20240115_143022"
cp -r /opt/pravah-backup/$BACKUP_DATE/* /opt/pravah/

# Verify files restored
ls -la /opt/pravah/docker-compose.yml

# Start services
cd /opt/pravah
docker compose --profile prod up -d

# Verify health
docker compose exec -T redis redis-cli ping
```

---

## 🔍 Troubleshooting

### Service Won't Start

```bash
# Check logs
docker compose logs <service_name>

# Check if port is already in use
sudo lsof -i :7000
sudo lsof -i :8000
sudo lsof -i :8600
sudo lsof -i :6379

# Kill process on port
sudo kill -9 <PID>

# Check disk space
df -h

# Check RAM
free -h

# Restart docker
sudo systemctl restart docker
docker compose up -d
```

### Redis Not Responding

```bash
# Check Redis status
docker compose exec -T redis redis-cli ping

# Check Redis logs
docker compose logs redis

# Restart Redis
docker compose restart redis

# Force restart
docker compose down
docker volume rm pravah-redis-data
docker compose up -d redis
```

### Control Plane Crashing

```bash
# Check error logs
docker compose logs --tail=100 control-plane

# Check health
curl http://localhost:7000/api/health

# Restart with increased verbosity
docker compose exec -T control-plane tail -f /app/logs/error.log

# Check memory
docker stats control-plane
```

### Out of Disk Space

```bash
# Check disk usage
df -h

# Cleanup unused images
docker image prune -a

# Cleanup unused volumes
docker volume prune

# Cleanup logs (but save to backup first)
sudo truncate -s 0 /opt/pravah/logs/*.log

# Check large files
du -sh /opt/pravah/*

# Clear old backups manually (keep latest 3)
ls -t /opt/pravah-backup/ | tail -n +4 | xargs -I {} rm -rf /opt/pravah-backup/{}
```

---

## 🔐 Configuration

### Edit Environment Variables

```bash
# Edit .env file
nano /opt/pravah/.env

# Key variables:
ENVIRONMENT=prod                    # Never change in prod
GUNICORN_WORKERS=4                 # Adjust for CPU cores
REDIS_MAX_MEMORY=512mb             # Adjust for available RAM
DOCKER_HUB_USERNAME=yourname       # Docker Hub username

# After edit, restart services
docker compose down
docker compose up -d --profile prod
```

### Add New Service

```bash
# Edit docker-compose.yml
nano /opt/pravah/docker-compose.yml

# Add new service definition
# Then restart
docker compose up -d --profile prod
```

---

## 📊 Monitoring

### Check Resource Usage

```bash
# Real-time stats
docker stats

# Container memory
docker stats control-plane --no-stream

# Disk usage by container
docker system df

# Network usage
docker stats --no-stream --format "table {{.Container}}\t{{.NetIO}}"
```

### View Metrics

```bash
# Prometheus (if enabled)
open http://localhost:9090

# Control Plane metrics
curl http://localhost:7000/metrics

# Redis memory usage
docker compose exec -T redis redis-cli INFO memory

# Check logs location
ls -lh /opt/pravah/logs/
```

---

## 🌐 Port Reference

| Service | Port | Access |
|---------|------|--------|
| Control Plane | 7000 | http://vm-ip:7000 |
| Decision Brain | 8000 | http://vm-ip:8000 |
| Observer | 8600 | http://vm-ip:8600 |
| Redis | 6379 | localhost only |
| Prometheus | 9090 | http://vm-ip:9090 |

---

## 📝 Backup & Restore

### Automatic Backups

- Location: `/opt/pravah-backup/`
- Created before every deployment
- Timestamped: `backup_YYYYMMDD_HHMMSS`
- Last 5 kept automatically

### Manual Backup

```bash
# Create manual backup
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
cp -r /opt/pravah /opt/pravah-backup/manual_$TIMESTAMP

# Backup to external storage
tar -czf /backups/pravah_$TIMESTAMP.tar.gz /opt/pravah/
```

### Restore from Backup

```bash
# Stop services first
docker compose down

# Restore files
cp -r /opt/pravah-backup/backup_YYYYMMDD_HHMMSS/* /opt/pravah/

# Verify
ls -la /opt/pravah/docker-compose.yml

# Start services
docker compose --profile prod up -d
```

---

## 🔔 Health Checks

### Manual Health Verification

```bash
# Redis
docker compose exec -T redis redis-cli ping

# Control Plane
curl -v http://localhost:7000/api/health

# Decision Brain
curl -v http://localhost:8000/health

# Observer
curl -v http://localhost:8600/health

# All services
docker compose ps
```

### Expected Health Output

```bash
$ docker compose ps

NAME                           STATUS
pravah-redis                   Up 2 hours (healthy)
pravah-control-plane          Up 2 hours (healthy)
pravah-decision-brain          Up 2 hours (healthy)
pravah-observer               Up 2 hours (healthy)
pravah-deploy-worker-1        Up 2 hours
pravah-deploy-worker-2        Up 2 hours
pravah-deploy-worker-3        Up 2 hours
pravah-queue-monitor          Up 2 hours
pravah-health-monitor         Up 2 hours
```

---

## 🚨 Emergency Procedures

### Complete System Restart

```bash
# Stop all services
docker compose down

# Wait 5 seconds
sleep 5

# Start all services
docker compose --profile prod up -d

# Wait for health checks (60 seconds)
sleep 60

# Verify all running
docker compose ps
```

### Force Restart (if stuck)

```bash
# Kill all containers
docker compose kill

# Remove containers
docker compose rm -f

# Restart
docker compose up -d --profile prod
```

### Factory Reset (Last Resort)

```bash
# WARNING: This removes all data!
# Create backup first!

cp -r /opt/pravah /opt/pravah-backup/factory_reset_$(date +%s)

# Stop services
docker compose down

# Remove all volumes and data
docker volume rm $(docker volume ls -q | grep pravah)
rm -rf /opt/pravah/logs/* /opt/pravah/data/*

# Restart
docker compose --profile prod up -d
```

---

## 📞 Support

### Collect Debug Info

```bash
# For troubleshooting, collect:

# 1. Service status
docker compose ps > debug_ps.txt

# 2. System resources
docker stats --no-stream > debug_stats.txt
free -h >> debug_stats.txt
df -h >> debug_stats.txt

# 3. Recent logs
docker compose logs --since=1h > debug_logs.txt

# 4. Systemd logs
journalctl -u pravah-compose -n 100 > debug_systemd.txt

# 5. Error logs
cat /opt/pravah/logs/error.log > debug_error.txt
```

### Report Issues

When reporting issues, include:
- Output of debug collection above
- Time when issue occurred
- What was deployed/changed
- Error messages from logs
- Steps to reproduce

---

## 📚 More Information

- Full documentation: `DEPLOYMENT_GUIDE.md`
- Docker Compose docs: https://docs.docker.com/compose/
- GitHub Actions docs: https://docs.github.com/actions
- Docker docs: https://docs.docker.com/

---

**Last Updated:** 2024
**Version:** 1.0
