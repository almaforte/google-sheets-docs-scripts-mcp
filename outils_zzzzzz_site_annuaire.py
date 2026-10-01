"""Almaval - site almaval.ch : données publiques de l'annuaire et des disponibilités, 30.09.2026.

Demande d'Alberto du 30.09.2026 : la page « Nos spécialistes » du site
doit publier seule les arrivées, retirer chacun au dernier jour de son
engagement et montrer les disponibilités, sans ressaisie. Même demande
pour l'encart des disponibilités de l'en-tête (psychothérapie,
évaluation diagnostique, bilans neuropsychologiques, suivis infirmiers).

Architecture. Les pages WordPress restent fixes. Elles lisent un fichier
public, gs://almaval-site-donnees/annuaire.json
(https://storage.googleapis.com/almaval-site-donnees/annuaire.json,
lecture publique, CORS limité à almaval.ch), que ce module recalcule et
dépose chaque nuit. Aucune écriture quotidienne dans WordPress.

Qui figure dans l'annuaire (règle d'Alberto du 30.09.2026). Une personne
dont un engagement est en cours au Registre - Engagements (date de fin
vide ou postérieure au jour du passage : retirée dès la nuit de son
dernier jour, pour ne plus recevoir de demandes qu'elle ne pourra suivre),
avec une affectation en cours au service Clinique ou au Service social du
Registre - Affectations, et dont le statut de collaboration n'est ni
locataire (jamais référencés nulle part) ni partenaire (encadrants et
superviseurs, qui ne font que de la formation), et dont l'engagement
porte au moins une demi-journée de présence au registre (une personne
« En cours » sans aucune demi-journée ne vient pas encore : Capozoli
Biancarelli au 01.10.2026). Une ligne « - » dans la
colonne « Publié sur le site » de l'onglet « Site - Annuaire »
d'Almaval - Collaborateurs - Effectif retire quelqu'un à la main.

Ce que dit chaque carte, et d'où cela vient :
  - nom d'usage et prénom d'usage, titre : Registre - Personnes (titre
    obtenu, sexe) et Registre - Engagements (profession, statut), avec le
    vocabulaire du 07.09.2026 (jamais « assistant ») ;
  - lieux et jours, publiés séparément, jamais un jour lié à un lieu : les
    douze demi-journées du Registre - Engagements ; « Télétravail » et
    « Itinérant » donnent « En ligne » ;
  - axes et âge des patients : Registre - Profil clinique, à défaut
    Places disponibles ;
  - langues : Registre - Personnes et Places disponibles ;
  - statut d'accueil des infirmiers (01.10.2026) : colonne « Statut
    infirmier » de Places disponibles, Ouvert oui, Sur étude à confirmer,
    Complet non, avec le secteur à domicile et les prises en charge ;
  - nouveaux patients (médecins et psychologues seulement) : oui si
    Places disponibles porte des places, non sinon ; « à confirmer » si la
    ligne annonce des places mais n'a pas été mise à jour depuis plus de
    30 jours (un zéro reste un non, règle d'Alberto du 01.10.2026) ;
  - boutons de rendez-vous : les liens d'agenda de la colonne « Plannings
    publiés sur la page web personnelle » de Places disponibles ;
  - photo et présentation : onglet « Site - Annuaire », montrées seulement
    quand « Validé par le collaborateur » vaut x. Les 39 fiches du site
    au 30.09.2026 y ont été reprises comme validées.

Disponibilités de l'en-tête : places de psychothérapie = somme de
« Places total » de Places disponibles ; délais = médiane, sur les
demandes des 180 derniers jours de l'onglet Patients, du nombre de jours
entre « Date demande » et le premier rendez-vous de la prestation.

Outil : site_annuaire(confirmer). Pont : lieux_cycle avec le sujet
« action:site_annuaire [confirmer] [fond|etat] ». Sans confirmer, rien
n'est écrit ni déposé.
"""

import datetime
import json
import re
import statistics

