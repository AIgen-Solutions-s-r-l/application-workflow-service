# Kubernetes Deployment Guide

This directory contains Kubernetes manifests for deploying the Application Manager Service using Kustomize.

## Directory Structure

```
k8s/
├── base/                    # Base resources (shared across all environments)
│   ├── kustomization.yaml
│   ├── namespace.yaml
│   ├── serviceaccount.yaml
│   ├── deployment.yaml      # API deployment
│   ├── worker-deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── hpa.yaml             # Horizontal Pod Autoscaler
│   └── pdb.yaml             # Pod Disruption Budget
├── overlays/
│   ├── development/         # Development environment
│   ├── staging/             # Staging environment
│   └── production/          # Production environment
└── README.md
```

## Prerequisites

- Kubernetes cluster (1.25+)
- kubectl configured
- Kustomize (built into kubectl 1.14+)
- MongoDB, RabbitMQ, and Redis accessible from the cluster

## Quick Start

### Development

```bash
# Preview what will be deployed
kubectl kustomize k8s/overlays/development

# Deploy
kubectl apply -k k8s/overlays/development
```

### Staging

```bash
kubectl apply -k k8s/overlays/staging
```

### Production

```bash
# First, update secrets with real values
kubectl create secret generic application-manager-secrets \
  --namespace=application-manager \
  --from-literal=SECRET_KEY=$(openssl rand -base64 32) \
  --from-literal=MONGODB="mongodb://user:pass@mongodb:27017/resumes" \
  --from-literal=RABBITMQ_URL="amqp://user:pass@rabbitmq:5672/" \
  --from-literal=REDIS_URL="redis://:password@redis:6379/0"

# Deploy
kubectl apply -k k8s/overlays/production
```

## Configuration

### Environment-Specific Settings

| Setting | Development | Staging | Production |
|---------|-------------|---------|------------|
| Replicas | 1 | 2 | 3-20 (HPA) |
| CPU Request | 50m | 100m | 200m |
| CPU Limit | 200m | 500m | 1000m |
| Memory Request | 128Mi | 256Mi | 512Mi |
| Memory Limit | 256Mi | 512Mi | 1Gi |
| Debug | true | false | false |
| Log Level | DEBUG | INFO | INFO |
| Cache | disabled | enabled | enabled |
| Rate Limit | disabled | enabled | enabled |

### Secrets Management

**Important**: Never commit real secrets to the repository!

For production, use one of these approaches:

1. **kubectl create secret** (shown above)
2. **Sealed Secrets** (Bitnami)
3. **External Secrets Operator** (AWS Secrets Manager, Vault, etc.)
4. **SOPS** with age or GPG encryption

Example with External Secrets Operator:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: application-manager-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: ClusterSecretStore
  target:
    name: application-manager-secrets
  data:
    - secretKey: SECRET_KEY
      remoteRef:
        key: secret/app-manager
        property: secret_key
```

## Scaling

### Horizontal Pod Autoscaler

The HPA is configured to scale based on:
- CPU utilization (target: 70%)
- Memory utilization (target: 80%)

```bash
# View HPA status
kubectl get hpa -n application-manager

# Manual scaling (overrides HPA temporarily)
kubectl scale deployment application-manager --replicas=5 -n application-manager
```

### Worker Scaling

Workers don't have an HPA by default. Scale manually based on queue depth:

```bash
kubectl scale deployment application-worker --replicas=5 -n application-manager
```

## Health Checks

The deployment includes three types of probes:

1. **Startup Probe**: `/health/live` - Allows slow startup
2. **Liveness Probe**: `/health/live` - Restarts unhealthy pods
3. **Readiness Probe**: `/health/ready` - Removes from service if not ready

```bash
# Check pod health
kubectl describe pod -l app.kubernetes.io/name=application-manager -n application-manager
```

## Monitoring

### Prometheus Metrics

Pods are annotated for Prometheus scraping:

```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8009"
  prometheus.io/path: "/metrics"
```

### Logs

```bash
# API logs
kubectl logs -l app.kubernetes.io/component=api -n application-manager -f

# Worker logs
kubectl logs -l app.kubernetes.io/component=worker -n application-manager -f
```

## Rolling Updates

The deployment is configured for zero-downtime updates:

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0
```

To update:

```bash
# Update image tag
kubectl set image deployment/application-manager \
  api=application-manager-service:1.2.0 \
  -n application-manager

# Or use kustomize with new tag
cd k8s/overlays/production
kustomize edit set image application-manager-service=ghcr.io/your-org/application-manager-service:1.2.0
kubectl apply -k .
```

## Troubleshooting

### Pod not starting

```bash
# Check events
kubectl get events -n application-manager --sort-by='.lastTimestamp'

# Check pod status
kubectl describe pod <pod-name> -n application-manager
```

### Database connection issues

```bash
# Exec into pod
kubectl exec -it <pod-name> -n application-manager -- sh

# Test MongoDB connection
python -c "from pymongo import MongoClient; print(MongoClient('$MONGODB').server_info())"
```

### Check resource usage

```bash
kubectl top pods -n application-manager
```

## Cleanup

```bash
# Remove specific environment
kubectl delete -k k8s/overlays/development

# Remove everything including namespace
kubectl delete namespace application-manager
```
