"""Almaval - onboarding porte en Python sous gestion@ : archivage et passage de nuit des sorties, 27.09.2026.

Deux moteurs de nuit du projet Apps Script « Almaval - RH - Onboarding des
collaborateurs », transcrits a l'identique sur le socle
outils_zzzzz_onboarding_0_socle. Les deux declarations gagnantes sont dans
« 67 Sortie, structure et automatismes du 26 09 2026 », charge apres « 10 »,
« 11 », « 17 » et « 65 » (ORDRE.txt) ; aucune enveloppe ne les habille
ensuite (REASSIGNATIONS.txt : les seules enveloppes de « 67 » portent sur
ouvrirSortie, envoyerLienSortie et preparerContinuiteClinique, qui sont
des actions RH, pas des moteurs de nuit).

  1. archiverLesSorties (4 h). Lit « Saisie - Collaborateurs » et le
     « Registre - Engagements » du classeur Effectif ; une ligne dont
     l'engagement est « Clos » au registre est archivee, sauf si sa sortie
     est ouverte par les RH (Annoncee, En cours, Documents remis), auquel
     cas elle est gardee jusqu'a « Clore la sortie ». L'archivage
     (archiverLaLigneDeSaisie_ de « 67 », par INTITULE) copie la ligne dans
     « Saisie - Archive » (intitules manquants ajoutes a droite, « Archivee
     le », « Motif de l'archivage »), vide la ligne de la saisie sans la
     supprimer, puis finalise la sortie (finaliserLaSortie67_) : si la
     sortie est ouverte et sa date passee, la ligne du therapeute passe de
     « Places disponibles » a « Places disponibles - Archive » (classeur
     Almaval - Patients) et les dossiers RH (1a) et personnel (1b) sont
     ranges aux anciens, l'acces du sortant au 1b retire ; le suivi
     (« Sortie - Suivi », taches 465 et 590) est pose.

  2. passageQuotidienDesSorties (4 h 15). Pour chaque sortie ouverte de la
     saisie, reporte au suivi ce qui se constate : page de sortie soumise
     (32, 35), instructions acceptees (35), date de sortie inscrite au
     registre Effectif (45, 560), liste des patients dans « Sortie -
     Continuite clinique » (150), certificat remis (250), entretien fait
     (550). Puis finalise les sorties closes avant leur date : lignes de
     « Saisie - Archive » archivees depuis le 26.09.2026, avec un statut de
     sortie, hors ligne d'essai, dont les taches 465 et 590 ne sont pas
     toutes reglees.

  3. Ouverture automatique des sorties (28.09.2026, en tete du passage de
     4 h 15). Une ligne de « Saisie - Collaborateurs » qui porte une « Date
     sortie », des initiales et aucun « Statut de la sortie » est ouverte
     en appelant l'Action RH « Ouvrir la sortie » par la porte d'Onboarding
     (03.10.2026). La ligne d'essai (Nom = Essai) est laissee a la chaine
     d'essai.

  4. Conditions d'application (28.09.2026, a chaque passage, pour chaque
     sortie ouverte). La colonne « Condition d'application » de « Sortie -
     Actions » dit de quoi depend une tache conditionnelle. Termes separes
     par « | » (l'un suffit) ; un terme est un intitule de colonne de la
     fiche (« Impôts source »), prefixe « registre: » pour une colonne du
     Registre - Engagements (« registre:Encadrant »), suffixe « # » pour un
     nombre ou un montant dont le vide vaut zero (« Carte repas (CHF/mois)#
     »), ou « Colonne = valeur » pour une egalite ; le suffixe « [soumise] »
     n'evalue la regle qu'une fois la page de sortie soumise (colonnes
     remplies par le collaborateur). Lecture d'une valeur : « oui » si elle
     porte quelque chose qui n'est pas une negation (« - », Non, Pas
     nécessaire, 0), « non » sur une negation explicite ou un nombre vide,
     « inconnu » sur une cellule vide. Si tous les termes disent « non », la
     tache encore A faire passe Sans objet, datee, signee « Moteur de sortie
     », avec la lecture dans la remarque ; une tache que le moteur avait
     mise Sans objet et dont la condition devient « oui » est rouverte A
     faire. Une regle « inconnue » ne touche a rien.

Aucun des deux premiers moteurs ne met de courriel en file et aucun des
quatre ne produit de Google Doc : la file et l'API Docs ne sont pas
sollicitees ici.

Sans confirmer, passage_archivage() et passage_sorties() lisent tout,
calculent tout et rendent ce qu'ils ecriraient (cellules, lignes ajoutees,
lignes videes ou supprimees, par onglet, et actions Drive), sans rien
ecrire ; avec confirmer, ils ecrivent et rendent le meme compte rendu plus
le texte de retour d'origine (resultat). Les onglets lus le sont une fois
par passage et tenus a jour en memoire au fil des ecritures, la ou
l'original relisait l'onglet a chaque appel : le resultat est le meme.

Outils : onboarding_archiver_sorties(confirmer), onboarding_sorties(confirmer).
Pont : lieux_cycle avec le sujet « action:onboarding_archiver_sorties
[confirmer] » et « action:onboarding_sorties [confirmer] ».
"""

import datetime
import re

from main import mcp, tolerant, run_web_app

import outils_lieux
from outils_zzzzz_distributeur import Date, _batch, _batch_avec_reponse, _classeur, _executer, _lire_grille, \
    _oublier, _onglet, _onglet_exige, _requete_cellules, _requete_effacer
from outils_zzzzz_onboarding_0_socle import (
    pont_de_fond,
    CFG, CFG_MUT, COL, COL_SORTIE, COL_SUIVI, ID_EFFECTIF, ID_GESTION, Onglet, TYPE_DOSSIER, _verrou, aujourdhui,
    cellule_vide_mut, date_de, deplacer_fichier, drive, ecrire_lignes, ecrire_objet, en_jour, est_actif, fichier,
    horodatage, lire_onglet, lire_onglet_de, liste_de_texte, maintenant, meme_texte, normaliser, serial_de,
    supprimer_lignes, texte, URL_APPLICATION,
)

# ------------------------------------------------ 67 Sortie, constantes

SORTIE67 = {
    "FAIT_PAR": "Moteur de sortie",
    "ANCIENS_RH": "157LVJQnsypEVoG8_b4CtdEdeG7Nv1kle",         # 1a, Collaborateurs - Anciens
    "ANCIENS_PERSONNEL": "1E0ScoMAO_0t-SoTApMs33c1wwSLLE-Hb",  # 1b, 1 Anciens collaborateurs
    "DEBUT_FINALISATION": "20260926",                          # archivages anterieurs laisses tels quels
    "ETATS_OUVERTS": ["Annoncée", "En cours", "Documents remis"],
    "OUVERTURE_AUTOMATIQUE": True,                              # 28.09.2026, en tete du passage de 4 h 15
}
CLE_SORTIE = "Clé engagement"          # 10 Sortie, CLE_SORTIE_
COL_ARCHIVE_LE = "Archivée le"
COL_MOTIF_ARCHIVAGE = "Motif de l'archivage"
RANG_ETAT = {"": 0, "À faire": 0, "Bloqué": 0, "En cours": 1, "Fait": 2, "Sans objet": 2}
COL_CONDITION = "Condition d'application"     # Sortie - Actions, colonne N depuis le 28.09.2026
NEGATIONS = {"-", "non", "no", "pas nécessaire", "pas necessaire", "0", "false", "faux", "aucun", "aucune", "néant", "neant"}


# ------------------------------------------------ outils de valeurs

def _s(v):
    """String(v || '') d'Apps Script : vide pour None, false et 0."""
    if v is None or v == "" or v is False:
        return ""
    if isinstance(v, (int, float)) and not isinstance(v, bool) and v == 0:
        return ""
    return texte(v)