from googleapiclient.http import MediaInMemoryUpload

from main import mcp, tolerant

import outils_lieux
import outils_zzzzz_onboarding_0_socle as socle
import outils_zzzzzz_places_membres as pm
from outils_cloud import _api
from outils_zzzzz_onboarding_0_socle import ID_EFFECTIF, _verrou, date_de, maintenant, pont_de_fond, texte

ID_PATIENTS = pm.ID_PLACES
SITE = {
    "BUCKET": "almaval-site-donnees",
    "OBJET": "annuaire.json",
    "URL": "https://storage.googleapis.com/almaval-site-donnees/annuaire.json",
    "GRAINE": ("gestion-almaval-sources-claude", "site/fiches_woocommerce_20260930.json"),
    "ONGLET": "Site - Annuaire",
    "FICHE_BASE": "",
    "JOURS_FRAICHEUR": 30,
    "JOURS_DELAIS": 180,
    "MIN_MESURES": 3,
}
PLANCHER = 30  # en dessous, le dépôt public est refusé
CATS = ["psychiatrie", "psychotherapie", "neuropsychologie", "infirmiers", "complementaires", "social"]
JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"]
VILLES = {"crissier": "Crissier", "morges": "Morges", "lausanne": "Lausanne", "lausanne riponne": "Lausanne",
          "la lisiere": "Lausanne", "geneve": "Genève", "vevey": "Vevey", "jura": "Jura"}
EN_LIGNE = {"teletravail", "itinerant"}
LANGUES = ["Français", "Italien", "Anglais", "Espagnol", "Portugais", "Allemand", "Arabe", "Roumain"]
CODES = {"F": "Français", "I": "Italien", "EN": "Anglais", "ES": "Espagnol", "PT": "Portugais", "D": "Allemand",
         "AR": "Arabe", "RO": "Roumain"}
AXES = {"TCC": "Cognitivo-comportementale (TCC)", "ACP": "Centrée sur la personne (ACP)",
        "PCI": "Corporelle intégrative (PCI)", "TCE": "Centrée sur les émotions (TCE)"}
SPECIAUX = {
    # Le registre porte la direction pour cet engagement (mandat, statut Partner depuis le 01.10.2026) ;
    # la fiche clinique suit le Document maître Formation.
    "AMFo": {"c": "psychiatrie", "t": "Médecin psychiatre psychothérapeute, directeur médical",
             "s": ["Crissier", "Morges"], "j": ["lundi", "mardi", "mercredi", "jeudi", "vendredi"], "o": True},
}
DISPOS = [
    {"cle": "psychotherapie", "libelle": "Psychothérapie", "date": "Date premier rdv psychothérapie", "places": True},
    {"cle": "evaluation", "libelle": "Évaluation diagnostique", "date": "Date rendez-vous bilan affectif", "places": False},
    {"cle": "neuropsy", "libelle": "Bilans neuropsy", "date": "Date bilan neuropsy", "places": False},
    {"cle": "infirmiers", "libelle": "Suivis infirmiers", "date": "Date bilan infirmier", "places": False},
]

_URL = re.compile(r"https?://[^\s,;]+")


def _n(s):
    return pm._norm(s)


def _slug(nom):
    return "-".join(pm.jetons(nom))


def _jour(d):
    return d.strftime("%d.%m.%Y") if d else ""


def _actif(e, aujourdhui):
    if pm._meme(e.get("État de l'engagement"), "Clos"):
        return False
    etat = _n(e.get("État de l'engagement"))
    debut = date_de(e.get("Date de début"))
    if etat == "a venir" and not (debut and debut.date() <= aujourdhui):
        return False
    fin = date_de(e.get("Date de fin"))
    return not (fin and fin.date() <= aujourdhui)


def _presente(e):
    """Vrai si l'engagement porte au moins une demi-journée de présence (lieu, Télétravail ou Itinérant)."""
    for jour in JOURS:
        for moment in ("matin", "après-midi"):
            brut = _n(e.get(jour + " " + moment))
            if brut and brut != "non travaille":
                return True
    return False


