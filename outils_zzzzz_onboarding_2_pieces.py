"""Almaval - onboarding porte en Python sous gestion@ : registre des pieces contractuelles, 27.09.2026.

Moteur de nuit passageQuotidienDesPieces (fichier « 14 Pieces
contractuelles », 6 h) du projet Apps Script « Almaval - RH - Onboarding des
collaborateurs », transcrit a l'identique sur le socle
outils_zzzzz_onboarding_0_socle, avec les deux surcharges qui l'atteignent :

  - pc_libelleDuSousDossier_ de « 47 Sous-dossiers du dossier RH par
    numero » : un sous-dossier est reconnu par son NUMERO de tete, et seuls
    les numeros 1, 2, 3, 5 et 7 entrent dans l'inventaire ;
  - pc_personneDuDossier_ de « 48 Dossiers parents au nom d usage » : le
    nom porte par le dossier (avant le premier « - ») est traduit dans le
    nom du registre des engagements par l'index des appellations
    (Registre - Personnes, Registre - Engagements, Saisie - Collaborateurs).

Aucun autre fichier (03, 46, 61, 65, 99) ne redeclare ni n'enveloppe une
fonction de ce moteur ; verifie sur ORDRE.txt, DECLARATIONS_MULTIPLES.txt
et REASSIGNATIONS.txt.

CE QUE FAIT UN PASSAGE, dans cet ordre :
  1. lit « Registre - Engagements » d'Almaval - Collaborateurs - Effectif
     (cle, nom, type de contrat, objet du contrat) ;
  2. liste les sous-dossiers directs des trois populations du Drive
     (Internes, Externes, Anciens), tries par population puis par nom ;
  3. s'assure de l'onglet « Registre - Pièces » du meme classeur Effectif
     (creation, vingt et une colonnes, ligne d'en-tetes) et indexe ses
     lignes par « cle engagement | identifiant Drive », en gardant les six
     colonnes de lecture manuelle (Lue le ... Heures facturables lues) ;
  4. dossier par dossier : rattache le dossier a un ou plusieurs
     engagements (exact, approche par jetons du nom, ou aucun), ramasse
     les fichiers a la racine, ceux des sous-dossiers reconnus et ceux de
     leurs propres sous-dossiers (un niveau de plus), range les pieces de
     regime (Contrat, Avenant, Mandat) selon la regle du 13.09.2026, pose
     les anomalies, et ecrit une ligne par (engagement, piece) : mise a
     jour en place si la cle composite existe, ajout sinon ;
  5. cloture : retire les lignes qui ne portent pas le jeton du passage et
     les lignes « Aucune piece », en ajoute une par engagement sans aucune
     piece, trie par nom puis cle puis date decroissante, reecrit tout
     l'onglet des la ligne 2 et retire les lignes et colonnes en trop.

Memoire (remplacant de PropertiesService) : PC_PASSAGE (jeton du type
P20260927-0636) et PC_CURSEUR (rang du prochain dossier).

Sans confirmer, passage() lit tout, calcule tout et rend les lignes que le
registre recevrait (en-tetes, mises a jour, ajouts, cloture), sans rien
ecrire ; avec confirmer, il ecrit et rend le meme compte rendu plus le
bilan d'origine (resultat). Ce moteur n'ecrit dans aucune fiche et ne met
aucun courriel en file. Avec initiales=XxYy, seuls les dossiers de cette
personne sont parcourus et la cloture n'a pas lieu, puisqu'elle retirerait
toutes les autres lignes.

Outil : onboarding_pieces(confirmer, initiales, exemples).
Pont : lieux_cycle avec le sujet « action:onboarding_pieces [confirmer]
[initiales=XxYy] [exemples=50] ».
"""

import datetime
import functools
import re
import time
import unicodedata

from main import mcp, tolerant

import outils_lieux
from outils_zzzzz_distributeur import (
    Date, FORMAT_DATE_HEURE, _assurer_dimensions, _batch, _classeur, _creer_onglet, _executer,
    _lire_grille, _onglet, _oublier, _requete_cellules, _requete_effacer,
)
from outils_zzzzz_onboarding_0_socle import (
    pont_de_fond,
    CFG, CFG_MUT, COL, ID_EFFECTIF, TYPE_DOSSIER, _verrou, appellation_nom_prenom_av, date_de, drive,
    lire_onglet, lire_onglet_de, maintenant, memoire_ecrire, memoire_lire, nom_de_fichier, normaliser,
    serial_de, texte,
)

# ------------------------------------------------ 14 Pieces contractuelles

PC = {
    "ID_EFFECTIF": ID_EFFECTIF,
    "ONGLET_ENGAGEMENTS": "Registre - Engagements",
    "ONGLET_CIBLE": "Registre - Pièces",
    "POPULATIONS": [
        {"nom": "Internes", "id": "1Sy_unbBC0kwtT7NntFjCEBR-S-R-hWpW"},
        {"nom": "Externes", "id": "1kqnXgvOhS_ukS1Tm2EavASXVgA9zXgP1"},
        {"nom": "Anciens", "id": "157LVJQnsypEVoG8_b4CtdEdeG7Nv1kle"},
    ],
    "LIBELLE_RACINE": "Racine du dossier",
    "BUDGET_MS": 40000,
    "BUDGET_NUIT_MS": 280000,
    "TOURS_MAX": 20,
    "CLE_CURSEUR": "PC_CURSEUR",
    "CLE_PASSAGE": "PC_PASSAGE",
    "ENTETES": [
        "Clé engagement", "Nom prénom", "Population", "Sous-dossier",
        "Nature", "Titre de la pièce", "Format", "Signée",
        "Date de la pièce", "Rang du régime", "Modifiée le",
        "Identifiant", "Lien",
        "Lue le", "Clause verbatim", "Taux lu", "Date d'effet lue",
        "Jours et lieux lus", "Heures facturables lues",
        "Anomalie", "Vue le",
    ],
}
PC_COL_LECTURE_DEBUT = 14
PC_COL_LECTURE_FIN = 19
PC_NATURES_DE_REGIME = ["Contrat", "Avenant", "Mandat"]
LARGEUR = len(PC["ENTETES"])