def _est_date(v):
    """v instanceof Date : une Date du distributeur, jamais un texte."""
    return isinstance(v, Date)


def _jour(v):
    """jour67_ : aaaammjj d'une Date, vide sinon."""
    d = date_de(v) if _est_date(v) else None
    return d.strftime("%Y%m%d") if d else ""


def _nombre_js(v):
    """Number(v) de JavaScript : 0 pour vide, NaN pour un texte illisible."""
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    t = str("" if v is None else v).strip()
    if t == "":
        return 0.0
    try:
        return float(t)
    except ValueError:
        return float("nan")


def _vrai(v):
    """vrai67_ : coche, x, oui, si, yes, true."""
    if v is True:
        return True
    t = normaliser(v)
    return t in ("x", "oui", "si", "yes", "true")


def _jetons(t):
    """jetons67_ : sans civilite, minuscules, lettres non ASCII remplacees par
    une espace (comme l'original), morceaux de plus d'une lettre."""
    brut = re.sub(r"^\s*(dr|dre|mme|m)\.?\s+", "", str(t or ""), flags=re.I)
    n = re.sub(r"[^a-z0-9\s-]", " ", normaliser(brut))
    return [x for x in re.split(r"[\s-]+", n) if len(x) > 1]


def _ajouter_remarque(ancienne, nouvelle):
    a = _s(ancienne).strip()
    if not nouvelle:
        return a
    if nouvelle in a:
        return a
    return a + " | " + nouvelle if a else nouvelle


def _id_depuis_url(url):
    """idDepuisUrl_ de « 05 » : le premier mot de 25 caracteres ou plus."""
    if not url:
        return ""
    m = re.search(r"[-A-Za-z0-9_]{25,}", url)
    return m.group(0) if m else url


def _cle_de_la_saisie(ligne):
    """cleDeLaSaisie_ de « 13 » : Initiales-N° d'engagement, 1 a defaut."""
    initiales = _s(ligne.get(COL["INITIALES"])).strip()
    if not initiales:
        return ""
    v = ligne.get(COL["NUMERO_ENGAGEMENT"])
    numero = ("" if v is None else texte(v)).strip()
    return initiales + "-" + (numero or "1")


def _cle_de_sortie(ligne):
    """cleDeSortie_ de « 10 » : la cle d'engagement portee par la ligne."""
    return _s(ligne.get(CLE_SORTIE)).strip()


def _ligne_de_cette_sortie(l, colonne_cle, cle, initiales):
    """ligneDeCetteSortie_ de « 10 » : par cle d'engagement, a defaut par initiales."""
    if cle and colonne_cle and _s(l.get(CLE_SORTIE)).strip():
        return meme_texte(l.get(CLE_SORTIE), cle)
    return meme_texte(l.get(colonne_cle), initiales)


def _nom_de_places(valeur):
    """nomDePlaces_ de « 15 » : sans « Dr », minuscules, espaces reduites."""
    return re.sub(r"\s+", " ", normaliser(re.sub(r"^\s*dr\.?\s+", "", _s(valeur), flags=re.I)))


def _lisible(v):
    if _est_date(v):
        d = date_de(v)
        return d.strftime("%d.%m.%Y %H:%M") if v.format != "dd.mm.yyyy" else d.strftime("%d.%m.%Y")
    return v


def _rangee_lisible(entetes, rangee):
    """Une ligne a ecrire, rendue { intitule: valeur } sans les cellules vides ;
    un intitule repete ou absent est distingue par son numero de colonne."""
    sortie = {}
    for j, v in enumerate(rangee):
        if cellule_vide_mut(v) and v != "-":
            continue
        e = entetes[j] if j < len(entetes) and entetes[j] else ""
        cle = e if e and e not in sortie else (e + " " if e else "") + "(colonne " + str(j + 1) + ")"
        sortie[cle] = _lisible(v)
    return sortie


# ------------------------------------------------ le contexte d'un passage

class _Passage:
    """Ce qu'un passage lit une fois et ce qu'il ecrirait ; avec confirmer,
    les ecritures partent aussi vers Google."""

    def __init__(self, moteur, confirmer):
        self.confirmer = bool(confirmer)
        self.onglets = {}
        self.rendu = {"moteur": moteur, "confirme": self.confirmer, "ecritures": {}, "drive": [], "file": [],
                      "journal": []}

    def noter(self, onglet, operation):
        self.rendu["ecritures"].setdefault(onglet, []).append(operation)

    def dire(self, t):
        self.rendu["journal"].append(t)

    def saisie(self):
        if "saisie" not in self.onglets:
            self.onglets["saisie"] = lire_onglet(CFG["ONGLET_SAISIE"], rafraichir=True)
        return self.onglets["saisie"]

    def suivi(self):
        if "suivi" not in self.onglets:
            self.onglets["suivi"] = lire_onglet(CFG["ONGLET_SORTIE_SUIVI"], rafraichir=True)
        return self.onglets["suivi"]

    def engagements(self):
        if "engagements" not in self.onglets:
            self.onglets["engagements"] = lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_ENGAGEMENTS"], rafraichir=True)
        return self.onglets["engagements"]

    def actions(self):
        if "actions" not in self.onglets:
            self.onglets["actions"] = lire_onglet(CFG["ONGLET_SORTIE_ACTIONS"], rafraichir=True)
        return self.onglets["actions"]


def _poser_objet(ctx, onglet, ligne, numero, objet):
    """ecrire_ cellule par cellule dans l'original ; ici un seul batch par
    ligne, et la copie en memoire tenue a jour."""
    for colonne, valeur in objet.items():
        op = {"ligne": numero, "colonne": colonne, "valeur": valeur}
        if _est_date(valeur):
            op["affichee"] = _lisible(valeur)
        ctx.noter(onglet.titre, op)
        if ligne is not None:
            ligne[colonne] = valeur
    if ctx.confirmer:
        ecrire_objet(onglet, numero, objet)


# ------------------------------------------------ le suivi des taches

def marquer_taches(ctx, cle, initiales, ordres, etat, remarque):
    """marquerTaches67_ : pose un etat et une remarque sur des taches du
    suivi sans jamais revenir en arriere. Rend le nombre de taches touchees."""
    suivi = ctx.suivi()
    touchees = 0
    for l in suivi.lignes:
        if _nombre_js(l.get(COL_SUIVI["ORDRE"])) not in ordres:
            continue
        if not _ligne_de_cette_sortie(l, COL_SUIVI["INITIALES"], cle, initiales):
            continue
        actuel = _s(l.get(COL_SUIVI["ETAT"])).strip()
        rang_actuel = RANG_ETAT.get(actuel, 0)
        if rang_actuel >= 2:
            continue
        nouvelle = _ajouter_remarque(l.get(COL_SUIVI["REMARQUE"]), remarque)
        objet = {}
        if etat and RANG_ETAT.get(etat) is not None and RANG_ETAT[etat] > rang_actuel:
            objet[COL_SUIVI["ETAT"]] = etat
            if etat in ("Fait", "Sans objet"):
                objet[COL_SUIVI["FAIT_LE"]] = serial_de(maintenant())
                objet[COL_SUIVI["FAIT_PAR"]] = SORTIE67["FAIT_PAR"]
        if nouvelle != _s(l.get(COL_SUIVI["REMARQUE"])).strip():
            objet[COL_SUIVI["REMARQUE"]] = nouvelle
        if objet:
            _poser_objet(ctx, suivi, l, l["_ligne"], objet)
            touchees += 1
    return touchees


def etat_de_tache(ctx, cle, initiales, ordre):
    """etatDeTache67_ : etat et remarque d'une tache, None si elle n'est pas instanciee."""
    for l in ctx.suivi().lignes:
        if _nombre_js(l.get(COL_SUIVI["ORDRE"])) == ordre and _ligne_de_cette_sortie(l, COL_SUIVI["INITIALES"], cle, initiales):
            return {"etat": _s(l.get(COL_SUIVI["ETAT"])).strip(), "remarque": _s(l.get(COL_SUIVI["REMARQUE"]))}
    return None