def _exclu(e):
    s = _n(e.get("Statut de collaboration"))
    return s.startswith("locataire") or s.startswith("partner")


def _categorie(e, service):
    p = _n(e.get("Profession"))
    if p.startswith("medecin"):
        return "psychiatrie"
    if p.startswith("neuropsychologue"):
        return "neuropsychologie"
    if p.startswith("psychologue"):
        return "psychotherapie"
    if p.startswith("infirmier"):
        return "infirmiers"
    if p.startswith("approches complementaires"):
        return "complementaires"
    if _n(service) == "service social":
        return "social"
    return None


def _femme(pers):
    return _n(pers.get("Sexe")).startswith("f")


def _titre(c, e, pers, poste):
    titre = _n(pers.get("Titre obtenu"))
    formation = _n(e.get("Statut")) == "en formation"
    if c == "psychiatrie":
        return "Médecin psychiatre en formation" if formation else "Médecin psychiatre psychothérapeute"
    if c == "psychotherapie":
        if "psychotherapie" in titre:
            return "Psychologue psychothérapeute"
        if "psychologie clinique" in titre:
            return "Psychologue spécialiste en psychologie clinique"
        return "Psychologue en formation de psychothérapie" if formation else "Psychologue"
    if c == "neuropsychologie":
        if "neuropsychologie" in titre:
            return "Psychologue spécialiste en neuropsychologie"
        return "Neuropsychologue en formation" if formation else "Neuropsychologue"
    if c == "infirmiers":
        return "Infirmière" if _femme(pers) else "Infirmier"
    if c == "complementaires":
        return "Approches complémentaires"
    if c == "social":
        return "Responsable du service social" if "responsable" in _n(poste) else "Service social"
    return ""


def _nom_affiche(pers, medecin):
    prenom = texte(pers.get("Prénom d'usage")).strip() or texte(pers.get("Prénom")).strip()
    nom = texte(pers.get("Nom de famille d'usage")).strip() or texte(pers.get("Nom")).strip()
    titre = ("Dre " if _femme(pers) else "Dr ") if medecin else ""
    return (titre + prenom + " " + nom).strip()


def _presence(e):
    sites, jours, en_ligne = [], [], False
    for jour in JOURS:
        present = False
        for moment in ("matin", "après-midi"):
            brut = _n(e.get(jour + " " + moment))
            if not brut or brut == "non travaille":
                continue
            present = True
            if brut in EN_LIGNE:
                en_ligne = True
            elif brut in VILLES and VILLES[brut] not in sites:
                sites.append(VILLES[brut])
        if present:
            jours.append(jour.lower())
    ordre = ["Crissier", "Morges", "Lausanne", "Vevey", "Genève", "Jura"]
    return sorted(sites, key=ordre.index), jours, en_ligne


def _ages(a, b):
    def nombre(v):
        try:
            return int(float(str(v).replace(",", ".")))
        except (TypeError, ValueError):
            return None
    a, b = nombre(a), nombre(b)
    if a is None and b is None:
        return ""
    a = 0 if a is None else a
    b = 100 if b is None else b
    if a <= 0 and b >= 100:
        return "Tous âges"
    if a >= 18 and b >= 100:
        return "Adultes"
    if b >= 100:
        return "Dès " + str(a) + " ans"
    if a <= 0:
        return "Jusqu'à " + str(b) + " ans"
    return str(a) + " à " + str(b) + " ans"


def _liens(brut):
    """[[url, libellé]] depuis la cellule des plannings : « Crissier: url » donne le libellé."""
    sortie = []
    for ligne in str(brut or "").splitlines():
        for m in _URL.finditer(ligne):
            avant = ligne[:m.start()].strip().rstrip(":").strip()
            sortie.append([m.group(0), avant if avant and len(avant) <= 30 else ""])
    if len(sortie) > 1 and not any(l for _, l in sortie):
        sortie = [[u, str(i + 1)] for i, (u, _) in enumerate(sortie)]
    return sortie


