# DEV-PLAN.md — Model Router API

> **Produit :** API de routage intelligent pour LLMs
> **Objectif :** Économiser 80% des coûts LLM en routant vers le bon modèle
> **Business Model :** Freemium (100 req/jour) + Abonnements (10-200€/mois)

---

## Prototype Actuel (Bash)

**Fichier :** `tools/model-router.sh`

**Features :**
- ✅ Analyse de prompt (tokens, tools, task type)
- ✅ Routing intelligent 3 modèles (llama3.2:3b, phi3:mini, claude-sonnet-4)
- ✅ Logging des décisions
- ✅ Résultats : 100% pertinent, économies 80%

**Limitations :**
- ❌ Script bash (pas API)
- ❌ Pas d'authentification
- ❌ Pas de quota/comptage
- ❌ Pas de dashboard
- ❌ Pas de persistence

---

## Architecture API Cible

### Stack Technique

**Backend :**
- **FastAPI** (Python) — API REST moderne, rapide, async
- **Redis** — Cache, quota tracking, rate limiting
- **PostgreSQL** — Users, API keys, logs, métriques
- **Docker** — Déploiement isolé

**Frontend (Option v2) :**
- **React** ou **Svelte** — Dashboard admin
- **Chart.js** — Visualisation métriques
- **shadcn/ui** — Components UI

**Infra :**
- **Docker Compose** — Déploiement local/dev
- **Nginx** — Reverse proxy (prod)
- **Prometheus + Grafana** — Monitoring (option v2)

---

## API Endpoints

### 1. `POST /v1/route` — Router un prompt

**Request :**
```json
{
  "prompt": "Write a Python script to parse JSON files",
  "context": {
    "max_tokens": 1000,
    "tools_available": ["python", "bash"]
  }
}
```

**Response :**
```json
{
  "model": "ollama/phi3:mini",
  "reasoning": "Code generation task with medium complexity → local model",
  "confidence": 0.85,
  "estimated_cost": 0.001,
  "estimated_savings": 0.004
}
```

### 2. `POST /v1/generate` — Router + Générer

**Request :**
```json
{
  "prompt": "Summarize this log file...",
  "generate": true
}
```

**Response :**
```json
{
  "model": "ollama/llama3.2:3b",
  "reasoning": "...",
  "generation": "The log file shows...",
  "tokens_used": 234,
  "cost": 0.0002
}
```

### 3. `GET /v1/stats` — Statistiques utilisateur

**Response :**
```json
{
  "requests_today": 45,
  "requests_month": 1234,
  "quota_remaining": 55,
  "total_saved": 12.50,
  "models_used": {
    "llama3.2:3b": 30,
    "phi3:mini": 12,
    "claude-sonnet-4": 3
  }
}
```

### 4. `GET /v1/health` — Health check

**Response :**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "models": {
    "ollama": "connected",
    "openrouter": "connected",
    "anthropic": "connected"
  }
}
```

---

## Features MVP (v1.0 - Semaine 1)

### Must Have ( pour lancer)

- [x] Algorithme de routing (déjà fait)
- [ ] API REST `/v1/route`
- [ ] Authentification API key
- [ ] Quota tracking (Redis)
- [ ] Basic logging
- [ ] Documentation README
- [ ] Docker compose pour dev

### Nice to Have (si le temps)

- [ ] Endpoint `/v1/generate` (route + generate)
- [ ] Dashboard simple (une page HTML)
- [ ] Monitoring basique (Prometheus)

### Later (v2.0)

- [ ] Web dashboard complet
- [ ] User management
- [ ] Usage analytics
- [ ] Auto-optimization des règles de routing
- [ ] Support de plus de modèles

---

## Pricing & Plans

### Free Tier
- **100 requests/jour**
- **1 API key**
- **Community support**
- **Rate limiting : 10 req/min**

### Hobby - 10€/mois
- **10,000 requests/mois**
- **5 API keys**
- **Email support**
- **Rate limiting : 100 req/min**
- **Basic analytics**

### Pro - 50€/mois
- **100,000 requests/mois**
- **20 API keys**
- **Priority support**
- **Rate limiting : 1000 req/min**
- **Advanced analytics**
- **Custom routing rules**

### Enterprise - 200€/mois
- **1,000,000 requests/mois**
- **Unlimited API keys**
- **Dedicated support**
- **Custom rate limits**
- **SLA 99.9%**
- **On-premise deployment option**

---

## Database Schema

### users
```sql
CREATE TABLE users (
  id UUID PRIMARY KEY,
  email VARCHAR(255) UNIQUE,
  plan VARCHAR(50) DEFAULT 'free',
  api_key_hash VARCHAR(255),
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

### quotas
```sql
CREATE TABLE quotas (
  user_id UUID REFERENCES users(id),
  month VARCHAR(7) -- '2026-03'
  requests_used INTEGER DEFAULT 0,
  requests_limit INTEGER,
  PRIMARY KEY (user_id, month)
);
```

### logs
```sql
CREATE TABLE logs (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  prompt_hash VARCHAR(255),
  model_selected VARCHAR(100),
  reasoning TEXT,
  tokens_saved INTEGER,
  cost_saved DECIMAL(10, 4),
  timestamp TIMESTAMP
);
```

---

## Development Roadmap

### Jour 1 (Demain)
- [ ] Créer repo GitHub
- [ ] Setup FastAPI project
- [ ] Implémenter `/v1/route` endpoint
- [ ] Implémenter auth API key
- [ ] Tests unitaires

### Jour 2
- [ ] Setup Redis pour quotas
- [ ] Implémenter quota tracking
- [ ] Rate limiting
- [ ] Tests d'intégration

### Jour 3
- [ ] Docker compose setup
- [ ] Documentation complète
- [ ] README avec exemples
- [ ] Déploiement staging

### Jour 4
- [ ] Tests de charge
- [ ] Bugfixes
- [ ] Performance tuning
- [ ] Documentation finale

### Jour 5
- [ ] Beta release
- [ ] Feedback early adopters
- [ ] Ajustements pricing/features
- [ ] Préparation Stripe

---

## Success Metrics

**Technique :**
- API response time < 100ms (sans génération)
- 99.9% uptime
- Routing accuracy > 95%

**Business :**
- 100 free users (1ère semaine)
- 10 paying users (1er mois)
- 1000€/mois revenus (3ème mois)

**Product :**
- Feedback positif utilisateurs
- < 5% churn rate
- Feature requests pertinentes

---

## Risks & Mitigations

### Risque 1 : Concurrents avec plus de features
- **Mitigation :** Se différencier sur "local first" + prix agressif

### Risque 2 : Routing pas assez précis
- **Mitigation :** A/B testing, feedback loop auto, ML-based routing v2

### Risque 3 : Abandon free users sans payer
- **Mitigation :** Valeur ajoutée dans plans payants (analytics, custom rules)

### Risque 4 : Échec technique (latence, bugs)
- **Mitigation :** Tests rigoureux, beta limitée, support réactif

---

## Next Actions

1. ✅ Attendre résultats Specter (recherche concurrentielle)
2. ⏳ Valider le business model (est-ce que ça se vend ?)
3. ⏳ Si validé → commencer développement Jour 1 demain
4. ⏳ Si pas validé → pivoter vers autre produit

---

**Dernière mise à jour :** 2026-03-22
**Statut :** En attente validation marché (Specter en cours)
