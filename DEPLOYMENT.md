# Ginie Deployment Guide

This guide covers deployment strategies for all Ginie services across different environments.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Production Stack                         │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────┐    │
│  │  Frontend   │    │  Backend API │    │ Canton Network│   │
│  │  (Next.js)  │───►│  (FastAPI)   │───►│  (DevNet/Main)│  │
│  │  Port 3000  │    │  Port 8000   │    │  Port 7575    │    │
│  └─────────────┘    └──────────────┘    └──────────────┘    │
│         │                   │                   │              │
│         │                   ▼                   │              │
│         │            ┌──────────────┐         │              │
│         │            │ PostgreSQL    │         │              │
│         │            │ Port 5432     │         │              │
│         │            └──────────────┘         │              │
│         │                   │                   │              │
│         │            ┌──────────────┐         │              │
│         └───────────►│   Redis      │◄────────┘              │
│                      │  Port 6379    │                         │
│                      └──────────────┘                         │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Service 1: Canton Network Deployment

### Options

| Environment | Use Case | Deployment Method |
|-------------|----------|-------------------|
| **Sandbox** | Local development, testing | Run locally with Daml SDK |
| **DevNet** | Staging, integration testing | Splice DevNet (managed) |
| **MainNet** | Production, real transactions | Splice MainNet (managed) |

### 1.1 Sandbox (Local Development)

**When to use**: Development, quick iteration, no persistence needed

**Deployment Method**: Run locally on your machine

```bash
# Start Canton sandbox locally
cd /path/to/Canton_Ginie
./scripts/start-canton-sandbox.ps1 -InMemory
```

**Pros**:
- Free, no infrastructure cost
- Fast startup
- Full control

**Cons**:
- Data lost on restart
- Not suitable for production
- Requires Java 11+

---

### 1.2 DevNet (Staging)

**When to use**: Integration testing, staging environment, multi-party testing

**Deployment Method**: Splice DevNet (managed Canton network)

**Steps**:

1. **Sign up for Splice DevNet**:
   - Go to: https://splice.dev/
   - Create an account
   - Get API credentials

2. **Configure environment variables**:
   ```bash
   # backend/.env.ginie
   CANTON_ENVIRONMENT=devnet
   CANTON_DEVNET_URL=https://devnet.splice.api.com
   CANTON_TOKEN=your_splice_devnet_token
   CANTON_OAUTH2_TOKEN_URL=https://devnet.splice.api.com/oauth/token
   CANTON_CLIENT_ID=your_client_id
   CANTON_CLIENT_SECRET=your_client_secret
   CANTON_SCOPE=openid profile email
   CANTON_AUDIENCE=https://devnet.splice.api.com
   CANTON_API_VERSION=v2
   ```

3. **OAuth2 Token Management**:
   The backend will automatically fetch OAuth2 tokens using the client credentials flow.

**Pros**:
- Persistent ledger state
- Multi-party simulation
- Production-like environment
- Managed infrastructure

**Cons**:
- Requires Splice account
- Rate limits may apply
- Network latency

---

### 1.3 MainNet (Production)

**When to use**: Production deployment, real transactions, regulated finance

**Deployment Method**: Splice MainNet or self-hosted Canton

**Steps**:

1. **Splice MainNet** (Recommended):
   - Apply for MainNet access: https://splice.dev/
   - Complete KYC/AML verification
   - Get production credentials

2. **Configure environment variables**:
   ```bash
   # backend/.env.ginie
   CANTON_ENVIRONMENT=mainnet
   CANTON_MAINNET_URL=https://mainnet.splice.api.com
   CANTON_TOKEN=your_splice_mainnet_token
   CANTON_OAUTH2_TOKEN_URL=https://mainnet.splice.api.com/oauth/token
   CANTON_CLIENT_ID=your_client_id
   CANTON_CLIENT_SECRET=your_client_secret
   CANTON_SCOPE=openid profile email
   CANTON_AUDIENCE=https://mainnet.splice.api.com
   CANTON_API_VERSION=v2
   JWT_SECRET=your_strong_jwt_secret  # REQUIRED for mainnet
   ```

3. **Self-hosted Canton** (Advanced):
   - Deploy Canton nodes on your infrastructure
   - Configure participant nodes
   - Set up domain services
   - Requires DevOps expertise