# « 47 » : les sous-dossiers qui entrent dans l'inventaire, par numero de tete.
SR_LIBELLES_PIECES = {
    1: "1. Dossier candidature",
    2: "2. Documents contractuels",
    3: "3. Documents administratifs",
    5: "5. Compétences et formations",
    7: "7. Fin des relations",
}

_ACCENTS_JS = re.compile("[̀-ͯ]")


def pc_norm(valeur):
    t = "" if valeur is None else texte(valeur)
    t = _ACCENTS_JS.sub("", unicodedata.normalize("NFD", t)).lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def pc_jetons(valeur):
    n = pc_norm(valeur)
    if n == "":
        return []
    return [t for t in n.split(" ") if len(t) > 1]


def pc_date_du_titre(titre):
    m = re.match(r"^(\d{4})(\d{2})(\d{2})", str(titre or "").strip())
    if not m:
        return {"tri": "", "affichage": ""}
    a, mo, j = m.group(1), m.group(2), m.group(3)
    if not (1 <= int(mo) <= 12) or not (1 <= int(j) <= 31):
        return {"tri": "", "affichage": ""}
    return {"tri": a + mo + j, "affichage": j + "." + mo + "." + a}


def pc_nature_du_titre(titre):
    t = pc_norm(titre)
    if re.search(r"(rupture|resiliation|reisiliation|licenciement|demission|fin de contrat|fin des relations|certificat de travail|attestation de fin)", t):
        return "Fin de relation"
    if re.search(r"(pre engagement|preengagement|promesse d engagement|lettre d intention)", t):
        return "Pré-engagement"
    if re.search(r"(autorisation de pratique|autorisation de pratiquer|autorisation de facturer|droit de pratique|\bddp\b)", t):
        return "Autorisation"
    if re.search(r"(psyreg|medreg|ofsp|\bbag\b|eidgenossenschaft|registre des professions)", t):
        return "Extrait de registre"
    if re.search(r"(diplome|diploma|bachelor|\bmaster\b|licence|\bmas\b|\bcas\b|\bdas\b|\bfmh\b|\bfsp\b|titre postgrade|titre de specialiste|specialise|doctorat|docteur)", t):
        return "Diplôme ou titre"
    if re.search(r"(attestation de formation|attestation de supervision|heures de supervision|releve de notes)", t):
        return "Attestation de formation"
    if re.search(r"(\bcv\b|curriculum|lettre de motivation|candidature)", t):
        return "Candidature"
    if re.search(r"(courriel|e mail|email|\bmail\b|fil de|echange de|reponse de|reponse a)", t):
        return "Lettre"
    if re.search(r"\bavenant\b", t):
        return "Avenant"
    if re.search(r"contrat de mandat", t) or (re.search(r"\bmandat\b", t) and re.search(r"\bcontrat\b", t)):
        return "Mandat"
    if re.search(r"\bcontrat\b", t) and re.search(r"(encadrement|encadrant|encadrante|supervision|superviseur|superviseuse)", t):
        return "Mandat"
    if re.search(r"\bmandat\b", t):
        return "Mandat"
    if re.search(r"\bcontrat\b", t):
        return "Contrat"
    if re.search(r"\bconvention\b", t):
        return "Convention"
    if re.search(r"cahier des charges", t):
        return "Cahier des charges"
    if re.search(r"conditions generales", t):
        return "Conditions générales"
    if re.search(r"\blettre\b", t):
        return "Lettre"
    if re.search(r"\bbail\b|sous location", t):
        return "Contrat"
    return "Autre"


def pc_format_du_type(mime):
    m = str(mime or "")
    if m == "application/pdf":
        return "PDF"
    if m == "application/vnd.google-apps.document":
        return "Document"
    if "wordprocessingml" in m or m == "application/msword":
        return "Word"
    if m.startswith("image/"):
        return "Image"
    if m == "application/vnd.google-apps.spreadsheet":
        return "Classeur"
    return "Autre"


def pc_est_signee(titre):
    for j in pc_norm(titre).split(" "):
        if j in ("signe", "signes", "signee", "signees"):
            return "x"
    return ""


def pc_lien_de_la_piece(ident, mime):
    if str(mime) == "application/vnd.google-apps.document":
        return "https://docs.google.com/document/d/" + ident + "/edit"
    if str(mime) == "application/vnd.google-apps.spreadsheet":
        return "https://docs.google.com/spreadsheets/d/" + ident + "/edit"
    return "https://drive.google.com/file/d/" + ident + "/view"


# ------------------------------------------------ 47 : le sous-dossier par son numero

