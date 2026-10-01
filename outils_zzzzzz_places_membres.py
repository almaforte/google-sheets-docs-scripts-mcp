"""Almaval - Places disponibles : la liste des thérapeutes tenue par le registre RH, 30.09.2026.

Demande d'Alberto du 30.09.2026 : « le moteur doit mettre et enlever tout
seul qui est là et qui n'y est plus ». Jusqu'ici l'entrée et la sortie
d'une ligne de « Places disponibles » (classeur Almaval - Patients)
n'étaient faites que sur un geste RH : insertion à la validation du contrat
signé (fichier « 15 Places disponibles » du projet Apps Script Onboarding,
action RH), archivage à la clôture d'une sortie (fichier « 67 »). Toute
personne arrivée ou partie par un autre chemin (reprise de l'Organigramme,
engagement clos sans sortie jouée sur la plateforme) restait donc absente,
ou présente à tort : Zaghir absent alors qu'il est médecin en cours, Durox
présente alors que son engagement est clos au 15.09.2026.

Ce module est le balayage quotidien qui manquait. Il ne remplace pas les
deux gestes RH, il rattrape ce qu'ils n'ont pas vu, avec la même géométrie
et le même format d'archive.

Qui a sa ligne. Une personne du Registre - Engagements dont un engagement :
  - est « En cours », ou « À venir » avec une date de début dans les
    MEMBRES["JOURS_AVANT_ARRIVEE"] jours ;
  - n'a pas de date de fin, ou une date de fin égale ou postérieure à
    aujourd'hui ;
  - porte une profession de MEMBRES["PROFESSIONS"] (médecins et
    psychologues : psychothérapie et évaluations) ;
  - n'a pas un statut de collaboration de MEMBRES["STATUTS_EXCLUS"]
    (locataires, jamais référencés nulle part ; partenaires, encadrants et
    superviseurs qui ne suivent pas de patients) ;
  - a une affectation au service Clinique dans le Registre - Affectations ;
  - s'il est « En cours », porte au moins une demi-journée de présence
    (lieu, Télétravail ou Itinérant) : une personne en cours sans aucune
    demi-journée ne vient pas encore (Capozoli Biancarelli, décision
    d'Alberto du 01.10.2026). Un engagement « À venir » garde sa ligne de
    préparation même sans demi-journée.
Tous les médecins en font partie, même sans place (décision d'Alberto du
30.09.2026, qui remplace pour eux le critère du suivi long terme du
14.09.2026).

Ajout. La ligne s'insère à sa place alphabétique dans son bloc (médecins
d'abord, affichés « Dr Nom Prénom », psychologues ensuite), toujours à
l'intérieur du bloc de données pour que les plages bornées des totaux
s'étendent. Contenu, dans cet ordre de priorité croissante : le profil
repris de « Places disponibles - Archive » si la personne y figure (par
position, jamais les lieux, jours, places ni dates), puis le Registre -
Profil clinique (axes, âges, pathologies, compétences, par intitulé), puis
le registre RH : nom d'usage, discipline, classe de formation, langues de
Registre - Personnes, sites cochés et lieu de chaque jour depuis les douze
demi-journées, zéro place sur chaque jour de présence, « Mis à jour le » du
jour. « Itinérant » et « Télétravail » donnent « Télétravail » et cochent
Online : un clinicien sans bureau fixe reçoit en ligne.

Archivage. Une ligne dont la personne n'a plus aucun engagement actif
(tous clos, ou date de fin dépassée) est recopiée par position dans
l'archive, avec « Fin de l'engagement », « Archivé le » et « Motif de
l'archivage », relue, puis retirée de l'onglet vivant. Une personne active
mais locataire ou partenaire est archivée avec ce motif, de même qu'une
personne en cours sans aucune demi-journée (motif « Aucune demi-journée au
registre ») : elle revient d'elle-même, profil repris de l'archive, dès que
ses demi-journées sont saisies. Une ligne sans
correspondance sûre au registre, ou ambiguë, n'est JAMAIS touchée : elle
est signalée dans le compte rendu.

Plafonds par passage : MEMBRES["PLAFOND_AJOUTS"] ajouts et
MEMBRES["PLAFOND_ARCHIVAGES"] archivages. Au-delà, le reste attend le
passage suivant et le compte rendu le dit.

Les colonnes qui débordent d'une matricielle posée dans les lignes
d'en-tête (miroir du nom, jours sans mise à jour, places total) ne sont
jamais écrites.

Outil : places_membres(confirmer). Pont : lieux_cycle avec le sujet
« action:places_membres [confirmer] ». Sans confirmer, rien n'est écrit et
le compte rendu dit ce qui serait fait.
"""