# ------------------------------------------------------------------ lectures

def _registres():
    personnes = {}
    for l in socle.lire_onglet_de(ID_EFFECTIF, "Registre - Personnes", rafraichir=True, avec_calculees=False).lignes:
        ini = texte(l.get("Initiales")).strip()
        if ini and ini not in personnes:
            personnes[ini] = l
    engagements = [l for l in socle.lire_onglet_de(ID_EFFECTIF, "Registre - Engagements", rafraichir=True,
                                                   avec_calculees=False).lignes
                   if texte(l.get("Clé engagement")).strip() and texte(l.get("Initiales")).strip()]
    affectations = {}
    for l in socle.lire_onglet_de(ID_EFFECTIF, "Registre - Affectations", rafraichir=True, avec_calculees=False).lignes:
        service = texte(l.get("Service")).strip()
        if _n(service) not in ("clinique", "service social"):
            continue
        if pm._meme(l.get("État de l'engagement"), "Clos"):
            continue
        fin = date_de(l.get("Date de fin"))
        if fin and fin.date() < maintenant().date():
            continue
        affectations.setdefault(texte(l.get("Clé engagement")).strip(), []).append(l)
    profils = {}
    try:
        for l in socle.lire_onglet_de(ID_EFFECTIF, "Registre - Profil clinique", rafraichir=True,
                                      avec_calculees=False).lignes:
            ini = texte(l.get("Initiales")).strip()
            if ini:
                profils[ini] = l
    except Exception:  # noqa: BLE001
        pass
    return personnes, engagements, affectations, profils


def _places():
    """Par ligne de Places disponibles : nom, places, fraîcheur, langues, liens, compétences, axes, âges."""
    p = pm._lire_places()
    vis = p["visibles"]

    def col(nom, visible=False):
        return p["colonne"](nom, visible=visible)

    c_places, c_maj, c_online = col("Places total"), col("Mis à jour le"), col("Online")
    c_liens = col("Plannings publiés sur la page web personnelle")
    c_axes = [col("Axe thérapie 1"), col("Axe thérapie 2"), col("Axe thérapie complémentaire")]
    c_age, c_jusqu = col("Âge patients"), col("Jusqu'à")
    c_statut, c_secteur = col("Statut infirmier"), col("Secteur à domicile")
    d_soins, f_soins = col("Évaluation infirmière", visible=True), col("Activation par le mouvement", visible=True)
    c_soins = list(range(d_soins, f_soins + 1)) if d_soins and f_soins and f_soins >= d_soins else []
    debut = col("Couple & famille", visible=True)
    fin = col("Autres compétences", visible=True)
    c_comp = list(range(debut, fin)) if debut and fin and fin > debut else []
    lignes = []
    for l in p["lignes"]:
        v = l["valeurs"]

        def cel(c):
            return v[c - 1] if c and c - 1 < len(v) else ""
        try:
            places = float(cel(c_places) or 0)
        except (TypeError, ValueError):
            places = 0.0
        langues = [nom for code, nom in CODES.items() if pm._meme(cel(col(code)), "x")]
        autre = texte(cel(col("Autre"))).strip()
        if autre and autre.lower() not in ("x", "-"):
            langues.append(autre)
        lignes.append({
            "nom": l["nom"], "places": places, "maj": date_de(cel(c_maj)),
            "online": pm._meme(cel(c_online), "x"), "langues": langues, "liens": _liens(cel(c_liens)),
            "competences": [vis[c - 1] for c in c_comp if pm._meme(cel(c), "x")],
            "axes": [texte(cel(c)).strip() for c in c_axes if texte(cel(c)).strip() not in ("", "-", "x")],
            "age": cel(c_age), "jusqu": cel(c_jusqu),
            "statut": texte(cel(c_statut)).strip(), "secteur": texte(cel(c_secteur)).strip(),
            "soins": [vis[c - 1] for c in c_soins if pm._meme(cel(c), "x")],
        })
    total = sum(l["places"] for l in lignes)
    return lignes, total


