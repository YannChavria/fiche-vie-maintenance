"""Génère un jeu EXEMPLE (synthétique, anonymisé) au format CSV.
positions.csv, cartes.csv, cartes_ref.csv, transferts.csv, tests.csv

Schémas de séjour modélisés :
  - NORMAL        : arrivée N1 (verte) -> pose -> service -> dépose -> départ N2 (rouge)
  - SWITCH (jour même) : pose -> permutation directe le MÊME JOUR vers une autre rame/baie
                    (sans atelier) -> service -> ...
  - PERMUTATION DIAG. : pose Baie A -> permutation directe Baie B (sans N2) -> service -> ...
  - RÉPARATION INEFFICACE : montage court -> permutation A/B -> défaut persistant -> retour N2.
"""
import csv, random
from datetime import datetime, timedelta

random.seed(7)
OUT = "/mnt/user-data/outputs"
DRAWER = "TIROIR TR-0142"
LIFE_START, LIFE_END = datetime(2013,4,5), datetime(2021,3,1)
POSITIONS = ["BAIE_A","BAIE_B"]
CARDS = ["Carte UC","Carte ALIM","Carte E/S","Carte COM","Carte SUP"]   # config complète du tiroir
TRAINS = [f"TR-{n}" for n in (101,108,112,119,123,130,134,141,147,152)]
STOCKS = ["MAG-10","MAG-11","MAG-12","STOCK-A"]
CODES_N1 = ["RA","RA","RA","EE","MO","CO"]
CODES_N3 = ["RA","EE","CO","MO"]
SYMPT = ["défaut système embarqué","défaut unité de gestion",
         "anomalie capteur embarqué","indisponibilité fonction principale"]
dt  = lambda d: d.strftime("%Y-%m-%d")
dtm = lambda d: d.strftime("%Y-%m-%d %H:%M")
seq = 1000
def ot(p):
    global seq; seq += 7; return f"{p}_OT_{seq}"
def htime(d): return d + timedelta(hours=random.randint(7,16), minutes=random.randint(0,59))
other = lambda b: "BAIE_B" if b == "BAIE_A" else "BAIE_A"

pos_rows, crt_rows, trf_rows, tst_rows = [], [], [], []
def addpos(baie, train, ps, dp, code, desc, com):
    pos_rows.append([DRAWER, baie, train, dt(ps), "" if dp is None else dt(dp), ot("N1"), code, desc, com])
def addcard(when, nb=None):
    for _ in range(nb if nb else random.randint(1,2)):
        card = random.choice(CARDS)
        dpd = when + timedelta(days=random.randint(2,30)); rpd = dpd + timedelta(days=random.randint(4,21))
        cc = random.choice(CODES_N3)
        crt_rows.append([DRAWER,card,dt(dpd),dt(rpd),ot("N3"),cc,
                         f"Atelier électronique (N3) - {card}",
                         "Échange composant (R/C/IC)" if cc in ("RA","EE") else "Contrôle et remise en état"])
n_test = 0
def addtest(when, force=None):
    global n_test
    res = force if force else ("KO" if random.random() < 0.22 else "RAS")
    tst_rows.append([DRAWER, dtm(htime(when)), res,
                     "Tiroir conforme au banc (RAS)" if res == "RAS"
                     else "Tiroir non conforme au banc (KO) - remise en réparation"])
    n_test += 1