# ------------------------------------------------ Places disponibles (15) et son archive

def _onglet_de(ident, nom, ligne_entete=1):
    classeur = _classeur(ident)
    prop = _onglet_exige(classeur, nom)
    _oublier(ident, prop["title"])
    grille = _lire_grille(ident, prop["title"])
    return Onglet(ident, prop, [], [], ligne_entete, {}, grille)


def lire_onglet_places():
    """lireOngletPlaces_ : ligne technique 2, donnees des la ligne 4, jusqu'a « Total »."""
    o = _onglet_de(CFG["CLASSEUR_PLACES"], CFG["ONGLET_PLACES"], CFG["LIGNE_TECHNIQUE_PLACES"])
    grille = o.grille
    largeur = max([len(l) for l in grille] + [0])
    technique = CFG["LIGNE_TECHNIQUE_PLACES"]
    entetes = [texte(e).strip() for e in (grille[technique - 1] if len(grille) >= technique else [])]
    col_therapeute = next((i + 1 for i, e in enumerate(entetes) if meme_texte(e, "Thérapeute")), 0)
    if not col_therapeute:
        raise ValueError("La ligne technique de Places disponibles ne porte pas « Thérapeute ».")
    premiere = technique + 2
    lignes, ligne_totaux = [], 0
    for i in range(premiere - 1, len(grille)):
        numero = i + 1
        nom = _s(grille[i][col_therapeute - 1] if col_therapeute - 1 < len(grille[i]) else "").strip()
        if meme_texte(nom, "Total"):
            ligne_totaux = numero
            break
        if not nom:
            continue
        lignes.append({"numero": numero, "nom": nom, "cle": _nom_de_places(nom), "valeurs": grille[i]})
    if not ligne_totaux:
        raise ValueError("Ligne de totaux introuvable dans Places disponibles.")
    o.entetes = entetes
    return {"onglet": o, "entetes": entetes, "lignes": lignes, "ligneTotaux": ligne_totaux, "lastCol": largeur,
            "colTherapeute": col_therapeute}


def archiver_la_place(ctx, objet, date_sortie, essai):
    """archiverLaPlace67_ : passe la ligne du therapeute dans « Places disponibles - Archive »."""
    noms = _jetons(_s(objet.get(COL["NOM"])) + " " + _s(objet.get("Nom d'usage")))
    prenoms = _jetons(_s(objet.get(COL["PRENOM"])) + " " + _s(objet.get("Prénom d'usage")))
    tous = noms + prenoms
    p = lire_onglet_places()
    trouvees = []
    for l in p["lignes"]:
        t = _jetons(l["nom"])
        if len(t) < 2:
            continue
        if all(x in tous for x in t) and any(x in noms for x in t) and any(x in prenoms for x in t):
            trouvees.append(l)
    if not trouvees:
        return {"etat": "absente"}
    if len(trouvees) > 1:
        return {"etat": "ambiguë", "detail": ", ".join(t["nom"] for t in trouvees)}
    cible = trouvees[0]
    if essai:
        return {"etat": "serait archivée", "ligne": cible["numero"]}

    arch = _onglet_de(CFG["CLASSEUR_PLACES"], CFG["ONGLET_PLACES_ARCHIVE"])
    nb_a = max([len(l) for l in arch.grille] + [0])
    tete = arch.grille[:min(5, len(arch.grille))]
    rang = -1
    for i, r in enumerate(tete):
        if any(meme_texte(v, "Thérapeute") for v in r):
            rang = i
    if rang == -1:
        raise ValueError("Ligne d'en-têtes introuvable dans " + CFG["ONGLET_PLACES_ARCHIVE"])
    h_a = [texte(e).strip() for e in tete[rang]]
    col_t = p["colTherapeute"]
    if col_t - 1 >= len(h_a) or not meme_texte(h_a[col_t - 1], "Thérapeute"):
        raise ValueError("Les colonnes de l'archive ne correspondent plus à celles de Places disponibles")

    source = list(cible["valeurs"]) + [""] * (p["lastCol"] - len(cible["valeurs"]))
    rangee = [source[j] if j < p["lastCol"] else "" for j in range(nb_a)]
    for intitule, valeur in (("Fin de l'engagement", en_jour(date_sortie)), ("Archivé le", aujourdhui()),
                             (COL_MOTIF_ARCHIVAGE, "Sortie close")):
        if intitule in h_a:
            rangee[h_a.index(intitule)] = valeur

    libre = len(arch.grille) + 1
    ctx.noter(arch.titre, {"ligne": libre, "valeurs": _rangee_lisible(h_a, rangee)})
    ctx.noter(p["onglet"].titre, {"supprimer_ligne": cible["numero"], "therapeute": cible["nom"]})
    if ctx.confirmer:
        ecrire_lignes(arch, libre, 1, [rangee])
        relu_grille = _lire_grille(arch.id, arch.titre)
        relu = relu_grille[libre - 1][col_t - 1] if libre - 1 < len(relu_grille) and col_t - 1 < len(relu_grille[libre - 1]) else ""
        if _nom_de_places(relu) != cible["cle"]:
            raise ValueError("Relecture de l'archive de Places disponibles non conforme, ligne vivante laissée en place")
        supprimer_lignes(p["onglet"], [cible["numero"]])
    return {"etat": "archivée", "ligneArchive": libre}


# ------------------------------------------------ les dossiers, aux anciens

def _dossier_drive(ident):
    """DriveApp.getFolderById : le dossier avec ses parents, une erreur sinon."""
    d = fichier(ident, "id,name,mimeType,parents,trashed")
    if d.get("mimeType") != TYPE_DOSSIER:
        raise ValueError("Pas un dossier : " + str(ident))
    return d


def _retirer_acces(id_dossier, adresse):
    """removeEditor puis removeViewer : toute permission de cette adresse sur le dossier."""
    rep = _executer(drive().permissions().list(fileId=id_dossier, supportsAllDrives=True,
                                               fields="permissions(id,emailAddress,role)"))
    for p in rep.get("permissions", []):
        if str(p.get("emailAddress") or "").lower() == adresse.lower():
            try:
                _executer(drive().permissions().delete(fileId=id_dossier, permissionId=p["id"], supportsAllDrives=True))
            except Exception:  # noqa: BLE001
                pass


def ranger_les_dossiers(ctx, id_rh, id_perso, email, essai):
    """rangerLesDossiers67_ : range 1a et 1b aux anciens, retire l'acces du sortant au 1b."""
    faits = []

    def ranger(ident, cible, quoi, dossier=None):
        try:
            d = dossier or _dossier_drive(ident)
        except Exception:  # noqa: BLE001
            faits.append(quoi + " introuvable")
            return False
        if cible in d.get("parents", []):
            faits.append(quoi + " déjà aux anciens")
            return True
        if essai:
            faits.append(quoi + " serait rangé aux anciens")
            return True
        ctx.rendu["drive"].append({"action": "déplacer", "quoi": quoi, "dossier": ident, "nom": d.get("name", ""),
                                   "vers": cible})
        if ctx.confirmer:
            deplacer_fichier(ident, cible)
        faits.append(quoi + " rangé aux anciens")
        return True

    if id_rh:
        ranger(id_rh, SORTIE67["ANCIENS_RH"], "dossier RH")
    if id_perso and id_perso != id_rh:
        cible = SORTIE67["ANCIENS_RH"]
        perso = None
        try:
            perso = _dossier_drive(id_perso)
            if CFG["DOSSIER_INTERNES"] in perso.get("parents", []):
                cible = SORTIE67["ANCIENS_PERSONNEL"]
        except Exception:  # noqa: BLE001
            perso = None
        if ranger(id_perso, cible, "dossier personnel", perso) and email and not essai:
            ctx.rendu["drive"].append({"action": "retirer l'accès", "dossier": id_perso, "adresse": email})
            if ctx.confirmer:
                try:
                    _retirer_acces(id_perso, email)
                except Exception:  # noqa: BLE001
                    pass
    return faits


