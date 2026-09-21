CREATE TABLE IF NOT EXISTS ventes (
    id        SERIAL PRIMARY KEY,
    date      TEXT, produit VARCHAR(50),
    vendeur   VARCHAR(30), region VARCHAR(50),
    montant   NUMERIC(10,2), marge NUMERIC(10,2),
    taille    VARCHAR(10), charge_le TEXT
);
CREATE TABLE IF NOT EXISTS metriques (
    date         TEXT PRIMARY KEY,
    ca_total     NUMERIC(12,2), marge_totale NUMERIC(12,2),
    nb_ventes    INTEGER, duree_s NUMERIC(8,3),
    statut       VARCHAR(20), container_id VARCHAR(100),
    calcule_le   TEXT
);