import datetime
import re
import unicodedata

from main import mcp, tolerant

import outils_lieux
import outils_zzzzz_onboarding_0_socle as socle
from outils_zzzzz_onboarding_0_socle import CFG, ID_EFFECTIF, _verrou, date_de, maintenant, pont_de_fond, texte

ID_PLACES = CFG["CLASSEUR_PLACES"]
ONGLET_PLACES = CFG["ONGLET_PLACES"]
ONGLET_ARCHIVE = CFG["ONGLET_PLACES_ARCHIVE"]
LIGNE_TECHNIQUE = CFG["LIGNE_TECHNIQUE_PLACES"]
PREMIERE_DONNEE = LIGNE_TECHNIQUE + 2

MEMBRES = {
    "PROFESSIONS": ["Médecin psychiatre", "Médecin pédopsychiatre", "Médecin", "Psychologue"],
    "STATUTS_EXCLUS": {"locataire": "Locataire, jamais référencé", "partner": "Partenaire, sans suivi de patients"},
    "JOURS_AVANT_ARRIVEE": 45,
    "PLAFOND_AJOUTS": 8,
    "PLAFOND_ARCHIVAGES": 8,
    "SITES": ["Crissier", "Morges", "Lausanne", "Genève", "Vevey", "Jura"],
    "LIEUX": {"crissier": "Crissier", "morges": "Morges", "lausanne": "Lausanne", "lausanne riponne": "Lausanne",
              "la lisiere": "Lausanne", "geneve": "Genève", "vevey": "Vevey", "jura": "Jura",
              "teletravail": "Télétravail", "itinerant": "Télétravail"},
    "JOURS": ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"],
    "LANGUES": {"Français": "F", "Italien": "I", "Anglais": "EN", "Espagnol": "ES", "Portugais": "PT",
                "Allemand": "D", "Arabe": "AR", "Roumain": "RO"},
    "HORS_REPRISE": ["Thérapeute", "Mis à jour le", "Places total", "Places LAMal", "Spécifier le lieu, si places en 2 lieux ≠",
                     "Publié", "Plannings publiés sur la page web personnelle", "Crissier", "Morges", "Lausanne",
                     "Genève", "Vevey", "Jura", "Online", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi",
                     "Lundi - Places", "Mardi - Places", "Mercredi - Places", "Jeudi - Places", "Vendredi - Places",
                     "Samedi - Places", "Lieu", "Places", "Titré", "Classe", "Discipline"],
    "ALIAS_PROFIL": {"Âge patients dès": "Âge patients"},
}

_MARQUES = re.compile("[̀-ͯ]")
SANS_PRESENCE = "aucune demi-journée au registre"


# ------------------------------------------------------------------ noms

def _sans_accent(s):
    return _MARQUES.sub("", unicodedata.normalize("NFD", str("" if s is None else s)))


def jetons(nom):
    """Jetons comparables d'un nom : minuscules, sans accent, tirets et
    apostrophes coupés, titres Dr et Dre retirés."""
    t = _sans_accent(nom).lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return [x for x in t.split() if x and x not in ("dr", "dre")]


def _cle(nom):
    return " ".join(jetons(nom))


def _norm(s):
    return " ".join(jetons(s))


def _meme(a, b):
    return _norm(a) == _norm(b)


def _jour(d):
    return d.strftime("%d.%m.%Y") if d else ""


def _lettre(n):
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


# ------------------------------------------------------------------ registres

def _registres():
    """Personnes (par initiales), engagements, affectations cliniques, profils."""
    personnes = {}
    for l in socle.lire_onglet_de(ID_EFFECTIF, "Registre - Personnes", rafraichir=True, avec_calculees=False).lignes:
        ini = texte(l.get("Initiales")).strip()
        if not ini or ini in personnes:
            continue
        personnes[ini] = l
    engagements = []
    for l in socle.lire_onglet_de(ID_EFFECTIF, "Registre - Engagements", rafraichir=True, avec_calculees=False).lignes:
        if not texte(l.get("Clé engagement")).strip() or not texte(l.get("Initiales")).strip():
            continue
        engagements.append(l)
    cliniques = set()
    for l in socle.lire_onglet_de(ID_EFFECTIF, "Registre - Affectations", rafraichir=True, avec_calculees=False).lignes:
        if not _meme(l.get("Service"), "Clinique"):
            continue
        if _meme(l.get("État de l'engagement"), "Clos"):
            continue
        fin = date_de(l.get("Date de fin"))
        if fin and fin.date() < maintenant().date():
            continue
        cliniques.add(texte(l.get("Clé engagement")).strip())
    profils = {}
    try:
        onglet = socle.lire_onglet_de(ID_EFFECTIF, "Registre - Profil clinique", rafraichir=True, avec_calculees=False)
        for l in onglet.lignes:
            ini = texte(l.get("Initiales")).strip()
            if ini:
                profils[ini] = l
    except Exception:  # noqa: BLE001
        profils = {}
    return personnes, engagements, cliniques, profils