# ------------------------------------------------ la finalisation d'une sortie

def autre_engagement_en_cours(ctx, initiales, cle):
    """autreEngagementEnCours67_ : un autre engagement ouvert au registre, ou une autre ligne de saisie."""
    init = _s(initiales).strip()
    if not init:
        return False
    for e in ctx.engagements().lignes:
        if meme_texte(e.get("Initiales"), init) and not meme_texte(e.get("Clé engagement"), cle) \
                and _s(e.get("Clé engagement")).strip() != "" and not meme_texte(e.get("État de l'engagement"), "Clos"):
            return True
    for l in ctx.saisie().lignes:
        if meme_texte(l.get(COL["INITIALES"]), init) and _cle_de_la_saisie(l) and not meme_texte(_cle_de_la_saisie(l), cle):
            return True
    return False


def finaliser_la_sortie(ctx, objet, essai):
    """finaliserLaSortie67_ : Places disponibles et dossiers d'une sortie ouverte
    par les RH, une fois la date passee. Rend { texte, fait }."""
    statut = _s(objet.get(COL["STATUT_SORTIE"])).strip()
    if not statut:
        return {"texte": ""}
    cle = _s(objet.get("Clé engagement")).strip() or _cle_de_la_saisie(objet)
    initiales = _s(objet.get(COL["INITIALES"])).strip()
    date_sortie = objet.get(COL["DATE_SORTIE"])
    essai_ligne = meme_texte(objet.get(COL["NOM"]), "Essai")
    simulation = essai or essai_ligne
    if not _est_date(date_sortie):
        return {"texte": "date de sortie absente"}
    if not (_jour(date_sortie) < maintenant().strftime("%Y%m%d")):
        if not simulation:
            marquer_taches(ctx, cle, initiales, [465, 590], "", "Finalisation au passage de nuit qui suit le " + en_jour(date_sortie))
        return {"texte": "reportée après le " + en_jour(date_sortie)}
    if not essai_ligne and autre_engagement_en_cours(ctx, initiales, cle):
        if not simulation:
            marquer_taches(ctx, cle, initiales, [465, 590], "Sans objet",
                           "Autre engagement en cours : Places disponibles et dossiers restent en place")
        return {"texte": "autre engagement en cours, rien à ranger", "fait": not simulation}

    dits = []
    if essai_ligne:
        dits.append("Places disponibles non touchée (ligne d'essai)")
    else:
        try:
            place = archiver_la_place(ctx, objet, date_sortie, simulation)
            dits.append("Places disponibles : " + place["etat"])
            if not simulation:
                if place["etat"] == "archivée":
                    marquer_taches(ctx, cle, initiales, [465], "Fait", "Ligne de Places disponibles archivée le " + aujourdhui())
                elif place["etat"] == "absente":
                    marquer_taches(ctx, cle, initiales, [465], "Sans objet", "Aucune ligne à son nom dans Places disponibles")
                else:
                    marquer_taches(ctx, cle, initiales, [465], "", "Places disponibles : plusieurs lignes possibles ("
                                   + (place.get("detail") or "") + "), archivage à faire à la main")
        except Exception as exc:  # noqa: BLE001
            dits.append("Places disponibles en échec (" + str(exc) + ")")
            marquer_taches(ctx, cle, initiales, [465], "", "Archivage de Places disponibles en échec : " + str(exc))
    try:
        id_rh = _id_depuis_url(_s(objet.get(COL["DOSSIER_RH"])))
        id_perso = _id_depuis_url(_s(objet.get(COL["DOSSIER"])))
        email = _s(objet.get("E-mail Almaval")).strip()
        rangs = ranger_les_dossiers(ctx, id_rh, id_perso, email, simulation)
        dits.append(", ".join(rangs) or "aucun dossier sur la fiche")
        if not simulation:
            if rangs and all(re.search(r"anciens$", t) for t in rangs):
                marquer_taches(ctx, cle, initiales, [590], "Fait", "Dossiers rangés aux anciens le " + aujourdhui() + " : " + ", ".join(rangs))
            else:
                marquer_taches(ctx, cle, initiales, [590], "", "Rangement des dossiers : " + (", ".join(rangs) or "aucun dossier sur la fiche"))
    except Exception as exc:  # noqa: BLE001
        dits.append("dossiers en échec (" + str(exc) + ")")
    return {"texte": " ; ".join(dits), "fait": not simulation}


# ------------------------------------------------ l'archivage d'une ligne de saisie, par intitule

def _onglet_archive_saisie(ctx, saisie):
    """ongletArchiveSaisie_ de « 17 » : l'onglet d'archive, cree a la premiere
    utilisation aux memes colonnes, gele en ligne 1 et masque."""
    if "archive" in ctx.onglets:
        return ctx.onglets["archive"]
    classeur = _classeur(ID_GESTION)
    prop = _onglet(classeur, CFG["ONGLET_SAISIE_ARCHIVE"])
    if prop is None:
        entetes = [e for e in saisie.entetes] + [COL_ARCHIVE_LE, COL_MOTIF_ARCHIVAGE]
        ctx.dire("Onglet « " + CFG["ONGLET_SAISIE_ARCHIVE"] + " » absent : " + ("créé" if ctx.confirmer else "serait créé")
                 + " avec " + str(len(entetes)) + " en-têtes, ligne 1 gelée, masqué")
        if ctx.confirmer:
            rep = _batch_avec_reponse(ID_GESTION, [{"addSheet": {"properties": {
                "title": CFG["ONGLET_SAISIE_ARCHIVE"], "hidden": True,
                "gridProperties": {"rowCount": 100, "columnCount": max(len(entetes), 1), "frozenRowCount": 1}}}}])
            prop = rep["replies"][0]["addSheet"]["properties"]
            classeur["onglets"].append(prop)
            _batch(ID_GESTION, _requete_cellules(prop["sheetId"], 0, 0, [entetes]))
            _oublier(ID_GESTION, prop["title"])
            ctx.onglets["archive"] = lire_onglet(CFG["ONGLET_SAISIE_ARCHIVE"], rafraichir=True)
        else:
            prop = {"title": CFG["ONGLET_SAISIE_ARCHIVE"], "sheetId": None,
                    "gridProperties": {"rowCount": 100, "columnCount": len(entetes), "frozenRowCount": 1}}
            ctx.onglets["archive"] = Onglet(ID_GESTION, prop, entetes, [], 1, {}, [list(entetes)])
    else:
        ctx.onglets["archive"] = lire_onglet(CFG["ONGLET_SAISIE_ARCHIVE"], rafraichir=True)
    return ctx.onglets["archive"]


def _vider_la_ligne(ctx, saisie, numero, largeur):
    """clearContent sur la ligne de saisie, et la copie en memoire videe."""
    ctx.noter(saisie.titre, {"ligne": numero, "vider": largeur})
    if ctx.confirmer:
        _batch(saisie.id, [_requete_effacer(saisie.sheet_id, numero - 1, numero, 0, largeur)])
        _oublier(saisie.id, saisie.titre)
    if numero - 1 < len(saisie.grille):
        saisie.grille[numero - 1] = [""] * len(saisie.grille[numero - 1])
    for l in saisie.lignes:
        if l["_ligne"] == numero:
            for k in list(l):
                if k != "_ligne":
                    l[k] = ""


