# 📡 Jour 8 / 10 — Docker : Monitoring

> **Série : 10 Days of Docker** · Jour 8/10  
> Concepts : Health checks avancés · Logs structurés JSON · docker stats · Métriques pipeline · Endpoint /health

---

## 📁 Fichiers du projet

```
day-08-monitoring/
│
├── docker-compose-j8.yml    ← Stack avec health checks + logging config
├── Dockerfile.j8            ← Multi-stage build
├── requirements_j8.txt      ← Dépendances
├── sql_j8/
│   └── init.sql             ← Tables ventes + metriques
├── app_j8/
│   ├── etl_monitoring.py    ← Pipeline avec logs JSON et métriques
│   └── health_server.py     ← Serveur HTTP /health et /metrics
├── output_j8/               ← CSV de sortie
└── README.md
```

---

## 🚀 ÉTAPE 1 — Préparer la structure

```bash
mkdir -p jour8-docker/app_j8
mkdir -p jour8-docker/sql_j8
mkdir -p jour8-docker/output_j8
cd jour8-docker/

# Copier les fichiers :
# docker-compose-j8.yml  → racine
# Dockerfile.j8          → racine
# requirements_j8.txt    → racine
# init_j8.sql            → sql_j8/init.sql
# etl_monitoring.py      → app_j8/etl_monitoring.py
# health_server.py       → app_j8/health_server.py
```

---

## 🔑 ÉTAPE 2 — Health checks avancés

```yaml
# Dans docker-compose-j8.yml
postgres:
  healthcheck:
    test    : ["CMD-SHELL", "pg_isready -U admin -d ventes_db"]
    interval: 10s       # vérifie toutes les 10s
    timeout : 5s        # abandon si pas de réponse en 5s
    retries : 5         # 5 échecs → unhealthy
    start_period: 10s   # délai avant le 1er check (démarrage)

healthcheck-api:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8081/health"]
    interval: 30s
    retries : 3
```

**Statuts possibles :**
```
starting  → dans le start_period
healthy   → dernier check OK
unhealthy → N échecs consécutifs
```

---

## 🚀 ÉTAPE 3 — Lancer la stack

```bash
docker-compose -f docker-compose-j8.yml up --build -d

# Suivre les logs
docker-compose -f docker-compose-j8.yml logs -f

# Voir les statuts health
docker-compose -f docker-compose-j8.yml ps
```

---

## 🔑 ÉTAPE 4 — Logs structurés JSON

```python
class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            'timestamp': datetime.now().isoformat(),
            'level'    : record.levelname,
            'service'  : 'etl_j8',
            'message'  : record.getMessage(),
        })

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())
```

Chaque ligne de log est un objet JSON — parseable par n'importe quel outil de monitoring.

```bash
# Voir les logs JSON
docker logs etl_j8

# Filtrer les erreurs avec jq
docker logs etl_j8 | jq 'select(.level == "ERROR")'

# Filtrer par service
docker logs etl_j8 | jq 'select(.service == "etl_j8")'
```

---

## 🔑 ÉTAPE 5 — Configuration des logs Docker

```yaml
# Dans docker-compose-j8.yml
etl:
  logging:
    driver: "json-file"    # driver par défaut
    options:
      max-size: "5m"       # rotation à 5MB
      max-file: "2"        # garder 2 fichiers max
```

```bash
# Voir les logs d'un conteneur
docker logs etl_j8
docker logs etl_j8 --tail 50     # 50 dernières lignes
docker logs etl_j8 --since 1h    # depuis 1 heure
docker logs etl_j8 -f            # en temps réel

# Localiser les fichiers de logs sur l'hôte
docker inspect etl_j8 | grep LogPath
```

---

## 🔑 ÉTAPE 6 — Endpoint /health et /metrics

```bash
# Tester le health check
curl http://localhost:8081/health

# Réponse si tout va bien :
# {"status": "healthy", "db": "connected", "timestamp": "2024-01-01T12:00:00"}

# Tester les métriques
curl http://localhost:8081/metrics

# Réponse :
# {"nb_ventes": 28, "ca_total": 19200.0, "timestamp": "..."}
```

---

## 🔑 ÉTAPE 7 — docker stats (métriques en temps réel)

```bash
# Voir la consommation CPU/RAM/réseau de tous les conteneurs
docker stats

# Résultat :
# CONTAINER       CPU %   MEM USAGE / LIMIT   NET I/O       BLOCK I/O
# etl_j8          0.01%   45MiB / 7.7GiB      1.2kB / 800B  0B / 0B
# postgres_j8     0.1%    32MiB / 7.7GiB      2.1kB / 1.5kB 0B / 8.19kB

# Stats d'un seul conteneur (sans streaming)
docker stats etl_j8 --no-stream

# Format JSON
docker stats --no-stream --format '{"container":"{{.Name}}","cpu":"{{.CPUPerc}}","mem":"{{.MemUsage}}"}'
```

---

## 🔑 ÉTAPE 8 — Décorateur de mesure des durées

```python
def mesurer(func):
    def wrapper(*args, **kwargs):
        debut = time.time()
        try:
            result = func(*args, **kwargs)
            duree  = round(time.time() - debut, 3)
            log.info(f"{func.__name__} terminé en {duree}s")
            return result
        except Exception as e:
            log.error(f"{func.__name__} échoué après {round(time.time()-debut,3)}s : {e}")
            raise
    return wrapper

@mesurer
def extraire(engine, today):
    ...

@mesurer
def transformer(df):
    ...
```

---

## 🚀 ÉTAPE 9 — Vérifier les métriques en base

```bash
docker exec -it postgres_j8 psql -U admin -d ventes_db

-- Métriques des runs
SELECT date, ca_total, nb_ventes, duree_s, statut
FROM metriques ORDER BY date DESC;

-- Ventes chargées
SELECT date, COUNT(*), SUM(montant) AS ca
FROM ventes GROUP BY date;

\q
```

---

## 🔑 ÉTAPE 10 — Politique de restart

```yaml
etl:
  restart: on-failure:3   # relance max 3 fois en cas d'échec

# Autres valeurs :
# restart: "no"           → jamais (défaut)
# restart: always         → toujours (même si arrêté manuellement)
# restart: unless-stopped → toujours sauf si arrêté manuellement
# restart: on-failure     → seulement en cas d'erreur
```

---

## 💡 Récap — Outils de monitoring Docker

| Outil | Usage |
|-------|-------|
| `docker stats` | CPU, RAM, réseau en temps réel |
| `docker logs` | Logs des conteneurs |
| `docker inspect` | Config complète d'un conteneur |
| `healthcheck` | Vérifier qu'un service est prêt |
| Endpoint /health | Health check HTTP exposé |
| Logs JSON | Parseable par des outils externes |

---



---

⭐ **Si ce projet t'aide, mets une étoile !**