**Pros**:
- Real production ledger
- Regulatory compliance
- Full control (if self-hosted)

**Cons**:
- Requires approval/verification
- Infrastructure costs
- Strict compliance requirements

---

## Service 2: Backend API Deployment

### Options

| Platform | Complexity | Cost | Scaling |
|----------|------------|------|---------|
| **Docker + VPS** | Low | $5-20/mo | Manual |
| **AWS ECS** | Medium | $50-200/mo | Auto |
| **Google Cloud Run** | Low | $0-50/mo | Auto |
| **Azure Container Apps** | Medium | $30-150/mo | Auto |
| **Kubernetes** | High | $100-500/mo | Auto |

---

### 2.1 Docker + VPS (Simplest)

**When to use**: Small deployments, cost-sensitive, single instance

**Platforms**: DigitalOcean, Linode, AWS Lightsail, Hetzner

**Steps**:

1. **Build Docker image**:
   ```bash
   cd backend
   docker build -t ginie-backend:latest .
   ```

2. **Push to registry**:
   ```bash
   docker tag ginie-backend:latest your-registry.com/ginie-backend:latest
   docker push your-registry.com/ginie-backend:latest
   ```

3. **Deploy to VPS**:
   ```bash
   # SSH into VPS
   ssh user@your-vps-ip
   
   # Pull and run
   docker pull your-registry.com/ginie-backend:latest
   docker run -d \
     --name ginie-backend \
     -p 8000:8000 \
     --env-file .env.ginie \
     --restart unless-stopped \
     your-registry.com/ginie-backend:latest
   ```

4. **Set up reverse proxy** (Nginx):
   ```nginx
   server {
       listen 80;
       server_name api.yourdomain.com;
       
       location / {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

**Pros**:
- Simple deployment
- Low cost ($5-10/mo)
- Full control

**Cons**:
- Manual scaling
- No auto-healing
- Security management

---

### 2.2 AWS ECS (Recommended for Production)

**When to use**: Production, auto-scaling, enterprise

**Steps**:

1. **Push to ECR**:
   ```bash
   # Login to ECR
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com
   
   # Build and push
   docker build -t ginie-backend .
   docker tag ginie-backend:latest YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/ginie-backend:latest
   docker push YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/ginie-backend:latest
   ```

2. **Create ECS Task Definition** (AWS Console or Terraform):
   ```json
   {
     "family": "ginie-backend",
     "networkMode": "awsvpc",
     "requiresCompatibilities": ["FARGATE"],
     "cpu": "512",
     "memory": "1024",
     "containerDefinitions": [
       {
         "name": "ginie-backend",
         "image": "YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/ginie-backend:latest",
         "portMappings": [{"containerPort": 8000}],
         "environment": [
           {"name": "DATABASE_URL", "value": "${DATABASE_URL}"},
           {"name": "REDIS_URL", "value": "${REDIS_URL}"},
           {"name": "CANTON_ENVIRONMENT", "value": "mainnet"}
         ],
         "secrets": [
           {"name": "OPENAI_API_KEY", "valueFrom": "arn:aws:secretsmanager:...:OPENAI_API_KEY"}
         ],
         "logConfiguration": {
           "logDriver": "awslogs",
           "options": {
             "awslogs-group": "/ecs/ginie-backend",
             "awslogs-region": "us-east-1"
           }
         }
       }
     ]
   }
   ```

3. **Create ECS Service**:
   - Use Application Load Balancer
   - Enable auto-scaling (2-10 instances)
   - Configure health checks

4. **Set up CI/CD** (GitHub Actions):
   ```yaml
   name: Deploy Backend
   on:
     push:
       branches: [main]
   jobs:
     deploy:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - name: Build and push to ECR
           run: |
             docker build -t ginie-backend .
             docker push ${{ secrets.ECR_REGISTRY }}/ginie-backend:latest
         - name: Deploy to ECS
           run: |
             aws ecs update-service --cluster ginie-cluster --service ginie-backend --force-new-deployment
   ```

**Pros**:
- Auto-scaling
- Load balancing
- Managed infrastructure
- High availability

**Cons**:
- Higher cost ($50-200/mo)
- AWS complexity
- Learning curve

---

### 2.3 Google Cloud Run (Serverless)

**When to use**: Serverless, pay-per-use, zero infrastructure management

**Steps**:

1. **Push to GCR**:
   ```bash
   gcloud auth configure-docker
   docker build -t gcr.io/YOUR_PROJECT/ginie-backend .
   docker push gcr.io/YOUR_PROJECT/ginie-backend
   ```

2. **Deploy to Cloud Run**:
   ```bash
   gcloud run deploy ginie-backend \
     --image gcr.io/YOUR_PROJECT/ginie-backend \
     --platform managed \
     --region us-central1 \
     --port 8000 \
     --memory 1Gi \
     --cpu 1 \
     --max-instances 100 \
     --min-instances 1 \
     --allow-unauthenticated \
     --set-env-vars DATABASE_URL=$DATABASE_URL,REDIS_URL=$REDIS_URL \
     --set-secrets OPENAI_API_KEY=OPENAI_API_KEY:latest
   ```

**Pros**:
- Zero infrastructure management
- Pay-per-use ($0 when idle)
- Auto-scaling to zero
- SSL termination

**Cons**:
- Cold starts (500ms)
- Max 32GB memory
- Vendor lock-in

---

### 2.4 Environment Variables

**Required for all deployments**:
```bash
# LLM Provider (choose one)
LLM_PROVIDER=openai|anthropic|gemini
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...