def archiver_la_ligne_de_saisie(ctx, saisie, numero, motif):
    """archiverLaLigneDeSaisie_ de « 67 » : copie PAR INTITULE dans l'archive,
    intitules manquants ajoutes a droite, ligne videe, puis finalisation."""
    archive = _onglet_archive_saisie(ctx, saisie)
    entetes_a = [texte(e).strip() for e in (archive.grille[0] if archive.grille else [])]
    voulus = [e for e in saisie.entetes if e] + [COL_ARCHIVE_LE, COL_MOTIF_ARCHIVAGE]
    manquants = []
    for e in voulus:
        if e not in entetes_a and e not in manquants:
            manquants.append(e)
    if manquants:
        premiere = len(entetes_a) + 1
        ctx.noter(archive.titre, {"ligne": 1, "colonne_debut": premiere, "en_tetes_ajoutes": manquants})
        if ctx.confirmer:
            ecrire_lignes(archive, 1, premiere, [manquants])
        if archive.grille:
            archive.grille[0] = list(archive.grille[0]) + manquants
        else:
            archive.grille.append(list(manquants))
        entetes_a = entetes_a + manquants
        archive.entetes = entetes_a
        archive.index = {}
        for i, e in enumerate(entetes_a):
            if e and e not in archive.index:
                archive.index[e] = i

    largeur = len(saisie.entetes)
    brut = saisie.grille[numero - 1] if numero - 1 < len(saisie.grille) else []
    valeurs = list(brut)[:largeur] + [""] * max(0, largeur - len(brut))
    objet = {}
    for j, e in enumerate(saisie.entetes):
        if e and e not in objet:
            objet[e] = valeurs[j]
    rangee = [objet.get(e, "") for e in entetes_a]
    rangee[entetes_a.index(COL_ARCHIVE_LE)] = serial_de(maintenant())
    rangee[entetes_a.index(COL_MOTIF_ARCHIVAGE)] = _s(motif)

    libre = max(2, len(archive.grille) + 1)
    ctx.noter(archive.titre, {"ligne": libre, "valeurs": _rangee_lisible(entetes_a, rangee)})
    if ctx.confirmer:
        ecrire_lignes(archive, libre, 1, [rangee])
    archive.grille.append(rangee)
    _vider_la_ligne(ctx, saisie, numero, largeur)

    try:
        suite = finaliser_la_sortie(ctx, objet, False)
        if suite and suite.get("texte"):
            ctx.dire("Finalisation de la sortie : " + suite["texte"])
    except Exception as exc:  # noqa: BLE001
        ctx.dire("Finalisation de la sortie non faite : " + str(exc))
    return libre


# ------------------------------------------------ 1. archiverLesSorties (4 h)

def passage_archivage(confirmer=False):
    """archiverLesSorties de « 67 » : archive les lignes de saisie dont
    l'engagement est clos au registre, hors sorties ouvertes par les RH."""
    ctx = _Passage("archivage", confirmer)
    rendu = ctx.rendu
    saisie = ctx.saisie()
    engagements = ctx.engagements()
    etat_par_cle = {}
    for e in engagements.lignes:
        cle = _s(e.get("Clé engagement")).strip()
        if cle:
            etat_par_cle[cle] = _s(e.get("État de l'engagement"))

    gardees, a_archiver, gardees_detail = 0, [], []
    for l in saisie.lignes:
        cle = _cle_de_la_saisie(l)
        if not cle:
            continue
        if cellule_vide_mut(l.get(COL["INITIALES"])) and cellule_vide_mut(l.get(COL["NOM"])):
            continue
        if etat_par_cle.get(cle) != "Clos":
            continue
        statut = _s(l.get(COL["STATUT_SORTIE"])).strip()
        if any(meme_texte(s, statut) for s in SORTIE67["ETATS_OUVERTS"]):
            gardees += 1
            gardees_detail.append({"ligne": l["_ligne"], "cle": cle, "statut_sortie": statut})
            continue
        a_archiver.append(l)

    rendu["a_archiver"] = [{"ligne": l["_ligne"], "cle": _cle_de_la_saisie(l), "nom": _s(l.get(COL["NOM"])),
                            "prenom": _s(l.get(COL["PRENOM"])), "statut_sortie": _s(l.get(COL["STATUT_SORTIE"]))}
                           for l in a_archiver]
    rendu["gardees"] = gardees_detail
    rendu["resultat_essai"] = (str(len(a_archiver)) + " ligne(s) seraient archivée(s), " + str(gardees)
                               + " gardée(s) parce que leur sortie est ouverte.")

    a_archiver.sort(key=lambda l: -l["_ligne"])
    with _verrou:
        for l in a_archiver:
            archiver_la_ligne_de_saisie(ctx, saisie, l["_ligne"], "Engagement clos au registre")

    bilan = (str(len(a_archiver)) + " ligne(s) de saisie archivée(s) dans « " + CFG["ONGLET_SAISIE_ARCHIVE"] + " »"
             + (", " + str(gardees) + " gardée(s) jusqu'à la clôture de leur sortie." if gardees else "."))
    rendu["resultat" if confirmer else "resultat_prevu"] = bilan
    return rendu


# ------------------------------------------------ 3. l'ouverture automatique des sorties (10 Sortie, ouvrirSortie)

def _annees_de_service(debut, reference):
    """anneesDeService_ : annees revolues entre deux datetime."""
    if debut is None or reference is None:
        return 0
    annees = reference.year - debut.year
    try:
        anniversaire = debut.replace(year=debut.year + annees)
    except ValueError:  # 29 fevrier
        anniversaire = debut.replace(year=debut.year + annees, day=28)
    if anniversaire > reference:
        annees -= 1
    return max(0, annees)


def _delai_de_conge_legal(date_debut, date_reference, fin_periode_essai):
    """delaiDeCongeLegal_ : minimum des articles 335b et 335c CO, { jours, mois, texte }."""
    if date_debut is None:
        return {"jours": 0, "mois": 0, "texte": "date de début manquante"}
    reference = date_reference if date_reference is not None else maintenant()
    if fin_periode_essai is not None and reference <= fin_periode_essai:
        return {"jours": 7, "mois": 0, "texte": "sept jours, période d'essai"}
    annees = _annees_de_service(date_debut, reference)
    if annees < 1:
        return {"jours": 0, "mois": 1, "texte": "un mois, première année de service"}
    if annees < 9:
        return {"jours": 0, "mois": 2, "texte": "deux mois, " + str(annees + 1) + "e année de service"}
    return {"jours": 0, "mois": 3, "texte": "trois mois, " + str(annees + 1) + "e année de service"}


def _fin_de_contrat_au_plus_tot(date_resiliation, delai):
    """finDeContratAuPlusTot_ : le delai en mois court pour la fin d'un mois, le delai en jours non."""
    if date_resiliation is None:
        return None
    if delai["jours"]:
        return date_resiliation + datetime.timedelta(days=delai["jours"])
    mois_index = date_resiliation.month - 1 + delai["mois"] + 1   # mois suivant celui de la fin
    an = date_resiliation.year + mois_index // 12
    mois = mois_index % 12 + 1
    return datetime.datetime(an, mois, 1) - datetime.timedelta(days=1)


def _mois_du_delai_contractuel(valeur):
    """moisDuDelaiContractuel_ : un nombre de mois lu dans un libelle."""
    if valeur is None or valeur == "":
        return None
    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
        return float(valeur)
    m = re.search(r"(\d+([.,]\d+)?)", str(valeur))
    return float(m.group(1).replace(",", ".")) if m else None


def _concerne(filtre, valeurs):
    """concerne_ de « 04 » : vrai si le filtre est vide, ou si l'une des valeurs y figure."""
    attendus = liste_de_texte(filtre)
    if not attendus:
        return True
    return any(any(meme_texte(a, v) for v in valeurs) for a in attendus)