def _onglet_site():
    classeur = socle._classeur(ID_EFFECTIF, rafraichir=True)
    prop = socle._onglet(classeur, SITE["ONGLET"])
    if prop is None:
        raise ValueError("Onglet introuvable dans l'Effectif : " + SITE["ONGLET"])
    socle._oublier(ID_EFFECTIF, prop["title"])
    grille = socle._lire_grille(ID_EFFECTIF, prop["title"])
    entetes = [texte(e).strip() for e in (grille[0] if grille else [])]
    lignes = {}
    for i, r in enumerate(grille[1:]):
        obj = {e: (r[j] if j < len(r) else "") for j, e in enumerate(entetes) if e}
        ini = texte(obj.get("Initiales")).strip()
        if ini:
            obj["_ligne"] = i + 2
            lignes[ini] = obj
    return prop, entetes, lignes, len(grille)


def _graine():
    try:
        seau, objet = SITE["GRAINE"]
        brut = _api("storage", "v1").objects().get_media(bucket=seau, object=objet).execute()
        return json.loads(brut.decode("utf-8") if isinstance(brut, bytes) else brut)
    except Exception:  # noqa: BLE001
        return []


def _delais(aujourdhui):
    socle._oublier(ID_PATIENTS, "Patients")
    grille = socle._lire_grille(ID_PATIENTS, "Patients")
    if not grille:
        return {}
    entetes = [texte(e).strip() for e in grille[0]]
    idx = {e: i for i, e in reversed(list(enumerate(entetes))) if e}
    i_dem = idx.get("Date demande")
    limite = aujourdhui - datetime.timedelta(days=SITE["JOURS_DELAIS"])
    sortie = {}
    for d in DISPOS:
        i_rdv = idx.get(d["date"])
        mesures = []
        if i_dem is None or i_rdv is None:
            sortie[d["cle"]] = {"delai": None, "n": 0, "colonne": d["date"], "absente": True}
            continue
        for r in grille[1:]:
            dem = date_de(r[i_dem] if i_dem < len(r) else "")
            rdv = date_de(r[i_rdv] if i_rdv < len(r) else "")
            if not dem or not rdv or dem.date() < limite or dem.date() > aujourdhui:
                continue
            ecart = (rdv.date() - dem.date()).days
            if 0 <= ecart <= 365:
                mesures.append(ecart)
        sortie[d["cle"]] = {"delai": int(round(statistics.median(mesures))) if len(mesures) >= SITE["MIN_MESURES"] else None,
                            "n": len(mesures), "colonne": d["date"]}
    return sortie


# ------------------------------------------------------------------ calcul