def _actif(e, aujourdhui):
    """Engagement actif au sens du registre : ni clos, ni échu."""
    if _meme(e.get("État de l'engagement"), "Clos"):
        return False
    fin = date_de(e.get("Date de fin"))
    return not (fin and fin.date() < aujourdhui)


def _statut_exclu(e):
    s = _norm(e.get("Statut de collaboration"))
    for cle, motif in MEMBRES["STATUTS_EXCLUS"].items():
        if s.startswith(cle):
            return motif
    return None


def _presente(e):
    """Vrai si l'engagement porte au moins une demi-journée de présence (lieu, Télétravail ou Itinérant)."""
    for jour in MEMBRES["JOURS"]:
        for moment in ("matin", "après-midi"):
            brut = _norm(e.get(jour + " " + moment))
            if brut and brut != "non travaille":
                return True
    return False


def _profession_ok(e):
    return any(_meme(e.get("Profession"), p) for p in MEMBRES["PROFESSIONS"])


def _candidat(e, aujourdhui, cliniques):
    """None si l'engagement donne une ligne, sinon la raison du refus."""
    etat = _norm(e.get("État de l'engagement"))
    if etat not in ("en cours", "a venir"):
        return "état " + texte(e.get("État de l'engagement"))
    if not _actif(e, aujourdhui):
        return "échu"
    if etat == "a venir":
        debut = date_de(e.get("Date de début"))
        if debut and (debut.date() - aujourdhui).days > MEMBRES["JOURS_AVANT_ARRIVEE"]:
            return "arrivée le " + _jour(debut)
    if not _profession_ok(e):
        return "profession " + (texte(e.get("Profession")) or "vide")
    motif = _statut_exclu(e)
    if motif:
        return motif
    if texte(e.get("Clé engagement")).strip() not in cliniques:
        return "sans affectation au service Clinique"
    if etat == "en cours" and not _presente(e):
        return SANS_PRESENCE
    return None


def _jetons_personne(p):
    morceaux = [p.get("Nom"), p.get("Prénom"), p.get("Nom prénom"), p.get("Nom d'usage"),
                p.get("Nom de famille d'usage"), p.get("Prénom d'usage"), p.get("Noms antérieurs")]
    return set(j for m in morceaux for j in jetons(m))


def _correspondances(nom_ligne, personnes, index_jetons):
    t = jetons(nom_ligne)
    if len(t) < 2:
        return []
    return [ini for ini in personnes if all(x in index_jetons[ini] for x in t)]


# ------------------------------------------------------------------ onglet vivant

