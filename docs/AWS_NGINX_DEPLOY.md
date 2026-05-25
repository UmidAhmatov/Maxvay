# AWS EC2 + NGINX deploy

Bu loyiha production uchun Docker Compose bilan yuradi:

- `web`: Django + Gunicorn
- `nginx`: reverse proxy va static files
- `maxway_data`: SQLite baza uchun Docker volume
- `maxway_static`: `collectstatic` natijalari uchun Docker volume

## AWS EC2 tayyorlash

1. EC2 instance yarating: Ubuntu 22.04/24.04 LTS.
2. Security Group inbound rules:
   - SSH: `22`, faqat o'zingizning IP manzilingizdan
   - HTTP: `80`, `0.0.0.0/0`
   - HTTPS: `443`, `0.0.0.0/0` kerak bo'lsa
3. Elastic IP ulang.
4. Domen bo'lsa, A record ni Elastic IP ga yo'naltiring.

## Serverga kerakli paketlar

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo tee /etc/apt/keyrings/docker.asc >/dev/null
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker ubuntu
```

Serverdan chiqib qayta SSH qiling, keyin:

```bash
docker --version
docker compose version
```

## Loyiha fayllarini serverga yuborish

Variant 1: Git orqali:

```bash
git clone <repo-url> ~/maxway
cd ~/maxway
```

Variant 2: `scp` yoki `rsync` orqali shu papkani `~/maxway` ga yuboring.

Windows/PyCharm kompyuteringizdan avtomatik deploy:

```powershell
.\scripts\deploy-aws.ps1 -HostName 13.61.27.33 -User ubuntu -KeyPath "C:\path\to\your-key.pem"
```

Amazon Linux ishlatsangiz user odatda `ec2-user`:

```powershell
.\scripts\deploy-aws.ps1 -HostName 13.61.27.33 -User ec2-user -KeyPath "C:\path\to\your-key.pem"
```

## Production `.env`

Serverda:

```bash
cd ~/maxway
cp .env.example .env
nano .env
```

Majburiy o'zgartiring:

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DJANGO_SUPERUSER_PASSWORD`

## Ishga tushirish

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
```

Loglarni ko'rish:

```bash
docker compose -f docker-compose.prod.yml logs -f
```

Yangilash:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

To'xtatish:

```bash
docker compose -f docker-compose.prod.yml down
```

## Tekshirish

```bash
curl http://127.0.0.1/api/health
```

Brauzer:

```text
http://server-public-ip
http://your-domain.com
```
