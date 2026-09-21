"""
JOUR 8 / 10 — Docker Monitoring
Pipeline ETL avec métriques, health checks et logs structurés.
"""

import os, sys, time, random, logging, json
import pandas as pd
from datetime import datetime, date
from sqlalchemy import create_engine, text

# ── Logging structuré JSON ────────────────────────────────────
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level'    : record.levelname,
            'service'  : 'etl_j8',
            'message'  : record.getMessage(),
        }
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
log = logging.getLogger(__name__)

DB_URL = (f"postgresql://{os.getenv('DB_USER','admin')}:"
          f"{os.getenv('DB_PASSWORD','secret123')}@"
          f"{os.getenv('DB_HOST','postgres')}:5432/"
          f"{os.getenv('DB_NAME','ventes_db')}")
OUTPUT_PATH = os.getenv('OUTPUT_PATH', '/app/output')


def get_engine():
    engine = create_engine(DB_URL)
    for i in range(15):
        try:
            with engine.connect() as c:
                c.execute(text("SELECT 1"))
            log.info("PostgreSQL connecté")
            return engine
        except Exception:
            log.warning(f"Attente PostgreSQL ({i+1}/15)")
            time.sleep(3)
    raise ConnectionError("PostgreSQL inaccessible")


def mesurer(func):
    """Décorateur qui mesure la durée d'une fonction."""
    def wrapper(*args, **kwargs):
        debut = time.time()
        try:
            result = func(*args, **kwargs)
            duree  = round(time.time() - debut, 3)
            log.info(f"{func.__name__} terminé en {duree}s")
            return result
        except Exception as e:
            duree = round(time.time() - debut, 3)
            log.error(f"{func.__name__} échoué après {duree}s : {e}")
            raise
    return wrapper


@mesurer
def extraire(engine, today):
    random.seed(int(today.strftime('%Y%m%d')))
    produits = ['Laptop Pro','Smartphone X','Tablette Air','Écouteurs BT']
    prix     = {'Laptop Pro':1200,'Smartphone X':650,'Tablette Air':450,'Écouteurs BT':120}
    vendeurs = ['Alice','Karim','Lucie','Thomas','Nadia']
    regions  = ['Île-de-France','PACA','Grand Est','Auvergne-Rhône-Alpes','Occitanie']

    rows = [{'date':today.isoformat(),'produit':(p:=random.choice(produits)),
             'vendeur':random.choice(vendeurs),'region':random.choice(regions),
             'montant':random.randint(1,10)*prix[p]}
            for _ in range(random.randint(20, 35))]

    df = pd.DataFrame(rows)
    with engine.begin() as conn:
        conn.execute(text(f"DELETE FROM ventes WHERE date='{today.isoformat()}'"))
    df['charge_le'] = datetime.now().isoformat()
    df.to_sql('ventes', engine, if_exists='append', index=False)
    log.info(f"Extract: {len(df)} lignes | CA: {df['montant'].sum():.0f}€")
    return df


@mesurer
def transformer(df):
    df = df.copy()
    df['marge'] = (df['montant'] * 0.42).round(2)
    df['taille'] = pd.cut(df['montant'], bins=[0,500,2000,float('inf')],
                          labels=['Petite','Moyenne','Grosse']).astype(str)
    log.info(f"Transform: marge={df['marge'].sum():.0f}€")
    return df


@mesurer
def sauvegarder_metriques(engine, df, duree_totale, today, statut):
    metriques = {
        'date'         : today.isoformat(),
        'ca_total'     : round(float(df['montant'].sum()), 2),
        'marge_totale' : round(float(df['marge'].sum()), 2),
        'nb_ventes'    : len(df),
        'duree_s'      : duree_totale,
        'statut'       : statut,
        'container_id' : os.getenv('HOSTNAME', 'local'),
        'calcule_le'   : datetime.now().isoformat(),
    }

    with engine.begin() as conn:
        conn.execute(text(f"DELETE FROM metriques WHERE date='{today.isoformat()}'"))
        conn.execute(text("""
            INSERT INTO metriques
            (date,ca_total,marge_totale,nb_ventes,duree_s,statut,container_id,calcule_le)
            VALUES (:date,:ca_total,:marge_totale,:nb_ventes,:duree_s,:statut,:container_id,:calcule_le)
        """), metriques)

    os.makedirs(OUTPUT_PATH, exist_ok=True)
    csv = f"{OUTPUT_PATH}/ventes_{today.isoformat()}.csv"
    df.to_csv(csv, index=False)
    log.info(f"Métriques sauvegardées | CSV: {csv}")
    return metriques


if __name__ == '__main__':
    started = time.time()
    today   = date.today()
    log.info("Pipeline ETL démarré")

    try:
        engine   = get_engine()
        df_raw   = extraire(engine, today)
        df_clean = transformer(df_raw)
        duree    = round(time.time() - started, 2)
        metriques= sauvegarder_metriques(engine, df_clean, duree, today, 'SUCCES')

        log.info(f"Pipeline terminé | CA={metriques['ca_total']}€ | durée={duree}s")
    except Exception as e:
        log.error(f"Pipeline échoué : {e}")
        sys.exit(1)