# Canton Connection
CANTON_ENVIRONMENT=sandbox|devnet|mainnet
CANTON_SANDBOX_URL=http://localhost:7575  # sandbox only
CANTON_DEVNET_URL=https://devnet.splice.api.com  # devnet only
CANTON_MAINNET_URL=https://mainnet.splice.api.com  # mainnet only
CANTON_TOKEN=...  # devnet/mainnet only
CANTON_API_VERSION=auto|v1|v2

# Database
DATABASE_URL=postgresql://user:pass@host:5432/ginie_daml

# Redis
REDIS_URL=redis://host:6379/0

# Auth (required for devnet/mainnet)
JWT_SECRET=your_strong_secret_32_chars_or_more
JWT_ALGORITHM=HS256
JWT_EXPIRY_DAYS=7

# CORS
CORS_ORIGINS=https://your-frontend.com
```

**Use AWS Secrets Manager, Google Secret Manager, or HashiCorp Vault** for production secrets.

---

## Service 3: Frontend Deployment

### Options

| Platform | Complexity | Cost | Features |
|----------|------------|------|----------|
| **Vercel** | Very Low | Free-$20/mo | CDN, SSL, Edge |
| **Netlify** | Very Low | Free-$19/mo | CDN, SSL, Edge |
| **Docker + VPS** | Low | $5-20/mo | Full control |
| **AWS Amplify** | Low | Free-$.25/hr | CI/CD, Auth |
| **Cloudflare Pages** | Low | Free | CDN, Edge |

---

### 3.1 Vercel (Recommended)

**When to use**: Fast deployment, best DX, Next.js optimized

**Steps**:

1. **Connect Vercel to GitHub**:
   - Go to: https://vercel.com/new
   - Import your repository
   - Select `frontend_dark` as root directory

2. **Configure environment variables** (Vercel Dashboard → Settings → Environment Variables):
   ```
   NEXT_PUBLIC_API_URL=https://api.yourdomain.com
   ```

3. **Deploy**:
   - Vercel auto-deploys on push to main
   - Preview deployments for PRs

4. **Custom domain**:
   - Add domain in Vercel Dashboard
   - Update DNS (CNAME to cname.vercel-dns.com)

**vercel.json** (optional configuration):
```json
{
  "buildCommand": "cd frontend_dark && npm run build",
  "outputDirectory": "frontend_dark/.next",
  "framework": "nextjs",
  "regions": ["iad1"],
  "env": {
    "NEXT_PUBLIC_API_URL": {
      "value": "https://api.yourdomain.com"
    }
  }
}
```

**Pros**:
- Zero-config deployment
- Automatic HTTPS
- Global CDN
- Preview deployments
- Free tier available

**Cons**:
- Vendor lock-in
- Build time limits (free tier)
- Edge functions limits

---

### 3.2 Netlify

**When to use**: Alternative to Vercel, good static sites

**Steps**:

1. **Connect Netlify to GitHub**
2. **Configure build settings**:
   - Build command: `cd frontend_dark && npm run build`
   - Publish directory: `frontend_dark/.next`
   - Base directory: `/`

3. **Add environment variables**:
   ```
   NEXT_PUBLIC_API_URL=https://api.yourdomain.com
   ```

4. **Deploy**

**netlify.toml**:
```toml
[build]
  base = "/"
  command = "cd frontend_dark && npm run build"
  publish = "frontend_dark/.next"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