def taches_de_sortie(ctx, statut_collaboration, profession):
    """tachesDeSortie_ : les taches actives du referentiel qui concernent ce statut et cette profession, par ordre."""
    taches = [t for t in ctx.actions().lignes
              if est_actif(t.get(COL_SORTIE["ACTIF"])) and _s(t.get(COL_SORTIE["ACTION"])).strip()
              and _concerne(t.get(COL_SORTIE["STATUTS"]), [statut_collaboration])
              and _concerne(t.get(COL_SORTIE["PROFESSIONS"]), [profession])]
    def ordre(t):
        n = _nombre_js(t.get(COL_SORTIE["ORDRE"]))
        return n if n == n else 0.0
    taches.sort(key=ordre)
    return taches


def _ordres_deja_suivis(suivi, initiales, cle):
    """ordresDejaSuivis_ : les ordres deja instancies pour cet engagement, ou pour cette personne a defaut."""
    deja = set()
    for l in suivi.lignes:
        if _ligne_de_cette_sortie(l, COL_SUIVI["INITIALES"], cle, initiales):
            deja.add(_s(l.get(COL_SUIVI["ORDRE"])).strip())
    return deja


def _remplir_si_vide(saisie, ligne, objet, nom_colonne, valeur):
    """remplirSiVide_ de « 05 » : la colonne existe, la source porte quelque
    chose, la destination est vide ; sinon rien. L'ecriture est cumulee dans objet."""
    if not saisie.existe(nom_colonne):
        return False
    if valeur is None or valeur == "":
        return False
    if not (ligne.get(nom_colonne) is None or ligne.get(nom_colonne) == ""):
        return False
    objet[nom_colonne] = valeur
    return True


def ouvrir_la_sortie(ctx, ligne):
    """ouvrirSortie de « 10 » pour une ligne de saisie deja lue : delai legal,
    taches instanciees sans doublon, statut En cours, date d'ouverture,
    coordonnees pre-remplies, compte rendu dans « Message du service ».
    Rend le detail de ce qui a ete fait ou serait fait.
    
    [2026-10-03] Cette fonction n'est plus appelée. La nuit ouvre les sorties
    en appelant l'Action RH « Ouvrir la sortie » par la porte d'Onboarding."""
    saisie = ctx.saisie()
    numero = ligne["_ligne"]
    detail = {"ligne": numero, "initiales": _s(ligne.get(COL["INITIALES"])).strip(),
              "nom": _s(ligne.get(COL["NOM"])), "prenom": _s(ligne.get(COL["PRENOM"]))}
    date_sortie = ligne.get(COL["DATE_SORTIE"])
    if not _est_date(date_sortie):
        detail["refus"] = "date de sortie absente ou illisible"
        return detail
    initiales = detail["initiales"]
    if not initiales:
        detail["refus"] = "initiales manquantes"
        return detail
    nom_prenom = (_s(ligne.get(COL["NOM"])) + " " + _s(ligne.get(COL["PRENOM"]))).strip()
    detail["date_sortie"] = en_jour(date_sortie)

    objet = {}
    remarque_delai = ""
    if meme_texte(ligne.get(COL["STATUT_COLLAB"]), "Salarié") and _est_date(ligne.get(COL["DATE_DEBUT"])):
        reference = date_de(ligne.get(COL["RESILIATION_RECUE"])) if _est_date(ligne.get(COL["RESILIATION_RECUE"])) else maintenant()
        fin_essai = date_de(ligne.get(COL["FIN_ESSAI"])) if _est_date(ligne.get(COL["FIN_ESSAI"])) else None
        delai = _delai_de_conge_legal(date_de(ligne.get(COL["DATE_DEBUT"])), reference, fin_essai)
        objet[COL["DELAI_LEGAL"]] = delai["jours"] / 30.0 if delai["jours"] else delai["mois"]
        contractuel = _mois_du_delai_contractuel(ligne.get(COL["DELAI_CONGE"]))
        if contractuel is not None and delai["mois"] and contractuel < delai["mois"]:
            remarque_delai = (" ATTENTION, le délai contractuel de " + texte(contractuel)
                              + " mois est inférieur au minimum légal de " + delai["texte"] + ", à vérifier.")
        else:
            remarque_delai = " Minimum légal : " + delai["texte"] + "."
        au_plus_tot = _fin_de_contrat_au_plus_tot(reference, delai)
        if au_plus_tot:
            remarque_delai += " Fin possible au plus tôt le " + au_plus_tot.strftime("%d.%m.%Y") + "."
        detail["delai_legal"] = delai

    suivi = ctx.suivi()
    cle = _cle_de_sortie(ligne)
    deja = _ordres_deja_suivis(suivi, initiales, cle)
    taches = taches_de_sortie(ctx, _s(ligne.get(COL["STATUT_COLLAB"])), _s(ligne.get(COL["PROFESSION"])))
    jour_sortie = date_de(date_sortie)
    nouvelles = []
    for t in taches:
        ordre = t.get(COL_SORTIE["ORDRE"])
        if _s(ordre).strip() in deja:
            continue
        jours = _nombre_js(t.get(COL_SORTIE["JOURS"]))
        if jours != jours:
            jours = 0.0
        echeance = jour_sortie + datetime.timedelta(days=int(jours))
        valeurs = {CLE_SORTIE: cle, COL_SUIVI["INITIALES"]: initiales, COL_SUIVI["NOM"]: nom_prenom,
                   COL_SUIVI["ORDRE"]: ordre, COL_SUIVI["ETAPE"]: t.get(COL_SORTIE["ETAPE"]),
                   COL_SUIVI["ACTION"]: t.get(COL_SORTIE["ACTION"]), COL_SUIVI["RESPONSABLE"]: t.get(COL_SORTIE["RESPONSABLE"]),
                   COL_SUIVI["ECHEANCE"]: serial_de(datetime.datetime(echeance.year, echeance.month, echeance.day)),
                   COL_SUIVI["ETAT"]: "À faire"}
        nouvelles.append([valeurs.get(e, "") if e else "" for e in suivi.entetes])
    detail["taches_applicables"] = len(taches)
    detail["taches_ajoutees"] = len(nouvelles)
    detail["cle"] = cle
    if nouvelles:
        premiere = max(len(suivi.lignes) + suivi.ligne_entete + 1, suivi.ligne_entete + 1)
        ctx.noter(suivi.titre, {"ligne": premiere, "lignes_ajoutees": len(nouvelles),
                                "ordres": [_s(n[suivi.colonne(COL_SUIVI["ORDRE"]) - 1]) for n in nouvelles]})
        if ctx.confirmer:
            ecrire_lignes(suivi, premiere, 1, nouvelles)
        for i, n in enumerate(nouvelles):
            obj = {"_ligne": premiere + i}
            for j, e in enumerate(suivi.entetes):
                if e:
                    obj[e] = n[j]
            suivi.lignes.append(obj)
            suivi.grille.append(list(n))

    objet[COL["STATUT_SORTIE"]] = "En cours"
    if not _est_date(ligne.get(COL["SORTIE_OUVERTE"])):
        objet[COL["SORTIE_OUVERTE"]] = serial_de(maintenant())
    remplies = 0
    for source, cible in ((COL["EMAIL_PRIVE"], COL["SORTIE_EMAIL"]), ("Téléphone mobile", COL["SORTIE_TELEPHONE"]),
                          ("Rue et numéro", COL["SORTIE_RUE"]), ("NPA", COL["SORTIE_NPA"]),
                          ("Localité", COL["SORTIE_LOCALITE"]), ("Pays", COL["SORTIE_PAYS"]), ("IBAN", COL["SORTIE_IBAN"])):
        if _remplir_si_vide(saisie, ligne, objet, cible, ligne.get(source)):
            remplies += 1
    detail["coordonnees_preremplies"] = remplies
    message = ("Sortie ouverte automatiquement le " + horodatage() + ", " + str(len(nouvelles)) + " tâche(s) ajoutée(s) sur "
               + str(len(taches)) + " applicable(s)." + remarque_delai
               + " Les lettres de fin et les brouillons se produisent par l'action RH « Ouvrir la sortie », relançable sans doublon.")
    if saisie.existe(COL["MESSAGE"]):
        objet[COL["MESSAGE"]] = message
    detail["message"] = message
    _poser_objet(ctx, saisie, ligne, numero, objet)
    return detail