def _lire_places():
    classeur = socle._classeur(ID_PLACES, rafraichir=True)
    prop = socle._onglet(classeur, ONGLET_PLACES)
    if prop is None:
        raise ValueError("Onglet introuvable : " + ONGLET_PLACES)
    socle._oublier(ID_PLACES, prop["title"])
    grille = socle._lire_grille(ID_PLACES, prop["title"])
    technique = [texte(e).strip() for e in (grille[LIGNE_TECHNIQUE - 1] if len(grille) >= LIGNE_TECHNIQUE else [])]
    visibles = [texte(e).strip() for e in (grille[LIGNE_TECHNIQUE] if len(grille) > LIGNE_TECHNIQUE else [])]
    largeur = max(len(technique), len(visibles), max([len(l) for l in grille] + [0]))
    technique += [""] * (largeur - len(technique))
    visibles += [""] * (largeur - len(visibles))
    col_nom = 0
    for i, e in enumerate(technique):
        if not col_nom and _meme(e, "Thérapeute"):
            col_nom = i + 1
    if not col_nom:
        raise ValueError("La ligne technique de Places disponibles ne porte pas « Thérapeute ».")
    # colonnes qui débordent d'une matricielle posée au-dessus des données
    plage = "'" + prop["title"].replace("'", "''") + "'!1:" + str(PREMIERE_DONNEE - 1)
    rep = socle._executer(socle._feuilles().values().get(spreadsheetId=ID_PLACES, range=plage, valueRenderOption="FORMULA"))
    debordement = set()
    for rangee in rep.get("values", []):
        for i, f in enumerate(rangee):
            if isinstance(f, str) and re.search(r"ARRAYFORMULA|^=\s*\{", f, re.I):
                debordement.add(i + 1)
    lignes, ligne_totaux = [], 0
    for numero in range(PREMIERE_DONNEE, len(grille) + 1):
        valeurs = list(grille[numero - 1]) + [""] * (largeur - len(grille[numero - 1]))
        nom = texte(valeurs[col_nom - 1]).strip()
        if _meme(nom, "Total"):
            ligne_totaux = numero
            break
        if not nom:
            continue
        lignes.append({"numero": numero, "nom": nom, "cle": _cle(nom), "valeurs": valeurs})
    if not ligne_totaux:
        raise ValueError("Ligne de totaux introuvable dans Places disponibles.")

    def colonne(nom, derniere=False, visible=False):
        entetes = visibles if visible else technique
        pos = [i + 1 for i, e in enumerate(entetes) if e and _meme(e, nom)]
        if not pos:
            return 0
        return pos[-1] if derniere else pos[0]

    return {"prop": prop, "grille": grille, "technique": technique, "visibles": visibles, "largeur": largeur,
            "colNom": col_nom, "debordement": debordement, "lignes": lignes, "ligneTotaux": ligne_totaux,
            "colonne": colonne}


def _est_medecin_ligne(p, l):
    c = p["colonne"]("Discipline")
    d = texte(l["valeurs"][c - 1]).strip() if c else ""
    return _meme(d, "Médecin") if d else bool(re.match(r"^\s*dr\.?\s", l["nom"], re.I))


# ------------------------------------------------------------------ archive

def _lire_archive():
    classeur = socle._classeur(ID_PLACES)
    prop = socle._onglet(classeur, ONGLET_ARCHIVE)
    if prop is None:
        raise ValueError("Onglet introuvable : " + ONGLET_ARCHIVE)
    socle._oublier(ID_PLACES, prop["title"])
    grille = socle._lire_grille(ID_PLACES, prop["title"])
    # la DERNIÈRE des cinq premières lignes qui porte « Thérapeute » : la
    # ligne 2 de l'archive est une bande qui le porte aussi.
    rang = -1
    for i in range(min(5, len(grille))):
        if any(_meme(v, "Thérapeute") for v in grille[i]):
            rang = i
    if rang < 0:
        raise ValueError("Ligne d'en-têtes introuvable dans " + ONGLET_ARCHIVE)
    entetes = [texte(e).strip() for e in grille[rang]]
    return {"prop": prop, "grille": grille, "entetes": entetes, "rang": rang}


def _profil_archive(arch, cle):
    """La DERNIÈRE ligne archivée de la personne, par position, ou None."""
    trouve = None
    col = None
    for i, e in enumerate(arch["entetes"]):
        if col is None and _meme(e, "Thérapeute"):
            col = i
    if col is None:
        return None
    for r in range(arch["rang"] + 1, len(arch["grille"])):
        if _cle(arch["grille"][r][col]) == cle:
            trouve = arch["grille"][r]
    return trouve


# ------------------------------------------------------------------ calcul

def _nom_affiche(pers, medecin):
    nom = texte(pers.get("Nom de famille d'usage")).strip() or texte(pers.get("Nom")).strip()
    prenom = texte(pers.get("Prénom d'usage")).strip() or texte(pers.get("Prénom")).strip()
    return ("Dr " if medecin else "") + (nom + " " + prenom).strip()


def _lieux_du_registre(e):
    """{jour: lieu} depuis les douze demi-journées : la ville du matin, ou de l'après-midi."""
    lieux = {}
    for jour in MEMBRES["JOURS"]:
        vus = []
        for moment in ("matin", "après-midi"):
            brut = _norm(e.get(jour + " " + moment))
            lieu = MEMBRES["LIEUX"].get(brut)
            if lieu and lieu not in vus:
                vus.append(lieu)
        villes = [v for v in vus if v != "Télétravail"]
        if villes:
            lieux[jour] = villes[0]
        elif vus:
            lieux[jour] = "Télétravail"
    return lieux