def calculer(aujourdhui=None):
    aujourdhui = aujourdhui or maintenant().date()
    personnes, engagements, affectations, profils = _registres()
    index = {ini: pm._jetons_personne(p) for ini, p in personnes.items()}
    par_personne = {}
    for e in engagements:
        par_personne.setdefault(texte(e.get("Initiales")).strip(), []).append(e)

    places, total_places = _places()
    places_par_ini, sans_personne = {}, []
    for l in places:
        inis = pm._correspondances(l["nom"], personnes, index)
        if len(inis) == 1:
            places_par_ini[inis[0]] = l
        else:
            sans_personne.append(l["nom"])

    prop, entetes, site, nb_lignes = _onglet_site()
    retenus, ecartes = [], []
    for ini, liste in par_personne.items():
        pers = personnes.get(ini)
        if not pers:
            continue
        candidats = []
        for e in liste:
            # Les cas particuliers (direction médicale) restent publiés quel que soit le statut du mandat.
            if not _actif(e, aujourdhui) or (_exclu(e) and ini not in SPECIAUX):
                continue
            affs = affectations.get(texte(e.get("Clé engagement")).strip(), [])
            if not affs and ini not in SPECIAUX:
                continue
            service = texte(affs[0].get("Service")) if affs else "Clinique"
            poste = " ".join(texte(a.get("Poste")) for a in affs)
            c = SPECIAUX.get(ini, {}).get("c") or _categorie(e, service)
            if c:
                candidats.append((CATS.index(c), e, c, poste))
        if not candidats:
            continue
        candidats.sort(key=lambda x: x[0])
        _, e, c, poste = candidats[0]
        conf = site.get(ini, {})
        if texte(conf.get("Publié sur le site")).strip() == "-":
            ecartes.append({"initiales": ini, "raison": "retiré à la main (Publié sur le site = -)"})
            continue
        if ini not in SPECIAUX and not _presente(e):
            ecartes.append({"initiales": ini, "raison": "aucune demi-journée de présence au registre"})
            continue
        retenus.append((ini, pers, e, c, poste))

    lignes = []
    manques = {"sansPlacesDisponibles": [], "sansPhotoValidee": []}
    for ini, pers, e, c, poste in retenus:
        medecin = c == "psychiatrie"
        special = SPECIAUX.get(ini, {})
        nom = _nom_affiche(pers, medecin)
        sites, jours, en_ligne = _presence(e)
        pdl = places_par_ini.get(ini)
        if special:
            sites, jours = special.get("s", sites), special.get("j", jours)
            en_ligne = special.get("o", en_ligne)
        if pdl and pdl["online"]:
            en_ligne = True
        langues = [x for x in LANGUES if socle.est_actif(pers.get(x))]
        for x in (pdl["langues"] if pdl else []):
            if x not in langues:
                langues.append(x)
        autre = texte(pers.get("Autre langue, laquelle")).strip()
        if autre and autre not in langues:
            langues.append(autre[:1].upper() + autre[1:])
        if not langues:
            langues = ["Français"]
        prof = profils.get(ini, {})
        axes = [texte(prof.get(k)).strip() for k in ("Axe thérapie 1", "Axe thérapie 2", "Axe thérapie complémentaire")]
        axes = [a for a in axes if a and a not in ("-", "x")] or (pdl["axes"] if pdl else [])
        axes = list(dict.fromkeys(AXES.get(a, a) for a in axes))
        age = _ages(prof.get("Âge patients dès"), prof.get("Jusqu'à")) if prof else ""
        if not age and pdl:
            age = _ages(pdl["age"], pdl["jusqu"])
        np, ac, maj = None, False, None
        if c in ("psychiatrie", "psychotherapie"):
            # Médecins : non d'office, oui seulement si des places de psychothérapie sont ouvertes.
            # Psychologues : selon Places disponibles ; « à confirmer » seulement si la ligne annonce
            # des places et a vieilli ; un zéro reste un non, même ancien (Alberto, 01.10.2026).
            if pdl:
                maj = (aujourdhui - pdl["maj"].date()).days if pdl["maj"] else None
                if medecin or pdl["places"] <= 0:
                    np = pdl["places"] > 0
                elif maj is None or maj > SITE["JOURS_FRAICHEUR"]:
                    ac = True
                else:
                    np = True
            else:
                if medecin:
                    np = False
                manques["sansPlacesDisponibles"].append(nom)
        elif c == "infirmiers" and pdl:
            # Soins infirmiers (décision d'Alberto du 01.10.2026) : pas de nombre de places, un statut tenu
            # par l'infirmier. Ouvert, ou suivi léger seulement : oui ; Sur étude : à confirmer ; Complet : non.
            statut = _n(pdl["statut"])
            if statut.startswith("ouvert"):
                np = True
            elif statut.startswith("sur etude"):
                ac = True
            elif statut.startswith("complet"):
                np = False
        conf = site.get(ini, {})
        valide = texte(conf.get("Validé par le collaborateur")).strip().lower() == "x"
        photo = texte(conf.get("Photo")).strip() if valide else ""
        bio = texte(conf.get("Présentation")).strip() if valide else ""
        if not valide:
            manques["sansPhotoValidee"].append(nom)
        fiche = texte(conf.get("Fiche actuelle")).strip()
        slug = _slug(nom)
        lignes.append({
            "n": nom, "c": c, "t": special.get("t") or _titre(c, e, pers, poste), "s": sites, "j": jours,
            "o": bool(en_ligne), "l": langues,
            "u": (SITE["FICHE_BASE"] + "?s=" + slug) if SITE["FICHE_BASE"] else fiche,
            "p": photo, "i": "".join(x[0] for x in pm.jetons(nom)[:1] + pm.jetons(nom)[-1:]).upper(),
            "np": np, "ac": ac, "r": (pdl["liens"] if pdl and np is True else []), "ax": axes, "ag": age,
            "slug": slug, "bio": bio, "comp": (pdl["competences"] if pdl else []),
            "st": (pdl["statut"] if pdl and c == "infirmiers" else ""),
            "sd": (pdl["secteur"] if pdl and c == "infirmiers" else ""),
            "so": (pdl["soins"] if pdl and c == "infirmiers" else []),
            "_tri": _n((texte(pers.get("Nom de famille d'usage")) or texte(pers.get("Nom"))) + " " + nom),
        })
    lignes.sort(key=lambda r: (CATS.index(r["c"]), r["_tri"]))
    for r in lignes:
        r.pop("_tri", None)

    delais = _delais(aujourdhui)
    dispos = []
    for d in DISPOS:
        m = delais.get(d["cle"], {})
        dispos.append({"cle": d["cle"], "libelle": d["libelle"],
                       "places": int(round(total_places)) if d["places"] else None,
                       "delai": m.get("delai"), "mesures": m.get("n", 0)})
        if d["cle"] == "infirmiers":
            # Engagement de l'équipe infirmière (01.10.2026) : toute demande a un premier contact sous deux
            # jours ouvrables ; « ouvert » si au moins un infirmier accueille ou étudie de nouvelles demandes.
            dispos[-1]["engagement"] = "Premier contact sous 2 jours ouvrables"
            dispos[-1]["ouvert"] = any(r["c"] == "infirmiers" and (r["np"] is True or r["ac"]) for r in lignes)
    donnees = {"genere_le": maintenant().strftime("%d.%m.%Y %H:%M"), "source": "Almaval, registres internes",
               "specialistes": lignes, "disponibilites": dispos}
    return {"donnees": donnees, "site": site, "prop": prop, "entetes": entetes, "nbLignes": nb_lignes,
            "retenus": retenus, "ecartes": ecartes, "manques": manques, "placesSansPersonne": sans_personne,
            "delais": delais, "personnes": personnes}