arrival = LIFE_START
plan = ["normal","switch","failed","diag","normal","diag","switch","failed"]
ci = 0
while arrival < LIFE_END:
    mag, train, baie = random.choice(STOCKS), random.choice(TRAINS), random.choice(POSITIONS)
    trf_rows.append([DRAWER, dtm(htime(arrival)), "retour", f"STOCK {mag}  →  N1 (atelier ligne)"])  # verte
    pose = arrival + timedelta(days=random.randint(2,15))
    if pose >= LIFE_END: break

    if ci < len(plan):
        typ = plan[ci]
    else:
        r = random.random()
        typ = "failed" if r<0.15 else ("diag" if r<0.32 else ("switch" if r<0.45 else "normal"))
    ci += 1
    failed, diag, switch = typ=="failed", typ=="diag", typ=="switch"

    serv1 = random.randint(8,40) if failed else random.randint(60,430)
    depose1 = pose + timedelta(days=serv1)
    if depose1 >= LIFE_END:
        addpos(baie, train, pose, None, "RA", f"Pose {DRAWER} en {baie} sur {train}", "Séjour en cours."); break

    if switch:
        b2 = other(baie); train2 = random.choice([t for t in TRAINS if t != train])
        addpos(baie, train, pose, depose1, "PE", f"Séjour {DRAWER} en {baie} sur {train}",
               f"SWITCH le jour même : permutation directe {train}/{baie} → {train2}/{b2} (sans passage atelier).")
        pose2 = depose1                                  # MÊME JOUR (switch rapide)
        depose2 = pose2 + timedelta(days=random.randint(60,400))
        if depose2 >= LIFE_END:
            addpos(b2, train2, pose2, None, "RA", f"Pose {DRAWER} en {b2} sur {train2}", "Séjour en cours (après switch)."); break
        addpos(b2, train2, pose2, depose2, random.choice(CODES_N1), f"Séjour {DRAWER} en {b2} sur {train2}",
               "Après switch le jour même, service nominal.")
        final_depose, red_label = depose2, f"{train2}  →  Atelier N3 (défaut)"
    elif failed or diag:
        b2 = other(baie)
        addpos(baie, train, pose, depose1, "PE", f"Séjour {DRAWER} en {baie} sur {train}",
               f"Défaut signalé ; permutation diagnostic {baie}→{b2} directe (sans passage atelier) pour isoler tiroir vs baie.")
        pose2 = depose1 + timedelta(days=random.randint(0,2))
        depose2 = pose2 + timedelta(days=(random.randint(5,30) if failed else random.randint(60,400)))
        if depose2 >= LIFE_END:
            addpos(b2, train, pose2, None, "RA", f"Pose {DRAWER} en {b2} sur {train}", "Séjour en cours (après permutation diagnostic)."); break
        if failed:
            addpos(b2, train, pose2, depose2, "RA", f"Séjour {DRAWER} en {b2} sur {train}",
                   "Défaut toujours présent après permutation : le défaut SUIT le tiroir → retour atelier (réparation précédente inefficace).")
            red_label = f"{train}  →  Atelier N3 (défaut persistant - réparation inefficace)"
        else:
            addpos(b2, train, pose2, depose2, random.choice(CODES_N1), f"Séjour {DRAWER} en {b2} sur {train}",
                   "Après permutation : fonctionnement nominal (défaut imputé à la baie/au câblage), puis dépose ultérieure.")
            red_label = f"{train}  →  Atelier N3 (défaut)"
        final_depose = depose2
    else:
        addpos(baie, train, pose, depose1, random.choice(CODES_N1), f"Séjour {DRAWER} en {baie} sur {train}",
               f"Dépose pour {random.choice(SYMPT)} ; investigation atelier.")
        final_depose, red_label = depose1, f"{train}  →  Atelier N3 (défaut)"

    departure = final_depose + timedelta(days=random.randint(1,10))
    trf_rows.append([DRAWER, dtm(htime(departure)), "defaut", red_label])           # rouge
    if failed: addcard(departure, nb=1)
    elif random.random() < 0.7: addcard(departure)
    next_arrival = departure + timedelta(days=random.randint(20,120))
    test_date = max(departure + timedelta(days=5), next_arrival - timedelta(days=random.randint(2,12)))
    addtest(test_date, force=("KO" if n_test == 0 else None))
    arrival = next_arrival

def write(name, header, rows):
    with open(f"{OUT}/{name}","w",newline="",encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)
write("positions.csv",  ["drawer","position","train","date_pose","date_depose","ot","code","description","commentaire"], pos_rows)
write("cartes.csv",     ["drawer","carte","date_depose","date_repose","ot","code","description","commentaire"], crt_rows)
write("cartes_ref.csv", ["drawer","carte","ordre"], [[DRAWER,c,i] for i,c in enumerate(CARDS,1)])
write("transferts.csv", ["drawer","datetime","sens","label"], trf_rows)
write("tests.csv",      ["drawer","datetime","resultat","commentaire"], tst_rows)
print("positions:",len(pos_rows),"| cartes(répa):",len(crt_rows),"| cartes_ref:",len(CARDS),
      "| transferts:",len(trf_rows),"| tests:",len(tst_rows))