def _meilleur_engagement(liste):
    def rang(e):
        etat = _norm(e.get("État de l'engagement"))
        return (0 if etat == "en cours" else 1, -(date_de(e.get("Date de début")) or datetime.datetime(1900, 1, 1)).toordinal())
    return sorted(liste, key=rang)[0]


def _valeurs_nouvelle_ligne(p, pers, e, profil, reprise, medecin, aujourdhui):
    """{numéro de colonne: valeur} pour la ligne neuve."""
    v = {}

    def poser(nom, valeur, derniere=False, visible=False):
        c = p["colonne"](nom, derniere=derniere, visible=visible)
        if c and c not in p["debordement"]:
            v[c] = valeur

    # 1. profil archivé, par position, hors lieux, jours, places et dates
    if reprise:
        for i in range(min(len(reprise), p["largeur"])):
            c = i + 1
            if c in p["debordement"]:
                continue
            titre = p["technique"][i] or p["visibles"][i]
            if not titre or any(_meme(titre, h) for h in MEMBRES["HORS_REPRISE"]):
                continue
            val = reprise[i]
            if val is None or texte(val).strip() == "":
                continue
            v[c] = val
    # 2. registre du profil clinique, par intitulé visible puis technique
    if profil:
        for titre, val in profil.items():
            if titre.startswith("_") or titre in ("Initiales", "Nom prénom", "Discipline"):
                continue
            if val is None or texte(val).strip() == "":
                continue
            cible = MEMBRES["ALIAS_PROFIL"].get(titre, titre)
            c = p["colonne"](cible, visible=True) or p["colonne"](cible)
            if c and c not in p["debordement"]:
                v[c] = val
    # 3. registre RH
    affichage = _nom_affiche(pers, medecin)
    if reprise:
        col_nom = p["colNom"] - 1
        ancien = texte(reprise[col_nom]).strip() if col_nom < len(reprise) else ""
        if ancien and _cle(ancien) == _cle(affichage):
            affichage = ancien
    poser("Thérapeute", affichage)
    poser("Discipline", "Médecin" if medecin else "Psychologue")
    classe = texte(pers.get("Classe de formation")).strip()
    if classe:
        poser("Titré", classe)
    elif texte(pers.get("Titre obtenu")).strip():
        poser("Titré", "T")
    for langue, code in MEMBRES["LANGUES"].items():
        if socle.est_actif(pers.get(langue)):
            poser(code, "x")
    autre = texte(pers.get("Autre langue, laquelle")).strip()
    if autre:
        poser("Autre", autre)
    lieux = _lieux_du_registre(e)
    for site in MEMBRES["SITES"]:
        if site in lieux.values():
            poser(site, "x")
    if "Télétravail" in lieux.values():
        poser("Online", "x")
    for jour in MEMBRES["JOURS"]:
        if jour in lieux:
            poser(jour, lieux[jour])
            poser(jour + " - Places", 0)
    d = datetime.datetime(aujourdhui.year, aujourdhui.month, aujourdhui.day)
    poser("Mis à jour le", socle.serial_de(d))
    return affichage, v, lieux