def numero_du_sous_dossier_sr(nom):
    """numeroDuSousDossierSr_ : le numero de tete, zero s'il n'y en a pas."""
    t = str(nom or "").strip()
    m = re.match(r"^(\d{1,2})\s*[.)\-]\s*(.+)$", t) or re.match(r"^(\d{1,2})\s+(.+)$", t)
    return int(m.group(1)) if m else 0


def pc_libelle_du_sous_dossier(nom):
    """Version gagnante (« 47 ») : seuls les numeros de SR_LIBELLES_PIECES entrent."""
    numero = numero_du_sous_dossier_sr(nom)
    if not numero:
        return ""
    return SR_LIBELLES_PIECES.get(numero, "")


# ------------------------------------------------ 48 : l'index des appellations

def _s(v):
    """String(v || '').trim() d'Apps Script sur une valeur de cellule."""
    return texte(v).strip()


def _id_depuis_url(url):
    """idDepuisUrl_ (« 05 ») : le premier bloc de 25 caracteres ou plus, l'url a defaut."""
    u = str(url or "")
    if not u:
        return ""
    m = re.search(r"[-\w]{25,}", u)
    return m.group(0) if m else u


def index_des_appellations_dp():
    """indexDesAppellationsDp_ : trois cartes acceptant la cle du nom d'usage,
    de l'etat civil ou du nom du registre des engagements. Construit une
    fois par passage (cache de _lire_grille)."""
    idx = {"usageParCle": {}, "etatCivilParCle": {}, "nomRegistreParCle": {}, "usageParInitiales": {}, "paires": 0}
    personnes = {}
    try:
        registre = lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_PERSONNES"], avec_calculees=False)
        for p in registre.lignes:
            init = _s(p.get("Initiales"))
            if not init or normaliser(init) in personnes:
                continue
            personnes[normaliser(init)] = p
    except Exception:  # noqa: BLE001
        pass
    noms_du_registre = {}
    try:
        engagements = lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_ENGAGEMENTS"], avec_calculees=False)
        for e in engagements.lignes:
            cle = _s(e.get("Clé engagement"))
            if not cle:
                continue
            nom = _s(e.get("Nom prénom"))
            if not nom:
                continue
            tiret = cle.find("-")
            init = cle[:tiret] if tiret > 0 else cle
            if normaliser(init) in noms_du_registre:
                continue
            noms_du_registre[normaliser(init)] = nom
    except Exception:  # noqa: BLE001
        pass
    try:
        saisie = lire_onglet(CFG["ONGLET_SAISIE"])
        for l in saisie.lignes:
            init = _s(l.get(COL["INITIALES"]))
            if not init:
                continue
            cle_init = normaliser(init)
            personne = personnes.get(cle_init, {})
            nom_legal = _s(personne.get("Nom")) or _s(l.get(COL["NOM"]))
            prenom_legal = _s(personne.get("Prénom")) or _s(l.get(COL["PRENOM"]))
            etat_civil = nom_de_fichier((nom_legal + " " + prenom_legal).strip())
            usage = nom_de_fichier(appellation_nom_prenom_av({"nom": nom_legal, "prenom": prenom_legal, "personne": personne,
                                                              "ligne": l, "engagement": {}}))
            if not usage:
                usage = etat_civil
            if not etat_civil:
                etat_civil = usage
            if not usage:
                continue
            nom_registre = noms_du_registre.get(cle_init) or etat_civil
            idx["usageParInitiales"][cle_init] = usage
            for candidat in (usage, etat_civil, nom_registre):
                k = normaliser(candidat)
                if not k:
                    continue
                idx["usageParCle"].setdefault(k, usage)
                idx["etatCivilParCle"].setdefault(k, etat_civil)
                idx["nomRegistreParCle"].setdefault(k, nom_registre)
            idx["paires"] += 1
    except Exception:  # noqa: BLE001
        pass
    return idx


def personne_du_nom_de_dossier_dp(nom):
    n = str(nom or "")
    i = n.find(" - ")
    return (n[:i] if i > 0 else n).strip()


def pc_personne_du_dossier(nom_du_dossier, idx):
    """Version gagnante (« 48 ») : le nom tel que le registre des engagements le porte."""
    brut = personne_du_nom_de_dossier_dp(nom_du_dossier)
    return idx["nomRegistreParCle"].get(normaliser(brut)) or brut


# ------------------------------------------------ engagements, rang, rattachement

def pc_lire_les_engagements():
    classeur = _classeur(ID_EFFECTIF)
    prop = _onglet(classeur, PC["ONGLET_ENGAGEMENTS"])
    if prop is None:
        raise ValueError("Onglet « " + PC["ONGLET_ENGAGEMENTS"] + " » introuvable.")
    valeurs = _lire_grille(ID_EFFECTIF, prop["title"])
    entete = [pc_norm(v) for v in (valeurs[0] if valeurs else [])]

    def col(nom):
        n = pc_norm(nom)
        if n not in entete:
            raise ValueError("Colonne « " + nom + " » absente de " + PC["ONGLET_ENGAGEMENTS"] + ".")
        return entete.index(n)
    i_cle, i_nom = col("Clé engagement"), col("Nom prénom")
    i_type = entete.index(pc_norm("Type de contrat")) if pc_norm("Type de contrat") in entete else -1
    i_objet = entete.index(pc_norm("Objet du contrat")) if pc_norm("Objet du contrat") in entete else -1
    liste = []
    for r in valeurs[1:]:
        cle = _s(r[i_cle] if i_cle < len(r) else "")
        if cle == "":
            continue
        nom = r[i_nom] if i_nom < len(r) else ""
        liste.append({"cle": cle, "nom": _s(nom),
                      "type": _s(r[i_type]) if 0 <= i_type < len(r) else "",
                      "objet": _s(r[i_objet]) if 0 <= i_objet < len(r) else "",
                      "jetons": pc_jetons(nom)})
    return liste