---

### 3.3 Docker + VPS

**Steps**:

1. **Create Dockerfile for frontend**:
   ```dockerfile
   # frontend_dark/Dockerfile
   FROM node:20-alpine AS builder
   WORKDIR /app
   COPY package*.json ./
   RUN npm ci
   COPY . .
   RUN npm run build

   FROM node:20-alpine AS runner
   WORKDIR /app
   COPY --from=builder /app/.next ./.next
   COPY --from=builder /app/node_modules ./node_modules
   COPY --from=builder /app/package.json ./package.json
   EXPOSE 3000
   CMD ["npm", "start"]
   ```

2. **Build and push**:
   ```bash
   docker build -t ginie-frontend .
   docker push your-registry.com/ginie-frontend
   ```

3. **Deploy**:
   ```bash
   docker run -d \
     --name ginie-frontend \
     -p 3000:3000 \
     -e NEXT_PUBLIC_API_URL=https://api.yourdomain.com \
     --restart unless-stopped \
     your-registry.com/ginie-frontend
   ```

4. **Nginx reverse proxy**:
   ```nginx
   server {
       listen 80;
       server_name app.yourdomain.com;
       
       location / {
           proxy_pass http://localhost:3000;
           proxy_set_header Host $host;
       }
   }
   ```

---

## Service 4: Infrastructure Deployment

### 4.1 PostgreSQL

**Options**:

| Platform | Complexity | Cost | Backup |
|----------|------------|------|--------|
| **Docker** | Low | $0 (local) | Manual |
| **AWS RDS** | Low | $15-200/mo | Auto |
| **Google Cloud SQL** | Low | $15-200/mo | Auto |
| **Azure Database** | Low | $15-200/mo | Auto |

**Recommended**: AWS RDS (Multi-AZ for production)

**Steps** (AWS RDS):

1. **Create RDS instance**:
   - Engine: PostgreSQL 16
   - Instance class: db.t3.micro (dev) or db.m5.large (prod)
   - Multi-AZ: Yes (production)
   - Storage: 20GB (dev) or 100GB (prod)

2. **Configure security group**:
   - Allow inbound from backend IP on port 5432

3. **Get connection string**:
   ```bash
   DATABASE_URL=postgresql://user:pass@your-db.rds.amazonaws.com:5432/ginie_daml
   ```

---

### 4.2 Redis

**Options**:

| Platform | Complexity | Cost | Persistence |
|----------|------------|------|-------------|
| **Docker** | Low | $0 (local) | No |
| **AWS ElastiCache** | Low | $20-150/mo | Yes |
| **Google Memorystore** | Low | $20-150/mo | Yes |
| **Azure Cache** | Low | $20-150/mo | Yes |

**Recommended**: AWS ElastiCache (Redis Cluster)

**Steps** (AWS ElastiCache):

1. **Create Redis cluster**:
   - Engine: Redis 7
   - Node type: cache.t3.micro (dev) or cache.m5.large (prod)
   - Cluster mode: Disabled (single node) or Enabled (production)

2. **Configure security group**:
   - Allow inbound from backend IP on port 6379

3. **Get connection string**:
   ```bash
   REDIS_URL=redis://your-redis.xxxxxx.use1.cache.amazonaws.com:6379/0
   ```

---

## Complete Deployment: Docker Compose (All-in-One)

For simple deployments, use the provided `docker-compose.yml`:

```bash
# Start all services (except Canton)
docker-compose up -d

# Start with Canton running locally
docker-compose up -d postgres redis backend
```

**Limitations**:
- Canton must run outside Docker
- Suitable for dev/staging, not production
- No auto-scaling

---

## Production Deployment Checklist