def calculer(aujourdhui=None):
    aujourdhui = aujourdhui or maintenant().date()
    personnes, engagements, cliniques, profils = _registres()
    index_jetons = {ini: _jetons_personne(pers) for ini, pers in personnes.items()}
    par_personne = {}
    for e in engagements:
        par_personne.setdefault(texte(e.get("Initiales")).strip(), []).append(e)

    candidats, refus = {}, {}
    for ini, liste in par_personne.items():
        bons = [e for e in liste if _candidat(e, aujourdhui, cliniques) is None]
        if bons:
            candidats[ini] = _meilleur_engagement(bons)
        else:
            refus[ini] = [_candidat(e, aujourdhui, cliniques) for e in liste]

    p = _lire_places()
    presents, sans_correspondance, ambigues, a_archiver, hors_critere = {}, [], [], [], []
    for l in p["lignes"]:
        inis = _correspondances(l["nom"], personnes, index_jetons)
        if not inis:
            sans_correspondance.append({"ligne": l["numero"], "nom": l["nom"]})
            continue
        if len(inis) > 1:
            ambigues.append({"ligne": l["numero"], "nom": l["nom"], "personnes": inis})
            continue
        ini = inis[0]
        presents.setdefault(ini, []).append(l)
        if ini in candidats:
            continue
        liste = par_personne.get(ini, [])
        actifs = [e for e in liste if _actif(e, aujourdhui)]
        if not actifs:
            fins = [date_de(e.get("Date de fin")) for e in liste if date_de(e.get("Date de fin"))]
            a_archiver.append({"ligne": l["numero"], "nom": l["nom"], "initiales": ini,
                               "fin": _jour(max(fins)) if fins else "",
                               "motif": "Engagement clos" if liste else "Aucun engagement au registre"})
            continue
        motifs = [_statut_exclu(e) for e in actifs if _statut_exclu(e)]
        if motifs and all(_statut_exclu(e) for e in actifs):
            a_archiver.append({"ligne": l["numero"], "nom": l["nom"], "initiales": ini, "fin": "", "motif": motifs[0]})
            continue
        if {_candidat(e, aujourdhui, cliniques) for e in actifs} == {SANS_PRESENCE}:
            a_archiver.append({"ligne": l["numero"], "nom": l["nom"], "initiales": ini, "fin": "",
                               "motif": "Aucune demi-journée au registre"})
            continue
        hors_critere.append({"ligne": l["numero"], "nom": l["nom"], "initiales": ini,
                             "raisons": sorted(set(_candidat(e, aujourdhui, cliniques) or "" for e in actifs))})
    doublons = [{"initiales": ini, "lignes": [l["numero"] for l in ls]} for ini, ls in presents.items() if len(ls) > 1]

    a_ajouter = []
    for ini, e in sorted(candidats.items(), key=lambda kv: _cle(kv[1].get("Nom prénom"))):
        if ini in presents:
            continue
        pers = personnes.get(ini)
        if not pers:
            continue
        medecin = _norm(e.get("Profession")).startswith("medecin")
        a_ajouter.append({"initiales": ini, "cle": _cle(_nom_affiche(pers, medecin)), "medecin": medecin,
                          "engagement": texte(e.get("Clé engagement")), "etat": texte(e.get("État de l'engagement")),
                          "profession": texte(e.get("Profession")), "nom": _nom_affiche(pers, medecin)})

    return {"aujourdhui": _jour(aujourdhui), "p": p, "personnes": personnes, "profils": profils,
            "candidats": candidats, "aAjouter": a_ajouter, "aArchiver": a_archiver,
            "sansCorrespondance": sans_correspondance, "ambigues": ambigues, "doublons": doublons,
            "horsCritere": hors_critere, "refus": refus, "lignesVues": len(p["lignes"]), "candidatsVus": len(candidats)}


# ------------------------------------------------------------------ écriture

def _requete_copie_format(sid, source, cible, largeur):
    reqs = []
    for type_ in ("PASTE_FORMAT", "PASTE_DATA_VALIDATION"):
        reqs.append({"copyPaste": {
            "source": {"sheetId": sid, "startRowIndex": source - 1, "endRowIndex": source,
                       "startColumnIndex": 0, "endColumnIndex": largeur},
            "destination": {"sheetId": sid, "startRowIndex": cible - 1, "endRowIndex": cible,
                            "startColumnIndex": 0, "endColumnIndex": largeur},
            "pasteType": type_, "pasteOrientation": "NORMAL"}})
    return reqs


def _requetes_valeurs(sid, numero, valeurs, debordement, largeur, effacer=False):
    """Écrit {colonne: valeur} sur une ligne ; avec effacer, vide d'abord les
    colonnes écrivables absentes du dict. Jamais une colonne de débordement."""
    reqs = []
    for c in range(1, largeur + 1):
        if c in debordement:
            continue
        if c in valeurs:
            reqs.extend(socle._requete_cellules(sid, numero - 1, c - 1, [[valeurs[c]]]))
        elif effacer:
            reqs.append({"updateCells": {"range": {"sheetId": sid, "startRowIndex": numero - 1, "endRowIndex": numero,
                                                   "startColumnIndex": c - 1, "endColumnIndex": c},
                                         "fields": "userEnteredValue"}})
    return reqs