def pc_famille_de_l_engagement(eng):
    type_ = pc_norm((eng or {}).get("type"))
    objet = pc_norm((eng or {}).get("objet"))
    if type_ == "mandat":
        return "Mandat"
    if re.search(r"(encadrement|supervision|expertise|formation|animation|direction et gouvernance)", objet):
        return "Mandat"
    return "Contrat"


def pc_clef_de_rang(p, famille, aujourdhui):
    nature = pc_nature_du_titre(p["titre"])
    date = pc_date_du_titre(p["titre"])["tri"]
    futur = 1 if (date != "" and aujourdhui != "" and date > aujourdhui) else 0
    groupe = 0 if nature == famille else (1 if nature == "Avenant" else 2)
    signee = 0 if pc_est_signee(p["titre"]) == "x" else 1
    format_ = 0 if str(p["mime"]) == "application/pdf" else 1
    return {"futur": futur, "groupe": groupe, "signee": signee, "format": format_,
            "date": "00000000" if date == "" else date, "nature": nature}


def pc_ranger_les_pieces_de_regime(pieces, eng, aujourdhui):
    famille = pc_famille_de_l_engagement(eng)
    candidates = [p for p in pieces if pc_nature_du_titre(p["titre"]) in PC_NATURES_DE_REGIME]

    def comparer(a, b):
        ka, kb = pc_clef_de_rang(a, famille, aujourdhui), pc_clef_de_rang(b, famille, aujourdhui)
        for c in ("futur", "groupe", "signee", "format"):
            if ka[c] != kb[c]:
                return ka[c] - kb[c]
        if ka["date"] == kb["date"]:
            return 0
        return 1 if ka["date"] < kb["date"] else -1
    candidates.sort(key=functools.cmp_to_key(comparer))
    return {"famille": famille, "pieces": candidates}


def pc_rattacher(nom_du_dossier, engagements):
    cible = pc_norm(nom_du_dossier)
    jetons_dossier = pc_jetons(nom_du_dossier)
    exacts = [e for e in engagements if pc_norm(e["nom"]) == cible]
    if exacts:
        return {"engagements": exacts, "mode": "exact"}
    approches = []
    for e in engagements:
        if not e["jetons"]:
            continue
        communs = [t for t in e["jetons"] if t in jetons_dossier]
        if len(communs) < 2:
            continue
        tous_dans_dossier = all(t in jetons_dossier for t in e["jetons"])
        tous_dans_engagement = all(t in e["jetons"] for t in jetons_dossier)
        if tous_dans_dossier or tous_dans_engagement:
            approches.append(e)
    if approches:
        return {"engagements": approches, "mode": "approché"}
    return {"engagements": [], "mode": "aucun"}


# ------------------------------------------------ Drive sous gestion@

def _lister(id_parent, dossiers=None):
    """Les enfants directs non supprimes d'un dossier, par l'API Drive v3
    (supportsAllDrives), tries par nom : dossiers=True pour les seuls
    dossiers, False pour les seuls fichiers, None pour tout."""
    q = "'" + id_parent + "' in parents and trashed = false"
    if dossiers is True:
        q += " and mimeType = '" + TYPE_DOSSIER + "'"
    elif dossiers is False:
        q += " and mimeType != '" + TYPE_DOSSIER + "'"
    liste, jeton = [], None
    while True:
        rep = _executer(drive().files().list(
            q=q, pageSize=1000, pageToken=jeton, orderBy="name", supportsAllDrives=True,
            includeItemsFromAllDrives=True, corpora="allDrives",
            fields="nextPageToken,files(id,name,mimeType,modifiedTime)"))
        liste.extend(rep.get("files", []))
        jeton = rep.get("nextPageToken")
        if not jeton:
            return liste


def _decalage_zurich(utc):
    """Heures a ajouter a un instant UTC pour l'heure de Zurich (regle
    europeenne), comme maintenant() du socle."""
    an = utc.year

    def dernier_dimanche(mois):
        d = datetime.datetime(an, mois, 31)
        return d - datetime.timedelta(days=(d.weekday() + 1) % 7)
    debut = dernier_dimanche(3).replace(hour=1)
    fin = dernier_dimanche(10).replace(hour=1)
    return 2 if debut <= utc < fin else 1