# ------------------------------------------------------------------ écritures

def _completer_onglet(calc, aujourdhui):
    """Ajoute à « Site - Annuaire » les personnes retenues qui n'y sont pas.
    Onglet vide : amorçage depuis la graine des fiches du site (photo, fiche,
    présentation, validées puisque déjà publiques)."""
    site, entetes, prop = calc["site"], calc["entetes"], calc["prop"]
    graine = _graine() if not site else []
    ajouts = []
    for ini, pers, e, c, poste in calc["retenus"]:
        if ini in site:
            continue
        nom = _nom_affiche(pers, c == "psychiatrie")
        g = None
        if graine:
            jp = pm._jetons_personne(pers)
            for f in graine:
                t = pm.jetons(f.get("nom"))
                if len(t) >= 2 and all(x in jp for x in t):
                    g = f
                    break
        if g:
            ajouts.append([ini, nom, g.get("photo", ""), g.get("fiche", ""), g.get("bio", ""), "x", "x",
                           "Repris du site le 30.09.2026"])
        else:
            ajouts.append([ini, nom, "", "", "", "", "x", "Ajout automatique le " + _jour(aujourdhui) +
                           ", photo et présentation à valider par le collaborateur"])
    if not ajouts:
        return []
    ordre = ["Initiales", "Nom affiché", "Photo", "Fiche actuelle", "Présentation", "Validé par le collaborateur",
             "Publié sur le site", "Remarque"]
    lignes = []
    for a in ajouts:
        valeurs = dict(zip(ordre, a))
        lignes.append([valeurs.get(e, "") for e in entetes])
    debut = calc["nbLignes"] + 1
    socle._assurer_dimensions(ID_EFFECTIF, prop, lignes=debut + len(lignes) - 1)
    socle._batch(ID_EFFECTIF, socle._requete_cellules(prop["sheetId"], debut - 1, 0, lignes))
    socle._oublier(ID_EFFECTIF, prop["title"])
    return [{"initiales": a[0], "nom": a[1], "graine": a[5] == "x"} for a in ajouts]