def _ajouter(fiche, aujourdhui, personnes, profils, candidats):
    """Insère une ligne, relue ensuite. Rend le compte rendu de la ligne."""
    p = _lire_places()
    sid = p["prop"]["sheetId"]
    ini = fiche["initiales"]
    pers = personnes[ini]
    e = candidats[ini]
    medecin = fiche["medecin"]
    cle = fiche["cle"]
    for l in p["lignes"]:
        if l["cle"] == cle:
            return {"nom": fiche["nom"], "etat": "déjà présente", "ligne": l["numero"]}
    try:
        arch = _lire_archive()
        reprise = _profil_archive(arch, cle)
    except Exception:  # noqa: BLE001
        reprise = None
    affichage, valeurs, lieux = _valeurs_nouvelle_ligne(p, pers, e, profils.get(ini), reprise, medecin, aujourdhui)

    bloc = [l for l in p["lignes"] if _est_medecin_ligne(p, l) == medecin]
    suivante = next((l for l in bloc if l["cle"] > cle), None)
    if suivante:
        index, permuter = suivante["numero"], False
    elif medecin and any(not _est_medecin_ligne(p, l) for l in p["lignes"]):
        index, permuter = next(l for l in p["lignes"] if not _est_medecin_ligne(p, l))["numero"], False
    else:
        index, permuter = p["ligneTotaux"] - 1, True
    largeur = p["largeur"]
    # Première ligne de données : une ligne insérée AU-DESSUS du bloc
    # décalerait le début des plages bornées ($CE$4 deviendrait $CE$5, et
    # la matricielle de « Places total » se décalerait d'une ligne, ce qui
    # est arrivé au premier passage du 30.09.2026). On insère donc sous la
    # première ligne, on y descend ses valeurs, et la ligne neuve prend la
    # première place.
    haut = (index == PREMIERE_DONNEE and not permuter)
    if haut:
        index = PREMIERE_DONNEE + 1
    reqs = [{"insertDimension": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": index - 1, "endIndex": index},
                                 "inheritFromBefore": haut}}]
    reqs.extend(_requete_copie_format(sid, index - 1 if haut else index + 1, index, largeur))
    if haut:
        premiere = p["grille"][PREMIERE_DONNEE - 1]
        anciennes = {c: premiere[c - 1] for c in range(1, largeur + 1)
                     if c not in p["debordement"] and c - 1 < len(premiere) and texte(premiere[c - 1]).strip() != ""}
        reqs.extend(_requetes_valeurs(sid, index, anciennes, p["debordement"], largeur))
        reqs.extend(_requetes_valeurs(sid, PREMIERE_DONNEE, valeurs, p["debordement"], largeur, effacer=True))
        cible = PREMIERE_DONNEE
    elif permuter:
        # la dernière ligne de données descend en index + 1 : elle remonte
        # en index, la ligne neuve prend sa place, plages bornées étendues.
        ancienne = p["grille"][index - 1]
        anciennes = {c: ancienne[c - 1] for c in range(1, largeur + 1)
                     if c not in p["debordement"] and c - 1 < len(ancienne) and texte(ancienne[c - 1]).strip() != ""}
        reqs.extend(_requetes_valeurs(sid, index, anciennes, p["debordement"], largeur))
        reqs.extend(_requetes_valeurs(sid, index + 1, valeurs, p["debordement"], largeur, effacer=True))
        cible = index + 1
    else:
        reqs.extend(_requetes_valeurs(sid, index, valeurs, p["debordement"], largeur))
        cible = index
    socle._batch(ID_PLACES, reqs)
    socle._oublier(ID_PLACES, p["prop"]["title"])
    relu = _lire_places()
    ligne = next((l for l in relu["lignes"] if l["numero"] == cible), None)
    conforme = bool(ligne and ligne["cle"] == _cle(affichage))
    return {"nom": affichage, "etat": "ajoutée" if conforme else "relecture non conforme", "ligne": cible,
            "engagement": fiche["engagement"], "repriseArchive": bool(reprise), "profilClinique": ini in profils,
            "lieux": lieux, "colonnesEcrites": len(valeurs)}