def pc_modifie_le(modified_time):
    """Utilities.formatDate(getLastUpdated(), 'Europe/Zurich', 'dd.MM.yyyy HH:mm'),
    que Sheets convertissait en date heure a l'ecriture : une Date au format
    date heure, a la minute pres."""
    t = str(modified_time or "")
    try:
        utc = datetime.datetime.strptime(t[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return ""
    local = (utc + datetime.timedelta(hours=_decalage_zurich(utc))).replace(second=0, microsecond=0)
    d = serial_de(local)
    d.format = FORMAT_DATE_HEURE
    return d


def pc_lister_les_dossiers_collaborateurs():
    plate = []
    for pop in PC["POPULATIONS"]:
        try:
            enfants = _lister(pop["id"], dossiers=True)
        except Exception as exc:  # noqa: BLE001
            raise ValueError("Dossier de population « " + pop["nom"] + " » illisible : " + str(exc)[:200])
        for d in enfants:
            plate.append({"population": pop["nom"], "id": d["id"], "nom": str(d.get("name") or "").strip()})
    plate.sort(key=lambda x: (x["population"], pc_norm(x["nom"])))
    return plate


def pc_ramasser_les_fichiers(fichiers, libelle, pieces, vus):
    for f in fichiers:
        ident = f["id"]
        if ident in vus:
            continue
        vus[ident] = True
        pieces.append({"sousDossier": libelle, "id": ident, "titre": str(f.get("name") or "").strip(),
                       "mime": f.get("mimeType") or "", "modifie": pc_modifie_le(f.get("modifiedTime"))})


def pc_pieces_du_dossier(id_dossier):
    """Racine, puis sous-dossiers reconnus (« 47 »), puis leurs sous-dossiers, un niveau de plus."""
    pieces, vus = [], {}
    enfants = _lister(id_dossier)
    pc_ramasser_les_fichiers([e for e in enfants if e["mimeType"] != TYPE_DOSSIER], PC["LIBELLE_RACINE"], pieces, vus)
    for sous in [e for e in enfants if e["mimeType"] == TYPE_DOSSIER]:
        libelle = pc_libelle_du_sous_dossier(sous.get("name"))
        if libelle == "":
            continue
        contenu = _lister(sous["id"])
        pc_ramasser_les_fichiers([e for e in contenu if e["mimeType"] != TYPE_DOSSIER], libelle, pieces, vus)
        for petit in [e for e in contenu if e["mimeType"] == TYPE_DOSSIER]:
            pc_ramasser_les_fichiers(_lister(petit["id"], dossiers=False), libelle, pieces, vus)
    return pieces


# ------------------------------------------------ l'onglet cible

def _ligne_pleine(l):
    l = list(l)[:LARGEUR]
    return l + [""] * (LARGEUR - len(l))


def _lisible(v):
    """Une valeur de cellule telle qu'elle s'affichera, pour le compte rendu."""
    if isinstance(v, Date):
        d = date_de(v)
        if d is None:
            return float(v)
        return d.strftime("%d.%m.%Y %H:%M" if v.format == FORMAT_DATE_HEURE else "%d.%m.%Y")
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


class _Cible:
    """pc_feuilleCible_ et son modele en memoire : la grille telle qu'elle
    serait apres chaque ecriture, ce qui permet de tout calculer sans
    ecrire, et d'ecrire au meme endroit avec confirmer."""

    def __init__(self, confirmer, journal):
        self.confirmer = confirmer
        self.journal = journal
        classeur = _classeur(ID_EFFECTIF)
        prop = _onglet(classeur, PC["ONGLET_CIBLE"])
        self.creee = prop is None
        if prop is None:
            if confirmer:
                prop = _creer_onglet(classeur, PC["ONGLET_CIBLE"])
            else:
                prop = {"title": PC["ONGLET_CIBLE"], "sheetId": -1, "gridProperties": {"rowCount": 100, "columnCount": 26}}
            journal["onglet_cree"] = True
        self.prop = prop
        self.sid = prop["sheetId"]
        if confirmer:
            _assurer_dimensions(ID_EFFECTIF, prop, colonnes=LARGEUR)
        _oublier(ID_EFFECTIF, prop["title"])
        grille = _lire_grille(ID_EFFECTIF, prop["title"]) if not self.creee else []
        self.grille = [_ligne_pleine(l) for l in grille]
        actuel = self.grille[0] if self.grille else [""] * LARGEUR
        memes = all(_s(actuel[c]) == PC["ENTETES"][c] for c in range(LARGEUR))
        if not memes:
            journal["en_tetes"] = list(PC["ENTETES"])
            if self.grille:
                self.grille[0] = list(PC["ENTETES"])
            else:
                self.grille.append(list(PC["ENTETES"]))
            self._ecrire(1, 1, [list(PC["ENTETES"])])

    def _ecrire(self, ligne, colonne, lignes):
        if not self.confirmer or not lignes:
            return
        _assurer_dimensions(ID_EFFECTIF, self.prop, lignes=ligne + len(lignes) - 1, colonnes=colonne + max(len(l) for l in lignes) - 1)
        _batch(ID_EFFECTIF, _requete_cellules(self.sid, ligne - 1, colonne - 1, lignes))
        _oublier(ID_EFFECTIF, self.prop["title"])

    def derniere_ligne(self):
        return len(self.grille)

    def lignes_max(self):
        return self.prop.get("gridProperties", {}).get("rowCount", 0)

    def colonnes_max(self):
        return self.prop.get("gridProperties", {}).get("columnCount", 0)

    def indexer_l_existant(self):
        index = {}
        for i, l in enumerate(self.grille[1:]):
            cle = _s(l[0]) + "|" + _s(l[11])
            index[cle] = {"ligne": i + 2, "lecture": list(l[PC_COL_LECTURE_DEBUT - 1:PC_COL_LECTURE_FIN])}
        return index

    def mettre_a_jour(self, maj):
        """Les lignes existantes reecrites en place, par blocs contigus, un batch."""
        if not maj:
            return
        for m in maj:
            self.grille[m["ligne"] - 1] = list(m["valeurs"])
        if not self.confirmer:
            return
        requetes, bloc, debut = [], [], None
        for m in sorted(maj, key=lambda x: x["ligne"]):
            if bloc and m["ligne"] != debut + len(bloc):
                requetes.append(_requete_cellules(self.sid, debut - 1, 0, bloc))
                bloc, debut = [], None
            if not bloc:
                debut = m["ligne"]
            bloc.append(list(m["valeurs"]))
        if bloc:
            requetes.append(_requete_cellules(self.sid, debut - 1, 0, bloc))
        _batch(ID_EFFECTIF, requetes)
        _oublier(ID_EFFECTIF, self.prop["title"])

    def ajouter(self, lignes):
        depart = self.derniere_ligne() + 1
        if not lignes:
            return depart
        self._ecrire(depart, 1, [list(l) for l in lignes])
        self.grille.extend([list(l) for l in lignes])
        return depart

    def reecrire_tout(self, gardees):
        """La cloture : tout effacer des la ligne 2, poser les lignes gardees,
        retirer les lignes et colonnes en trop."""
        self.grille = [self.grille[0]] + [list(l) for l in gardees]
        if not self.confirmer:
            return
        _assurer_dimensions(ID_EFFECTIF, self.prop, lignes=len(gardees) + 1)
        requetes = []
        if self.lignes_max() > 1:
            requetes.append(_requete_effacer(self.sid, 1, self.lignes_max(), 0, LARGEUR))
        if gardees:
            requetes.append(_requete_cellules(self.sid, 1, 0, [list(l) for l in gardees]))
        grid = self.prop.get("gridProperties", {})
        if self.lignes_max() > len(gardees) + 1:
            requetes.append({"deleteDimension": {"range": {"sheetId": self.sid, "dimension": "ROWS",
                                                           "startIndex": len(gardees) + 1, "endIndex": self.lignes_max()}}})
            grid["rowCount"] = len(gardees) + 1
        if self.colonnes_max() > LARGEUR:
            requetes.append({"deleteDimension": {"range": {"sheetId": self.sid, "dimension": "COLUMNS",
                                                           "startIndex": LARGEUR, "endIndex": self.colonnes_max()}}})
            grid["columnCount"] = LARGEUR
        _batch(ID_EFFECTIF, requetes)
        _oublier(ID_EFFECTIF, self.prop["title"])


def pc_lecture_vide():
    return [""] * (PC_COL_LECTURE_FIN - PC_COL_LECTURE_DEBUT + 1)


def pc_date_de_la_piece(affichage):
    """« jj.mm.aaaa » en texte chez Apps Script, converti en date par Sheets a
    l'ecriture : ici une Date au format date, ce que l'onglet porte deja."""
    if not affichage:
        return ""
    d = date_de(affichage)
    if d is None:
        return affichage
    return serial_de(d)


def _cle_de_tri_date(v):
    """La date de la piece pour le tri de la cloture : serie Sheets, ou None."""
    if isinstance(v, Date):
        return float(v)
    d = date_de(v) if _s(v) else None
    return float(serial_de(d)) if d else None


def pc_cloturer_le_passage(cible, engagements, passage, journal):
    valeurs = cible.grille[1:]
    cles_vues, gardees, retirees = {}, [], 0
    for l in valeurs:
        if _s(l[4]) == "Aucune pièce":
            continue
        if _s(l[20]) != passage:
            retirees += 1
            continue
        gardees.append(list(l))
        if _s(l[0]) != "":
            cles_vues[_s(l[0])] = True
    sans_piece = 0
    for e in engagements:
        if cles_vues.get(e["cle"]):
            continue
        sans_piece += 1
        gardees.append([e["cle"], e["nom"], "", "", "Aucune pièce", "", "", "", "", "", "", "", "",
                        "", "", "", "", "", "", "Aucun dossier ni aucune pièce trouvés dans le Drive", passage])

    def comparer(a, b):
        na, nb = pc_norm(a[1]), pc_norm(b[1])
        if na != nb:
            return -1 if na < nb else 1
        ca, cb = texte(a[0]), texte(b[0])
        if ca != cb:
            return -1 if ca < cb else 1
        da, db = _cle_de_tri_date(a[8]), _cle_de_tri_date(b[8])
        if da == db:
            return 0
        if da is None:
            return 1
        if db is None:
            return -1
        return 1 if da < db else -1
    gardees.sort(key=functools.cmp_to_key(comparer))
    journal["cloture"] = {"lignes": gardees, "lignes_apres_cloture": len(gardees) + 1, "colonnes_apres_cloture": LARGEUR}
    cible.reecrire_tout(gardees)
    return {"lignesConservees": len(gardees), "lignesRetirees": retirees, "engagementsSansAucunePiece": sans_piece}


def _dossiers_de_la_personne(dossiers, idx, engagements, initiales):
    """Le filtre initiales= : les dossiers dont le nom, traduit par l'index
    des appellations, rejoint un engagement de ces initiales, ou dont le
    prefixe est l'un des trois noms connus de la personne."""
    init = normaliser(initiales)
    usage = idx["usageParInitiales"].get(init, "")
    noms = set()
    for c in (usage, idx["etatCivilParCle"].get(normaliser(usage), ""), idx["nomRegistreParCle"].get(normaliser(usage), "")):
        if c:
            noms.add(normaliser(c))
    cles = {e["cle"] for e in engagements if normaliser(e["cle"].split("-")[0]) == init}
    retenus = []
    for d in dossiers:
        brut = personne_du_nom_de_dossier_dp(d["nom"])
        if normaliser(brut) in noms:
            retenus.append(d)
            continue
        personne = pc_personne_du_dossier(d["nom"], idx)
        if any(e["cle"] in cles for e in pc_rattacher(personne, engagements)["engagements"]):
            retenus.append(d)
    return retenus


def construire_inventaire_des_pieces(options=None, confirmer=False, journal=None, initiales=""):
    """construireInventaireDesPieces({ budgetMs, reprendre }) : un tour du
    parcours par tranches. Sans confirmer, rien n'est ecrit ni memorise."""
    options = options or {}
    journal = journal if journal is not None else {}
    debut = time.time()
    budget = float(options.get("budgetMs") or PC["BUDGET_MS"]) / 1000.0 if not options.get("sansBudget") else None
    reprendre = options.get("reprendre") is True
    curseur = int(memoire_lire(PC["CLE_CURSEUR"]) or 0) if reprendre else 0
    jeton = "P" + maintenant().strftime("%Y%m%d-%H%M")
    passage = (memoire_lire(PC["CLE_PASSAGE"]) or jeton) if reprendre else jeton
    memoire = journal.setdefault("memoire", {})
    if not reprendre:
        memoire[PC["CLE_PASSAGE"]] = passage
        memoire[PC["CLE_CURSEUR"]] = "0"
        if confirmer and not initiales:
            memoire_ecrire(PC["CLE_PASSAGE"], passage)
            memoire_ecrire(PC["CLE_CURSEUR"], "0")

    engagements = pc_lire_les_engagements()
    idx = index_des_appellations_dp()
    dossiers = pc_lister_les_dossiers_collaborateurs()
    if initiales:
        dossiers = _dossiers_de_la_personne(dossiers, idx, engagements, initiales)
    cible = _Cible(confirmer, journal)
    index = cible.indexer_l_existant()
    aujourdhui = maintenant().strftime("%Y%m%d")

    a_ajouter, maj_directes, traites, pieces_vues = [], [], 0, 0
    while curseur < len(dossiers):
        if budget is not None and time.time() - debut > budget:
            break
        dossier = dossiers[curseur]
        personne = pc_personne_du_dossier(dossier["nom"], idx)
        rattachement = pc_rattacher(personne, engagements)
        pieces = pc_pieces_du_dossier(dossier["id"])
        pieces_vues += len(pieces)
        cibles = rattachement["engagements"] if rattachement["engagements"] else [{"cle": "", "nom": personne}]
        for eng in cibles:
            rangement = pc_ranger_les_pieces_de_regime(pieces, eng, aujourdhui)
            de_regime = rangement["pieces"]
            rang_par_id = {p["id"]: k + 1 for k, p in enumerate(de_regime)}
            tete = pc_clef_de_rang(de_regime[0], rangement["famille"], aujourdhui) if de_regime else None
            for p in pieces:
                nature = pc_nature_du_titre(p["titre"])
                date = pc_date_du_titre(p["titre"])
                rang = rang_par_id.get(p["id"], "")
                cle_composite = eng["cle"] + "|" + p["id"]
                lecture = index[cle_composite]["lecture"] if cle_composite in index else pc_lecture_vide()
                anomalies = []
                if eng["cle"] == "":
                    anomalies.append("Dossier non rattaché à un engagement")
                elif rattachement["mode"] == "approché":
                    anomalies.append("Rattachement par approximation du nom")
                if date["tri"] == "" and nature in PC_NATURES_DE_REGIME:
                    anomalies.append("Pièce de régime sans date au gabarit AAAAMMJJ dans le titre")
                if p["sousDossier"] == PC["LIBELLE_RACINE"] and nature in PC_NATURES_DE_REGIME:
                    anomalies.append("Pièce de régime posée à la racine du dossier, hors des sous-dossiers")
                if rang == 1 and _s(lecture[1]) == "":
                    anomalies.append("Pièce en vigueur jamais lue")
                if rang != "" and date["tri"] != "" and date["tri"] > aujourdhui:
                    anomalies.append("Pièce de régime datée du futur, pas encore en vigueur")
                if rang != "" and rang > 1 and tete and date["tri"] != "" and date["tri"] > tete["date"] \
                        and pc_clef_de_rang(p, rangement["famille"], aujourdhui)["groupe"] == 0 and pc_est_signee(p["titre"]) != "x":
                    anomalies.append("Plus récente que la pièce de rang 1 mais non signée")
                ligne = [
                    eng["cle"], eng["nom"], dossier["population"], p["sousDossier"],
                    nature, p["titre"], pc_format_du_type(p["mime"]), pc_est_signee(p["titre"]),
                    pc_date_de_la_piece(date["affichage"]), float(rang) if rang != "" else "", p["modifie"],
                    p["id"], pc_lien_de_la_piece(p["id"], p["mime"]),
                    lecture[0], lecture[1], lecture[2], lecture[3], lecture[4], lecture[5],
                    " ; ".join(anomalies), passage,
                ]
                if cle_composite in index and index[cle_composite]["ligne"] > 0:
                    maj_directes.append({"ligne": index[cle_composite]["ligne"], "valeurs": ligne})
                else:
                    a_ajouter.append(ligne)
                    index[cle_composite] = {"ligne": -1, "lecture": lecture}
        curseur += 1
        traites += 1

    cible.mettre_a_jour(maj_directes)
    depart = cible.ajouter(a_ajouter)
    journal.setdefault("mises_a_jour", []).extend(maj_directes)
    if a_ajouter:
        journal.setdefault("ajouts", []).append({"depuis_ligne": depart, "lignes": a_ajouter})

    memoire[PC["CLE_CURSEUR"]] = str(curseur)
    if confirmer and not initiales:
        memoire_ecrire(PC["CLE_CURSEUR"], str(curseur))
    termine = curseur >= len(dossiers)
    bilan = {"passage": passage, "dossiersAuTotal": len(dossiers), "dossiersTraitesCeTour": traites, "curseur": curseur,
             "piecesVuesCeTour": pieces_vues, "lignesAjoutees": len(a_ajouter), "lignesMisesAJour": len(maj_directes),
             "termine": termine}
    if termine and not initiales:
        bilan["cloture"] = pc_cloturer_le_passage(cible, engagements, passage, journal)
    elif termine:
        bilan["cloture"] = "sans objet : passage limité à " + initiales + ", la clôture retirerait les autres lignes"
    return bilan


def passage(confirmer=False, initiales=""):
    """passageQuotidienDesPieces : tours de 280 s jusqu'a la cloture, vingt au
    plus. Sans confirmer, un seul tour sans budget, rien n'est ecrit."""
    initiales = str(initiales or "").strip()
    journal = {}
    rendu = {"moteur": "pieces", "confirme": bool(confirmer), "initiales": initiales, "classeur": ID_EFFECTIF,
             "onglet": PC["ONGLET_CIBLE"], "ecritures": {}, "fiche": [], "file": [], "memoire": {}}
    with _verrou:
        if not confirmer:
            bilan = construire_inventaire_des_pieces({"sansBudget": True}, confirmer=False, journal=journal, initiales=initiales)
            tours = 1
        else:
            bilan = construire_inventaire_des_pieces({"budgetMs": PC["BUDGET_NUIT_MS"]}, confirmer=True, journal=journal,
                                                     initiales=initiales)
            tours = 1
            while not bilan["termine"] and tours < PC["TOURS_MAX"]:
                bilan = construire_inventaire_des_pieces({"budgetMs": PC["BUDGET_NUIT_MS"], "reprendre": True},
                                                         confirmer=True, journal=journal, initiales=initiales)
                tours += 1
    onglet = "Almaval - Collaborateurs - Effectif / " + PC["ONGLET_CIBLE"]
    ecritures = {"onglet_cree": bool(journal.get("onglet_cree")), "en_tetes": journal.get("en_tetes"),
                 "mises_a_jour": [{"ligne": m["ligne"], "valeurs": [_lisible(v) for v in m["valeurs"]]} for m in journal.get("mises_a_jour", [])],
                 "ajouts": [{"depuis_ligne": a["depuis_ligne"], "lignes": [[_lisible(v) for v in l] for l in a["lignes"]]}
                            for a in journal.get("ajouts", [])]}
    if journal.get("cloture"):
        c = journal["cloture"]
        ecritures["cloture"] = {"lignes": [[_lisible(v) for v in l] for l in c["lignes"]],
                                "lignes_apres_cloture": c["lignes_apres_cloture"], "colonnes_apres_cloture": c["colonnes_apres_cloture"]}
    rendu["ecritures"][onglet] = ecritures
    rendu["memoire"] = journal.get("memoire", {})
    rendu["tours"] = tours
    if confirmer:
        rendu["resultat"] = bilan
    else:
        rendu["resultat_prevu"] = bilan
    return rendu


def _tronquer(rendu, exemples):
    """Le compte rendu de l'outil, borne a « exemples » lignes par bloc ;
    0 pour tout rendre."""
    n = int(exemples or 0)
    if n <= 0:
        return rendu
    for e in rendu.get("ecritures", {}).values():
        e["mises_a_jour_total"] = len(e.get("mises_a_jour", []))
        e["mises_a_jour"] = e.get("mises_a_jour", [])[:n]
        for a in e.get("ajouts", []):
            a["lignes_total"] = len(a["lignes"])
            a["lignes"] = a["lignes"][:n]
        if e.get("cloture"):
            e["cloture"]["lignes_total"] = len(e["cloture"]["lignes"])
            e["cloture"]["lignes"] = e["cloture"]["lignes"][:n]
    return rendu


# ------------------------------------------------ outil et pont

def lancer(confirmer=False, initiales="", exemples=50):
    return _tronquer(passage(confirmer=confirmer, initiales=initiales), exemples)


@mcp.tool()
@tolerant
def onboarding_pieces(confirmer: bool = False, initiales: str = "", exemples: int = 50):
    """Registre des pieces contractuelles (onboarding, 6 h) sous gestion@ ; simulation sans confirmer, exemples=0 pour tout rendre."""
    return lancer(confirmer=confirmer, initiales=initiales, exemples=exemples)


try:
    _pont_precedent = outils_lieux._pont

    def _pont(texte_sujet: str):
        brut = str(texte_sujet or "").strip()
        mots = brut.split()
        premier = mots[0].lower() if mots else ""
        options = dict(m.split("=", 1) for m in mots[1:] if "=" in m)
        drapeaux = {m.lower() for m in mots[1:] if "=" not in m}
        if premier == "onboarding_pieces":
            return pont_de_fond("pieces", drapeaux, tolerant(lancer),
                                dict(confirmer=("confirmer" in drapeaux), initiales=options.get("initiales", ""), exemples=options.get("exemples", "50")))
        return _pont_precedent(brut)

    outils_lieux._pont = _pont
except Exception as _exc:  # noqa: BLE001
    print("[onboarding pieces] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)