def ouvrir_les_sorties_en_attente(ctx, bilan):
    """Les lignes de saisie qui portent une date de sortie, des initiales et
    aucun statut de sortie, hors ligne d'essai : ouvertes une par une."""
    rendu = ctx.rendu
    rendu["sorties_ouvertes_automatiquement"] = []
    if not SORTIE67["OUVERTURE_AUTOMATIQUE"]:
        return
    for l in ctx.saisie().lignes:
        if not _est_date(l.get(COL["DATE_SORTIE"])):
            continue
        if _s(l.get(COL["STATUT_SORTIE"])).strip():
            continue
        if cellule_vide_mut(l.get(COL["INITIALES"])) and cellule_vide_mut(l.get(COL["NOM"])):
            continue
        if meme_texte(l.get(COL["NOM"]), "Essai"):
            continue
        try:
            payload = {
                "action": "almadeskEditer",
                "onglet": "Saisie - Collaborateurs",
                "ligne": l["_ligne"],
                "colonne": "Action RH",
                "valeur": "Ouvrir la sortie",
                "empreinte": {
                    "Initiales": _s(l.get(COL["INITIALES"])).strip(),
                    "Clé engagement": _cle_de_sortie(l)
                },
                "auteur": "gestion@almaval.ch"
            }
            if not ctx.confirmer:
                payload["simuler"] = True
            
            rep = run_web_app(URL_APPLICATION, payload, timeout=120)
            
            detail = {"ligne": l["_ligne"], "initiales": _s(l.get(COL["INITIALES"])).strip()}
            if rep.get("ok"):
                detail["message"] = rep.get("message", "Ouverture demandée à l'Action RH")
            else:
                detail["erreur"] = rep.get("message", "Erreur inconnue")
                bilan["erreurs"] += 1
        except Exception as exc:  # noqa: BLE001
            bilan["erreurs"] += 1
            detail = {"ligne": l["_ligne"], "initiales": _s(l.get(COL["INITIALES"])), "erreur": str(exc)[:200]}
        rendu["sorties_ouvertes_automatiquement"].append(detail)
        if "refus" not in detail and "erreur" not in detail:
            bilan["sortiesOuvertesAutomatiquement"] += 1


# ------------------------------------------------ 4. les conditions d'application (Sortie - Actions, colonne N)

def _lire_terme(terme, ligne, engagement):
    """Un terme de condition -> (« oui », « non » ou « inconnu », lecture lisible)."""
    t = terme.strip()
    source, ou = ligne, "fiche"
    if t.lower().startswith("registre:"):
        t = t[len("registre:"):].strip()
        source, ou = (engagement or {}), "registre"
    numerique = t.endswith("#")
    if numerique:
        t = t[:-1].strip()
    attendu = None
    if "=" in t:
        t, attendu = [x.strip() for x in t.split("=", 1)]
    v = source.get(t)
    lu = _s(v).strip()
    lecture = t + (" (" + ou + ") = « " + lu + " »" if lu else " (" + ou + ") vide")
    if attendu is not None:
        return ("oui" if meme_texte(v, attendu) else "non"), lecture
    if lu == "":
        return ("non" if numerique else "inconnu"), lecture
    if normaliser(v) in NEGATIONS:
        return "non", lecture
    if numerique:
        n = _nombre_js(v)
        if n == n and n == 0:
            return "non", lecture
    return "oui", lecture


def evaluer_condition(regle, ligne, engagement):
    """La colonne « Condition d'application » d'une tache -> (verdict, lecture).
    Verdict : « oui », « non », « inconnu », ou « » quand la tache n'a pas de regle."""
    r = _s(regle).strip()
    if not r:
        return "", ""
    if "[soumise]" in r.lower():
        r = re.sub(r"\[soumise\]", "", r, flags=re.I).strip()
        if not _est_date(ligne.get(COL["SORTIE_SOUMISE"])):
            return "inconnu", "page de sortie pas encore soumise"
    verdicts, lectures = [], []
    for terme in [x for x in r.split("|") if x.strip()]:
        v, lecture = _lire_terme(terme, ligne, engagement)
        verdicts.append(v)
        lectures.append(lecture)
    if "oui" in verdicts:
        verdict = "oui"
    elif verdicts and all(v == "non" for v in verdicts):
        verdict = "non"
    else:
        verdict = "inconnu"
    return verdict, " ; ".join(lectures)


def appliquer_les_conditions(ctx, ligne, cle, initiales, engagement):
    """Pour une sortie ouverte : les taches conditionnelles encore A faire dont
    la condition est absente passent Sans objet ; celles que le moteur avait
    mises Sans objet et dont la condition est presente sont rouvertes.
    Rend { sans_objet: [ordres], rouvertes: [ordres] }."""
    regles = {}
    for t in ctx.actions().lignes:
        regle = _s(t.get(COL_CONDITION)).strip()
        if regle:
            regles[_s(t.get(COL_SORTIE["ORDRE"])).strip()] = regle
    bilan = {"sans_objet": [], "rouvertes": []}
    if not regles:
        return bilan
    suivi = ctx.suivi()
    for l in suivi.lignes:
        ordre = _s(l.get(COL_SUIVI["ORDRE"])).strip()
        if ordre not in regles or not _ligne_de_cette_sortie(l, COL_SUIVI["INITIALES"], cle, initiales):
            continue
        verdict, lecture = evaluer_condition(regles[ordre], ligne, engagement)
        etat = _s(l.get(COL_SUIVI["ETAT"])).strip()
        par_le_moteur = meme_texte(l.get(COL_SUIVI["FAIT_PAR"]), SORTIE67["FAIT_PAR"])
        if verdict == "non" and etat in ("", "À faire"):
            _poser_objet(ctx, suivi, l, l["_ligne"], {
                COL_SUIVI["ETAT"]: "Sans objet",
                COL_SUIVI["FAIT_LE"]: serial_de(maintenant()),
                COL_SUIVI["FAIT_PAR"]: SORTIE67["FAIT_PAR"],
                COL_SUIVI["REMARQUE"]: _ajouter_remarque(l.get(COL_SUIVI["REMARQUE"]), "Sans objet : " + lecture)})
            bilan["sans_objet"].append(ordre)
        elif verdict == "oui" and etat == "Sans objet" and par_le_moteur:
            _poser_objet(ctx, suivi, l, l["_ligne"], {
                COL_SUIVI["ETAT"]: "À faire", COL_SUIVI["FAIT_LE"]: "", COL_SUIVI["FAIT_PAR"]: "",
                COL_SUIVI["REMARQUE"]: _ajouter_remarque(l.get(COL_SUIVI["REMARQUE"]), "Rouverte : " + lecture)})
            bilan["rouvertes"].append(ordre)
    return bilan


# ------------------------------------------------ 2. passageQuotidienDesSorties (4 h 15)