def _archiver(fiche, aujourdhui):
    p = _lire_places()
    ligne = next((l for l in p["lignes"] if l["numero"] == fiche["ligne"] and l["nom"] == fiche["nom"]), None)
    if ligne is None:
        ligne = next((l for l in p["lignes"] if l["nom"] == fiche["nom"]), None)
    if ligne is None:
        return {"nom": fiche["nom"], "etat": "introuvable au moment d'archiver"}
    arch = _lire_archive()
    ha = arch["entetes"]
    col_nom = p["colNom"]
    if not (col_nom - 1 < len(ha) and _meme(ha[col_nom - 1], "Thérapeute")):
        raise ValueError("Les colonnes de l'archive ne correspondent plus à celles de Places disponibles")
    nb = len(ha)
    rangee = [(ligne["valeurs"][j] if j < len(ligne["valeurs"]) else "") for j in range(nb)]
    for titre, val in (("Fin de l'engagement", fiche.get("fin", "")), ("Archivé le", _jour(aujourdhui)),
                       ("Motif de l'archivage", fiche["motif"])):
        if titre in ha:
            rangee[ha.index(titre)] = val
    libre = len(arch["grille"]) + 1
    socle._assurer_dimensions(ID_PLACES, arch["prop"], lignes=libre, colonnes=nb)
    socle._batch(ID_PLACES, socle._requete_cellules(arch["prop"]["sheetId"], libre - 1, 0, [rangee]))
    socle._oublier(ID_PLACES, arch["prop"]["title"])
    relu = socle._lire_grille(ID_PLACES, arch["prop"]["title"])
    lu = relu[libre - 1][col_nom - 1] if libre - 1 < len(relu) and col_nom - 1 < len(relu[libre - 1]) else ""
    if _cle(lu) != ligne["cle"]:
        return {"nom": fiche["nom"], "etat": "relecture de l'archive non conforme, ligne vivante laissée en place"}
    socle._batch(ID_PLACES, [{"deleteDimension": {"range": {"sheetId": p["prop"]["sheetId"], "dimension": "ROWS",
                                                             "startIndex": ligne["numero"] - 1, "endIndex": ligne["numero"]}}}])
    socle._oublier(ID_PLACES, p["prop"]["title"])
    return {"nom": fiche["nom"], "etat": "archivée", "ligneArchive": libre, "motif": fiche["motif"], "fin": fiche.get("fin", "")}


def passage_membres(confirmer=False):
    aujourdhui = maintenant().date()
    with _verrou:
        calc = calculer(aujourdhui)
        ajouts = calc["aAjouter"][:MEMBRES["PLAFOND_AJOUTS"]]
        archivages = sorted(calc["aArchiver"], key=lambda f: -f["ligne"])[:MEMBRES["PLAFOND_ARCHIVAGES"]]
        faits_archives, faits_ajouts = [], []
        if confirmer:
            for f in archivages:
                try:
                    faits_archives.append(_archiver(f, aujourdhui))
                except Exception as exc:  # noqa: BLE001
                    faits_archives.append({"nom": f["nom"], "etat": "erreur", "detail": str(exc)[:300]})
            for f in ajouts:
                try:
                    faits_ajouts.append(_ajouter(f, aujourdhui, calc["personnes"], calc["profils"], calc["candidats"]))
                except Exception as exc:  # noqa: BLE001
                    faits_ajouts.append({"nom": f["nom"], "etat": "erreur", "detail": str(exc)[:300]})
    lien = "https://docs.google.com/spreadsheets/d/" + ID_PLACES + "/edit#gid=" + str(calc["p"]["prop"]["sheetId"])
    return {
        "moteur": "places_membres", "confirme": bool(confirmer), "aujourdhui": calc["aujourdhui"], "lien": lien,
        "lignesVues": calc["lignesVues"], "candidats": calc["candidatsVus"],
        "aAjouter": [{k: f[k] for k in ("nom", "initiales", "engagement", "etat", "profession")} for f in calc["aAjouter"]],
        "aArchiver": calc["aArchiver"],
        "reportesAuPassageSuivant": {"ajouts": max(0, len(calc["aAjouter"]) - len(ajouts)),
                                     "archivages": max(0, len(calc["aArchiver"]) - len(archivages))},
        "ajoutes": faits_ajouts, "archives": faits_archives,
        "sansCorrespondance": calc["sansCorrespondance"], "ambigues": calc["ambigues"], "doublons": calc["doublons"],
        "actifsHorsCritere": calc["horsCritere"],
    }


# ------------------------------------------------------------------ outil et pont

@mcp.tool()
@tolerant
def places_membres(confirmer: bool = False):
    """Places disponibles : ajoute les thérapeutes actifs du registre qui manquent, archive ceux qui sont partis ; simulation sans confirmer."""
    return passage_membres(confirmer=confirmer)


try:
    _pont_precedent_membres = outils_lieux._pont

    def _pont(texte_sujet: str):
        brut = str(texte_sujet or "").strip()
        mots = brut.split()
        premier = mots[0].lower() if mots else ""
        drapeaux = {m.lower() for m in mots[1:] if "=" not in m}
        if premier == "places_membres":
            return pont_de_fond("places_membres", drapeaux, tolerant(passage_membres), dict(confirmer=("confirmer" in drapeaux)))
        return _pont_precedent_membres(brut)

    outils_lieux._pont = _pont
except Exception as _exc:  # noqa: BLE001
    print("[places membres] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)