### Security
- [ ] Use HTTPS (SSL/TLS certificates)
- [ ] Enable CORS only for trusted domains
- [ ] Store secrets in Secrets Manager (not env files)
- [ ] Enable rate limiting on API
- [ ] Set up WAF (Web Application Firewall)
- [ ] Enable audit logging
- [ ] Use strong JWT secrets
- [ ] Rotate API keys regularly

### Reliability
- [ ] Configure auto-scaling (min 2 instances)
- [ ] Enable health checks
- [ ] Set up load balancer
- [ ] Configure database backups (daily)
- [ ] Enable multi-AZ for RDS
- [ ] Set up monitoring (CloudWatch, Datadog)
- [ ] Configure alerting (PagerDuty, Slack)
- [ ] Test disaster recovery

### Performance
- [ ] Enable CDN for frontend
- [ ] Use Redis for caching
- [ ] Configure database connection pooling
- [ ] Enable Gzip compression
- [ ] Optimize database queries
- [ ] Use CDN for static assets
- [ ] Enable HTTP/2

### Compliance
- [ ] GDPR compliance (data handling)
- [ ] SOC 2 compliance (if required)
- [ ] PCI DSS (if handling payments)
- [ ] Canton network compliance
- [ ] Audit trail for all transactions
- [ ] Data encryption at rest
- [ ] Data encryption in transit

---

## Cost Estimates (Monthly)

| Service | Dev | Production |
|---------|-----|------------|
| **Frontend (Vercel)** | $0 | $20 |
| **Backend (ECS)** | $50 | $150 |
| **PostgreSQL (RDS)** | $15 | $100 |
| **Redis (ElastiCache)** | $20 | $80 |
| **Canton (Splice)** | $0 (sandbox) | $200 |
| **Load Balancer** | $18 | $30 |
| **Monitoring** | $0 | $50 |
| **Total** | **~$100** | **~$630** |

---

## CI/CD Pipeline

### GitHub Actions Example

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Build and push to ECR
        run: |
          aws ecr get-login-password | docker login --username AWS --password-stdin ${{ secrets.ECR_REGISTRY }}
          docker build -t ginie-backend ./backend
          docker tag ginie-backend ${{ secrets.ECR_REGISTRY }}/ginie-backend:latest
          docker push ${{ secrets.ECR_REGISTRY }}/ginie-backend:latest
      
      - name: Deploy to ECS
        run: |
          aws ecs update-service --cluster ginie-cluster --service ginie-backend --force-new-deployment

  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Deploy to Vercel
        uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.ORG_ID }}
          vercel-project-id: ${{ secrets.PROJECT_ID }}
          working-directory: ./frontend_dark
```

---

## Monitoring & Observability

### Recommended Tools

| Tool | Use Case | Cost |
|------|----------|------|
| **CloudWatch** | AWS metrics/logs | Built-in |
| **Datadog** | APM, metrics | $15/host/mo |
| **Sentry** | Error tracking | $26/mo |
| **Grafana** | Dashboards | Free |
| **Prometheus** | Metrics collection | Free |

### Key Metrics to Monitor

- Backend:
  - Request rate / latency
  - Error rate (4xx, 5xx)
  - LLM API usage/cost
  - Canton connection status
  - Job queue length

- Frontend:
  - Page load time
  - Core Web Vitals
  - API response time
  - Error rate

- Infrastructure:
  - CPU/memory usage
  - Database connections
  - Redis memory usage
  - Disk I/O

---

## Troubleshooting

### Backend won't connect to Canton
- Check `CANTON_SANDBOX_URL` is correct
- Verify Canton is running
- Check network/firewall rules
- Test with `curl http://canton-url:7575/v1/query`

### Frontend can't reach backend
- Check CORS configuration
- Verify `NEXT_PUBLIC_API_URL` is set
- Check backend is accessible
- Test with `curl https://api.yourdomain.com/health`

### Database connection failed
- Verify RDS instance is running
- Check security group allows backend IP
- Test with `psql` from backend container
- Check connection string format

### Redis connection failed
- Verify ElastiCache cluster is running
- Check security group allows backend IP
- Test with `redis-cli` from backend container

---

## Support

- **Documentation**: https://docs.daml.com
- **Canton Discord**: https://discord.gg/canton
- **Splice Support**: support@splice.dev
- **GitHub Issues**: https://github.com/BlockX-AI/Canton_Ginie/issues