def passage_sorties(confirmer=False):
    """passageQuotidienDesSorties de « 67 » : reporte au suivi ce qui se
    constate, puis finalise les sorties closes avant leur date."""
    ctx = _Passage("sorties", confirmer)
    rendu = ctx.rendu
    bilan = {"sortiesOuvertesAutomatiquement": 0, "sortiesOuvertes": 0, "tachesMisesAJour": 0, "archivesExaminees": 0,
             "finalisees": 0, "erreurs": 0}
    if not _verrou.acquire(timeout=30):
        rendu["resultat"] = {"fait": False, "motif": "classeur occupé"}
        return rendu
    try:
        saisie = ctx.saisie()
        erreurs_lecture = 0
        try:
            ouvrir_les_sorties_en_attente(ctx, bilan)
        except Exception as exc:  # noqa: BLE001
            bilan["erreurs"] += 1
            ctx.dire("ouverture automatique des sorties en échec (" + str(exc)[:200] + ")")
        fin_par_cle = {}
        engagement_par_cle = {}
        try:
            for e in ctx.engagements().lignes:
                c = _s(e.get("Clé engagement")).strip()
                if c:
                    engagement_par_cle[c] = e
                if c and _est_date(e.get("Date de fin")):
                    fin_par_cle[c] = e.get("Date de fin")
        except Exception as exc:  # noqa: BLE001
            bilan["erreurs"] += 1
            erreurs_lecture += 1
            ctx.dire("registre des engagements illisible (" + str(exc)[:200] + ")")
        continuite = {}
        try:
            for l in lire_onglet(CFG["ONGLET_SORTIE_PATIENTS"], rafraichir=True).lignes:
                c = _s(l.get(CLE_SORTIE)).strip()
                if c:
                    continuite[c] = True
        except Exception as exc:  # noqa: BLE001
            bilan["erreurs"] += 1
            erreurs_lecture += 1
            ctx.dire("continuité clinique illisible (" + str(exc)[:200] + ")")

        rendu["sorties_ouvertes"] = []
        for l in saisie.lignes:
            statut = _s(l.get(COL["STATUT_SORTIE"])).strip()
            if not any(meme_texte(s, statut) for s in SORTIE67["ETATS_OUVERTS"]):
                continue
            cle = _cle_de_sortie(l)
            init = _s(l.get(COL["INITIALES"]))
            if not cle and not init:
                continue
            bilan["sortiesOuvertes"] += 1
            detail = {"ligne": l["_ligne"], "cle": cle, "initiales": init, "statut_sortie": statut, "constats": []}
            rendu["sorties_ouvertes"].append(detail)
            try:
                n = 0
                soumise = l.get("Sortie soumise le")
                if _est_date(soumise):
                    n += marquer_taches(ctx, cle, init, [32, 35], "Fait", "Page de sortie soumise le " + en_jour(soumise))
                    detail["constats"].append("page de sortie soumise")
                elif _vrai(l.get("Instructions de départ acceptées")):
                    n += marquer_taches(ctx, cle, init, [35], "Fait", "Instructions de départ acceptées sur la page de sortie")
                    detail["constats"].append("instructions acceptées")
                fin = fin_par_cle.get(cle)
                if fin is not None and _est_date(l.get(COL["DATE_SORTIE"])) and _jour(fin) == _jour(l.get(COL["DATE_SORTIE"])):
                    n += marquer_taches(ctx, cle, init, [45, 560], "Fait", "Date de sortie inscrite au registre Effectif")
                    detail["constats"].append("date au registre")
                if continuite.get(cle):
                    n += marquer_taches(ctx, cle, init, [150], "Fait", "Liste des patients présente dans Sortie - Continuité clinique")
                    detail["constats"].append("continuité clinique")
                if _est_date(l.get(COL["CERTIFICAT_REMIS"])):
                    n += marquer_taches(ctx, cle, init, [250], "Fait", "Certificat remis le " + en_jour(l.get(COL["CERTIFICAT_REMIS"])))
                    detail["constats"].append("certificat remis")
                if _est_date(l.get(COL["ENTRETIEN_SORTIE"])):
                    n += marquer_taches(ctx, cle, init, [550], "Fait", "Entretien de sortie fait le " + en_jour(l.get(COL["ENTRETIEN_SORTIE"])))
                    detail["constats"].append("entretien fait")
                conditions = appliquer_les_conditions(ctx, l, cle, init, engagement_par_cle.get(cle))
                if conditions["sans_objet"] or conditions["rouvertes"]:
                    detail["conditions"] = conditions
                    n += len(conditions["sans_objet"]) + len(conditions["rouvertes"])
                detail["taches_touchees"] = n
                bilan["tachesMisesAJour"] += n
            except Exception as exc:  # noqa: BLE001
                bilan["erreurs"] += 1
                detail["erreur"] = str(exc)[:200]

        # Les sorties closes avant leur date
        archive = None
        try:
            archive = lire_onglet(CFG["ONGLET_SAISIE_ARCHIVE"], rafraichir=True)
        except Exception:  # noqa: BLE001
            archive = None
        rendu["archives_examinees"] = []
        if archive:
            for l in archive.lignes:
                le = l.get(COL_ARCHIVE_LE)
                if not _est_date(le) or _jour(le) < SORTIE67["DEBUT_FINALISATION"]:
                    continue
                if not _s(l.get(COL["STATUT_SORTIE"])).strip():
                    continue
                if meme_texte(l.get(COL["NOM"]), "Essai"):
                    continue
                cle = _s(l.get("Clé engagement")).strip()
                init = _s(l.get(COL["INITIALES"])).strip()
                t465 = etat_de_tache(ctx, cle, init, 465)
                t590 = etat_de_tache(ctx, cle, init, 590)
                finies = all(not t or t["etat"] in ("Fait", "Sans objet") for t in (t465, t590))
                if finies and (t465 or t590):
                    continue
                bilan["archivesExaminees"] += 1
                detail = {"ligne": l["_ligne"], "cle": cle, "initiales": init}
                rendu["archives_examinees"].append(detail)
                try:
                    r = finaliser_la_sortie(ctx, l, False)
                    detail["finalisation"] = r.get("texte", "")
                    if r.get("fait"):
                        bilan["finalisees"] += 1
                except Exception as exc:  # noqa: BLE001
                    bilan["erreurs"] += 1
                    detail["erreur"] = str(exc)[:200]
        resultat = {"fait": True, "essai": False, "bilan": bilan}
        rendu["resultat" if confirmer else "resultat_prevu"] = resultat
        rendu["resultat_essai"] = {"fait": True, "essai": True,
                                   "bilan": {"sortiesOuvertesAutomatiquement": bilan["sortiesOuvertesAutomatiquement"],
                                             "sortiesOuvertes": bilan["sortiesOuvertes"], "tachesMisesAJour": 0,
                                             "archivesExaminees": bilan["archivesExaminees"], "finalisees": 0,
                                             "erreurs": erreurs_lecture}}
        return rendu
    finally:
        try:
            _verrou.release()
        except Exception:  # noqa: BLE001
            pass


# ------------------------------------------------ outils et pont

@mcp.tool()
@tolerant
def onboarding_archiver_sorties(confirmer: bool = False):
    """Archivage des lignes de saisie closes au registre (onboarding, 4 h) sous gestion@ ; simulation sans confirmer."""
    return passage_archivage(confirmer=confirmer)


@mcp.tool()
@tolerant
def onboarding_sorties(confirmer: bool = False):
    """Passage de nuit des sorties : ouverture automatique des sorties datées, suivi et finalisation (onboarding, 4 h 15) sous gestion@ ; simulation sans confirmer."""
    return passage_sorties(confirmer=confirmer)


try:
    _pont_precedent = outils_lieux._pont

    def _pont(texte_sujet: str):
        brut = str(texte_sujet or "").strip()
        mots = brut.split()
        premier = mots[0].lower() if mots else ""
        drapeaux = {m.lower() for m in mots[1:] if "=" not in m}
        if premier == "onboarding_archiver_sorties":
            return pont_de_fond("archiver_sorties", drapeaux, tolerant(passage_archivage), dict(confirmer=("confirmer" in drapeaux)))
        if premier == "onboarding_sorties":
            return pont_de_fond("sorties", drapeaux, tolerant(passage_sorties), dict(confirmer=("confirmer" in drapeaux)))
        return _pont_precedent(brut)

    outils_lieux._pont = _pont
except Exception as _exc:  # noqa: BLE001
    print("[onboarding sorties] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)