def _deposer(donnees):
    corps = json.dumps(donnees, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    media = MediaInMemoryUpload(corps, mimetype="application/json; charset=utf-8", resumable=False)
    _api("storage", "v1").objects().insert(
        bucket=SITE["BUCKET"], name=SITE["OBJET"], media_body=media,
        body={"name": SITE["OBJET"], "contentType": "application/json; charset=utf-8",
              "cacheControl": "public, max-age=300"}).execute()
    return len(corps)


def passage_site(confirmer=False):
    aujourdhui = maintenant().date()
    with _verrou:
        calc = calculer(aujourdhui)
        ajouts, octets, refus = [], 0, ""
        if confirmer:
            ajouts = _completer_onglet(calc, aujourdhui)
            if ajouts:
                calc = calculer(aujourdhui)
            nombre = len(calc["donnees"]["specialistes"])
            if nombre < PLANCHER:
                # Garde-fou : une lecture partielle des registres ne doit jamais vider le site.
                refus = "dépôt refusé : " + str(nombre) + " spécialistes, plancher " + str(PLANCHER) + " ; le fichier de la veille reste en ligne"
            else:
                octets = _deposer(calc["donnees"])
    d = calc["donnees"]
    par_cat = {}
    for r in d["specialistes"]:
        par_cat.setdefault(r["c"], []).append(r["n"])
    return {
        "moteur": "site_annuaire", "confirme": bool(confirmer), "url": SITE["URL"], "octets": octets,
        "refus": refus,
        "specialistes": len(d["specialistes"]), "parCategorie": {k: len(v) for k, v in par_cat.items()},
        "noms": par_cat, "disponibilites": d["disponibilites"], "delais": calc["delais"],
        "nouveauxPatientsOui": [r["n"] for r in d["specialistes"] if r["np"] is True],
        "aConfirmer": [r["n"] for r in d["specialistes"] if r["ac"]],
        "avecLiens": [r["n"] for r in d["specialistes"] if r["r"]],
        "ajoutsOnglet": ajouts, "ecartes": calc["ecartes"], "manques": calc["manques"],
        "placesSansPersonne": calc["placesSansPersonne"],
        "onglet": "https://docs.google.com/spreadsheets/d/" + ID_EFFECTIF + "/edit#gid=" + str(calc["prop"]["sheetId"]),
    }


@mcp.tool()
@tolerant
def site_annuaire(confirmer: bool = False):
    """Site almaval.ch : recalcule l'annuaire et les disponibilités, dépose annuaire.json (public) ; simulation sans confirmer."""
    return passage_site(confirmer=confirmer)


try:
    _pont_precedent_site = outils_lieux._pont

    def _pont(texte_sujet: str):
        brut = str(texte_sujet or "").strip()
        mots = brut.split()
        premier = mots[0].lower() if mots else ""
        drapeaux = {m.lower() for m in mots[1:] if "=" not in m}
        if premier == "site_annuaire":
            return pont_de_fond("site_annuaire", drapeaux, tolerant(passage_site), dict(confirmer=("confirmer" in drapeaux)))
        return _pont_precedent_site(brut)

    outils_lieux._pont = _pont
except Exception as _exc:  # noqa: BLE001
    print("[site annuaire] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)
