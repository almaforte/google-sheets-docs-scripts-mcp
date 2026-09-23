"""Almaval - moteur des lieux : la cascade du contrat vers les attributions.

Mission unique d'Almaval 2.0, rappelee par Alberto le 22.09.2026 : une
information est ecrite UNE SEULE FOIS A UN SEUL ENDROIT, et de la elle
descend en cascade partout ailleurs.

Ce module est la premiere marche de cette cascade pour les lieux. Le
constat qui l'a fait naitre, ce jour-la : les douze colonnes de
demi-journees de Registre - Engagements ont DEUX ecrivains. Le moteur des
lieux les reecrit chaque nuit depuis l'onglet Attributions
(lieux_renvoyer_vers_effectif), et la chaine des mutations les ecrit
aussi, ses douze regles 820 a 930 etant actives depuis le 17.09.2026.
Deux ecrivains sur la meme colonne, c'est le dernier passe qui gagne :
une mutation validee peut etre effacee la nuit suivante sans que
personne ne le voie.

Le sens unique decide par Alberto le 22.09.2026 est celui-ci :

    contrat (onboarding ou mutation)
        -> Attributions, en PRE-ECRITURE a completer et valider
        -> les douze colonnes du registre
        -> Places disponibles

Chaque maillon garde son niveau de detail. Le contrat dit la VILLE et la
demi-journee, parce que c'est ce qu'un contrat sait dire. Les lieux
disent le BATIMENT et le BUREAU, parce que c'est ce qu'un contrat ne
peut pas savoir : le referentiel porte trois batiments a Lausanne, trois
a Geneve, deux a Morges, et le choix du bureau depend de ce qui est
libre. La pre-ecriture est donc PARTIELLE par construction : elle ouvre
le dossier et le pose sur la table, elle ne decide jamais qui va dans
quel bureau.

QUATRE CAS, et non un seul. La valeur d'une demi-journee au registre est
une ville, ou Teletravail, ou Itinerant, ou Non travaille, ou vide :

  1. une ville differente de celle qui est attribuee : fermer la ligne en
     cours A LA VEILLE de la date d'effet, ouvrir une ligne Proposee a la
     date d'effet ;
  2. Teletravail ou Itinerant : fermer, n'ouvrir aucune ligne, la
     personne n'occupe plus de bureau cette demi-journee ;
  3. Non travaille ou vide : fermer ;
  4. la meme ville qu'avant : ne rien faire, surtout ne pas rouvrir une
     ligne identique.

Et un cinquieme, trouve au premier passage a blanc : la ville est deja
prevue par une attribution qui ne commence que plus tard. La cascade le
dit et n'ouvre rien, sinon elle poserait une seconde ligne pour un lieu
deja decide.

LA REGLE DE LA VEILLE EST CODEE ICI UNE FOIS POUR TOUTES. Une fin et un
debut au meme jour font compter deux lieux le meme jour par tout moteur
qui lit une fenetre de dates. L'erreur a ete faite sur Salibian le
15.09.2026 et refaite a la main sur Schembari le 22.09.2026 ; elle ne
doit plus etre refaite par une personne.

CE QUE CE MODULE N'EST PAS ENCORE. Il lit aujourd'hui les douze colonnes
du registre, qui restent alimentees par les lieux : la cascade tourne
donc a vide tant que le contrat n'ecrit pas ces colonnes. C'est voulu.
L'etape 1 sert a voir, sur l'existant, ce que la cascade poserait, et a
mesurer les desaccords entre le registre et les attributions. Le
branchement sur la mutation et sur l'inscription, puis le retrait du
double ecrivain, viennent ensuite, dans cet ordre, une fois cette
lecture verifiee.

Le rapport complet est depose dans l'onglet technique « Cascade -
Propositions » du classeur des lieux, ecrit meme a blanc : c'est le
livrable lisible, et un passage a blanc ne touche rien d'autre.
"""

import datetime

from main import mcp, tolerant

import outils_lieux
from outils_lieux_socle import (
    DEMIS,
    EDITEURS,
    ETATS_ENGAGEMENT_VIVANTS,
    ID_EFFECTIF,
    ID_LIEUX,
    JOURS,
    ONGLET_ATTRIBUTIONS,
    ONGLET_EFFECTIF,
    _ajuster_taille,
    _aujourdhui,
    _cellule,
    _colonne,
    _date,
    _ecrire,
    _feuilles,
    _journaliser,
    _lettre,
    _lire,
    _maintenant,
    _normaliser,
    _onglets,
    _table_referentiel,
)

ONGLET_CASCADE = "Cascade - Propositions"
COLONNES_CASCADE = [
    "Horodatage", "Initiales", "Collaborateur", "Jour", "Demi-journée",
    "Ville au contrat", "Bâtiment attribué", "Action", "Bâtiment proposé",
    "Date d'effet", "Ligne d'attributions", "Remarque",
]

# Valeurs du registre qui disent que la personne travaille sans occuper
# de bureau, ou ne travaille pas : elles ferment, elles n'ouvrent jamais.
SANS_BUREAU = ("TELETRAVAIL", "ITINERANT", "NON TRAVAILLE")

# Marque qui empeche l'aplatissement de la grille Propositions de clore
# une ligne qu'il n'a pas posee. Une ligne de la cascade la porte, comme
# une ligne ecrite a la main, sinon le passage suivant la refermerait en
# silence. L'origine parlante viendra a l'etape 2, quand le moteur des
# mutations posera lui-meme ses lignes.
MARQUE_CASCADE = "Registre seul"

STATUTS_VIVANTS = ("Active", "Confirmée", "Proposée")


def _veille(date_iso: str) -> str:
    """Le jour d'avant, en ISO. Une attribution qui en remplace une autre
    se termine la veille du debut de la nouvelle, jamais le meme jour."""
    jour = datetime.date.fromisoformat(date_iso)
    return (jour - datetime.timedelta(days=1)).isoformat()


def _sites_et_batiments(sujet: str = ""):
    """({batiment normalise: site}, {site normalise: [batiments]}).

    Lu dans le referentiel des bureaux, source unique : un batiment
    appartient a une ville, une ville porte un ou plusieurs batiments.
    """
    _, par_identifiant = _table_referentiel(sujet=sujet)
    site_par_batiment, batiments_par_site = {}, {}
    for fiche in par_identifiant.values():
        batiment = str(fiche.get("nom_batiment") or "").strip()
        site = str(fiche.get("site") or "").strip()
        if not batiment or not site:
            continue
        site_par_batiment[_normaliser(batiment)] = site
        liste = batiments_par_site.setdefault(_normaliser(site), [])
        if batiment not in liste:
            liste.append(batiment)
    return site_par_batiment, batiments_par_site


def _attributions_par_creneau(date_iso: str, site_par_batiment, ref, sujet: str = ""):
    """{(initiales, jour, demi normalises): [lignes vivantes a la date]}.

    Une ligne vivante est Active, Confirmee, ou Proposee avec une date de
    debut atteinte, commencee au plus tard a la date et non close avant
    elle. Les occupants generiques (Menage, Direction, Colloque...) ne
    sont pas des personnes et sont ecartes.
    """
    from outils_lieux_noms import _resoudre
    lignes = _lire(ONGLET_ATTRIBUTIONS, sujet=sujet)
    entetes = lignes[0]
    i = {nom: _colonne(entetes, nom) for nom in (
        "Clé", "Collaborateur", "Bâtiment", "Bureau", "Jour", "Demi-journée",
        "Date de début", "Date de fin", "Statut", "Remarque")}
    etat, a_venir = {}, {}
    for r, ligne in enumerate(lignes[1:], start=2):
        if _cellule(ligne, i["Statut"]) not in STATUTS_VIVANTS:
            continue
        debut = _date(_cellule(ligne, i["Date de début"]))
        fin = _date(_cellule(ligne, i["Date de fin"]))
        if fin and fin < date_iso:
            continue
        dernier = str(_cellule(ligne, i["Clé"]) or "").split("|")[-1].strip()
        initiales = dernier if dernier in ref["personnes"] else _resoudre(
            _cellule(ligne, i["Collaborateur"]), ref)[0]
        if not initiales:
            continue
        batiment = str(_cellule(ligne, i["Bâtiment"]) or "").strip()
        cle = (initiales, _normaliser(_cellule(ligne, i["Jour"])),
               _normaliser(_cellule(ligne, i["Demi-journée"])))
        fiche = {
            "ligne": r,
            "batiment": batiment,
            "site": site_par_batiment.get(_normaliser(batiment), ""),
            "bureau": str(_cellule(ligne, i["Bureau"]) or "").strip(),
            "statut": _cellule(ligne, i["Statut"]),
            "debut": debut,
            "colonne_fin": i["Date de fin"],
        }
        # Une attribution qui ne commence que plus tard n'est pas en place
        # aujourd'hui, et elle ne doit pourtant pas etre ignoree : sans
        # elle, la cascade ouvrirait une seconde ligne pour un lieu deja
        # prevu. Constate le 22.09.2026 sur Baranova Youliana, attendue a
        # Lausanne des le 01.03.2027 et deja declaree au registre.
        (a_venir if (debut and debut > date_iso) else etat).setdefault(cle, []).append(fiche)
    return etat, a_venir, i


def _cibles_du_registre(sujet: str = ""):
    """[(initiales, nom, {(jour, demi): valeur du registre})] des vivants."""
    effectif = _lire(ONGLET_EFFECTIF, ID_EFFECTIF, sujet=sujet)
    tetes = effectif[0]
    i_nom = _colonne(tetes, "Nom prénom")
    i_ini = _colonne(tetes, "Initiales")
    try:
        i_etat = _colonne(tetes, "État de l'engagement")
    except RuntimeError:
        i_etat = None
    creneaux = []
    for jour in JOURS:
        for demi in DEMIS:
            intitule = jour + " " + demi.lower()
            try:
                creneaux.append((jour, demi, _colonne(tetes, intitule)))
            except RuntimeError:
                continue
    cibles = []
    for ligne in effectif[1:]:
        initiales = str(_cellule(ligne, i_ini) or "").strip()
        nom = str(_cellule(ligne, i_nom) or "").strip()
        if not initiales or not nom:
            continue
        if i_etat is not None and _cellule(ligne, i_etat) not in ETATS_ENGAGEMENT_VIVANTS:
            continue
        valeurs = {}
        for jour, demi, colonne in creneaux:
            valeurs[(jour, demi)] = str(_cellule(ligne, colonne) or "").strip()
        cibles.append((initiales, nom, valeurs))
    return cibles, len(creneaux)


def _actions(date_iso, cibles, etat, a_venir, batiments_par_site):
    """Les quatre cas, un enregistrement par geste a poser."""
    veille = _veille(date_iso)
    actions, inconnus = [], []
    for initiales, nom, valeurs in cibles:
        for (jour, demi), valeur in valeurs.items():
            cle = (initiales, _normaliser(jour), _normaliser(demi))
            en_place = etat.get(cle, [])
            cible = _normaliser(valeur)
            sites_en_place = [l["site"] for l in en_place if l["site"]]
            sans_site = [l for l in en_place if not l["site"]]
            if sans_site:
                # bureau hors referentiel, ou pseudo-bureau du bloc ADMIN :
                # on ne propose rien, on le dit.
                inconnus.append({"initiales": initiales, "collaborateur": nom,
                                 "creneau": jour + " " + demi.lower(),
                                 "batiments": [l["batiment"] for l in sans_site]})
                continue
            if cible in SANS_BUREAU or not cible:
                for l in en_place:
                    actions.append({
                        "initiales": initiales, "collaborateur": nom, "jour": jour, "demi": demi,
                        "registre": valeur or "(vide)", "attributions": l["batiment"],
                        "action": "Fermer", "batiment": "", "effet": veille, "ligne": l["ligne"],
                        "remarque": "Le registre ne place plus de bureau sur cette demi-journée",
                        "colonne_fin": l["colonne_fin"],
                    })
                continue
            if any(_normaliser(s) == cible for s in sites_en_place):
                continue  # cas 4, rien a faire
            prevues = [l for l in a_venir.get(cle, []) if _normaliser(l["site"]) == cible]
            if prevues and not en_place:
                # le lieu est deja prevu, plus tard : on le dit, on n'ouvre rien
                actions.append({
                    "initiales": initiales, "collaborateur": nom, "jour": jour, "demi": demi,
                    "registre": valeur, "attributions": "(aucune aujourd'hui)",
                    "action": "À venir", "batiment": prevues[0]["batiment"],
                    "effet": prevues[0]["debut"], "ligne": prevues[0]["ligne"],
                    "remarque": "Attribution déjà prévue dès " + str(prevues[0]["debut"])
                                + ", le registre l'annonce déjà",
                    "colonne_fin": None,
                })
                continue
            for l in en_place:
                actions.append({
                    "initiales": initiales, "collaborateur": nom, "jour": jour, "demi": demi,
                    "registre": valeur, "attributions": l["batiment"],
                    "action": "Fermer", "batiment": "", "effet": veille, "ligne": l["ligne"],
                    "remarque": "Remplacée par " + valeur + " au " + date_iso,
                    "colonne_fin": l["colonne_fin"],
                })
            candidats = batiments_par_site.get(cible, [])
            if len(candidats) == 1:
                batiment, remarque = candidats[0], "Bâtiment unique pour cette ville, bureau à compléter"
            elif candidats:
                batiment = ""
                remarque = "Ville à plusieurs bâtiments (" + ", ".join(candidats) + "), à choisir"
            else:
                batiment = ""
                remarque = "Ville inconnue du référentiel des bureaux"
            actions.append({
                "initiales": initiales, "collaborateur": nom, "jour": jour, "demi": demi,
                "registre": valeur, "attributions": ", ".join(l["batiment"] for l in en_place) or "(aucune)",
                "action": "Ouvrir", "batiment": batiment, "effet": date_iso, "ligne": "",
                "remarque": remarque, "colonne_fin": None,
            })
    return actions, inconnus


def _deposer_le_rapport(actions, inconnus, sujet: str = ""):
    """Ecrit l'onglet technique du rapport, meme a blanc. Le rapport EST
    le livrable : un passage a blanc ne touche rien d'autre."""
    horodatage = _maintenant()
    corps = [[horodatage, a["initiales"], a["collaborateur"], a["jour"], a["demi"],
              a["registre"], a["attributions"], a["action"], a["batiment"],
              a["effet"], a["ligne"], a["remarque"]] for a in actions]
    for u in inconnus:
        corps.append([horodatage, u["initiales"], u["collaborateur"],
                      u["creneau"].split(" ")[0], " ".join(u["creneau"].split(" ")[1:]),
                      "", ", ".join(u["batiments"]), "À vérifier", "", "", "",
                      "Bâtiment sans ville au référentiel, aucune proposition"])
    if ONGLET_CASCADE not in _onglets(sujet=sujet):
        _feuilles(sujet).batchUpdate(spreadsheetId=ID_LIEUX, body={"requests": [
            {"addSheet": {"properties": {"title": ONGLET_CASCADE,
                                         "gridProperties": {"rowCount": 100,
                                                            "columnCount": len(COLONNES_CASCADE)}}}}]}).execute()
        # Onglet de seule consultation, donc protege des sa creation, avec
        # pour seuls editeurs am.forte@ et gestion@ (regle du 09.09.2026).
        _feuilles(sujet).batchUpdate(spreadsheetId=ID_LIEUX, body={"requests": [
            {"addProtectedRange": {"protectedRange": {
                "range": {"sheetId": _onglets(sujet=sujet)[ONGLET_CASCADE]["sheetId"]},
                "description": "Rapport de la cascade, écrit par le moteur",
                "warningOnly": False, "requestingUserCanEdit": True,
                "editors": {"users": EDITEURS}}}}]}).execute()
    _ajuster_taille(ONGLET_CASCADE, max(len(corps) + 2, 3), len(COLONNES_CASCADE), sujet=sujet)
    derniere = _lettre(len(COLONNES_CASCADE) - 1)
    _feuilles(sujet).values().clear(
        spreadsheetId=ID_LIEUX, range="'" + ONGLET_CASCADE + "'!A1:" + derniere, body={}).execute()
    _ecrire(ONGLET_CASCADE, "A1:" + derniere + str(len(corps) + 1),
            [COLONNES_CASCADE] + corps, sujet=sujet)
    return len(corps)


@mcp.tool()
@tolerant
def lieux_cascade_attributions(date: str = "", ecrire: bool = False, sujet: str = ""):
    """Fait descendre les demi-journees du registre RH dans Attributions.

    Compare, pour chaque personne d'un engagement vivant, les douze
    colonnes de demi-journees de Registre - Engagements a ce que l'onglet
    Attributions declare a la date choisie, et produit les quatre gestes :
    fermer a la veille quand la ville change ou disparait, ouvrir une
    ligne Proposee a la date d'effet quand une ville apparait, ne rien
    faire quand les deux disent la meme chose. Le bureau n'est jamais
    choisi par le moteur ; le batiment n'est pose que lorsque la ville
    n'en porte qu'un.

    ecrire a faux, valeur par defaut : rien n'est touche dans
    Attributions, seul l'onglet technique « Cascade - Propositions » est
    depose. ecrire a vrai : les fermetures et les ouvertures sont
    ecrites, puis relues.
    """
    from outils_lieux_noms import _referentiel_personnes
    date_iso = _date(date) or _aujourdhui()
    ref = _referentiel_personnes(sujet=sujet)
    site_par_batiment, batiments_par_site = _sites_et_batiments(sujet=sujet)
    etat, a_venir, colonnes = _attributions_par_creneau(
        date_iso, site_par_batiment, ref, sujet=sujet)
    cibles, nb_creneaux = _cibles_du_registre(sujet=sujet)
    actions, inconnus = _actions(date_iso, cibles, etat, a_venir, batiments_par_site)
    posees = _deposer_le_rapport(actions, inconnus, sujet=sujet)

    fermetures = [a for a in actions if a["action"] == "Fermer"]
    ouvertures = [a for a in actions if a["action"] == "Ouvrir"]
    resume = {
        "date_d_effet": date_iso,
        "veille": _veille(date_iso),
        "collaborateurs_lus": len(cibles),
        "demi_journees_lues": len(cibles) * nb_creneaux,
        "fermetures": len(fermetures),
        "ouvertures": len(ouvertures),
        "ouvertures_sans_batiment": len([a for a in ouvertures if not a["batiment"]]),
        "deja_prevues_plus_tard": len([a for a in actions if a["action"] == "À venir"]),
        "batiments_sans_ville": len(inconnus),
        "rapport": "https://docs.google.com/spreadsheets/d/" + ID_LIEUX + "/edit",
        "onglet_du_rapport": ONGLET_CASCADE,
        "lignes_du_rapport": posees,
    }
    if not ecrire:
        resume["ecrit"] = False
        resume["apercu"] = [{k: a[k] for k in ("collaborateur", "jour", "demi", "registre",
                                               "attributions", "action", "batiment", "remarque")}
                            for a in actions[:25]]
        return resume

    # 1. les fermetures, une date de fin posee a la veille
    donnees = [{
        "range": "'" + ONGLET_ATTRIBUTIONS + "'!" + _lettre(a["colonne_fin"]) + str(a["ligne"]),
        "values": [[a["effet"]]],
    } for a in fermetures]
    if donnees:
        _feuilles(sujet).values().batchUpdate(
            spreadsheetId=ID_LIEUX,
            body={"valueInputOption": "USER_ENTERED", "data": donnees}).execute()

    # 2. les ouvertures, en fin d'onglet, a completer puis valider
    lignes = _lire(ONGLET_ATTRIBUTIONS, sujet=sujet)
    premiere = len(lignes) + 1
    largeur = len(lignes[0])
    nouvelles = []
    for a in ouvertures:
        ligne = [""] * largeur
        ligne[colonnes["Collaborateur"]] = ref["personnes"].get(a["initiales"], {}).get(
            "nom_usage", a["collaborateur"])
        ligne[colonnes["Bâtiment"]] = a["batiment"]
        ligne[colonnes["Jour"]] = a["jour"]
        ligne[colonnes["Demi-journée"]] = a["demi"]
        ligne[colonnes["Date de début"]] = a["effet"]
        ligne[colonnes["Statut"]] = "Proposée"
        ligne[colonnes["Remarque"]] = (
            MARQUE_CASCADE + " : posé par la cascade du registre le "
            + _aujourdhui() + ", compléter le bureau puis valider")
        nouvelles.append(ligne)
    if nouvelles:
        _ajuster_taille(ONGLET_ATTRIBUTIONS, premiere + len(nouvelles) + 2, largeur, sujet=sujet)
        _ecrire(ONGLET_ATTRIBUTIONS,
                "A" + str(premiere) + ":" + _lettre(largeur - 1) + str(premiere + len(nouvelles) - 1),
                nouvelles, sujet=sujet, mode="USER_ENTERED")

    relecture = _lire(ONGLET_ATTRIBUTIONS, sujet=sujet)
    _journaliser([[_maintenant(), ONGLET_ATTRIBUTIONS, "Cascade du registre", date_iso,
                   str(len(lignes) - 1), str(len(relecture) - 1), "Terminé",
                   str(len(donnees)) + " fermetures, " + str(len(nouvelles))
                   + " ouvertures à compléter"]], sujet=sujet)
    resume["ecrit"] = True
    resume["lignes_avant"] = len(lignes) - 1
    resume["lignes_apres"] = len(relecture) - 1
    return resume


# --------------------------------------------------- pont d'appel

# Le client MCP garde en cache la liste des outils d'une conversation :
# un outil ajoute au serveur n'y apparait qu'a la conversation suivante.
# La maison a un pont pour cela, le parametre sujet de lieux_cycle, de la
# forme « action:nom clef=valeur ». On y greffe la cascade sans toucher a
# outils_lieux, dont la moindre retouche coute la retransmission de
# soixante-treize kilo-octets par l'API GitHub.
_pont_d_origine = outils_lieux._pont


def _pont_avec_cascade(texte: str):
    """« action:cascade ecrire=oui date=2026-09-22 », puis le pont d'origine."""
    brut = str(texte or "").strip()
    morceaux = brut.split()
    if morceaux and morceaux[0].lower() == "cascade":
        params = {}
        for m in morceaux[1:]:
            if "=" in m:
                k, v = m.split("=", 1)
                params[k.strip()] = v.strip()
        ecrire = str(params.get("ecrire", "")).lower() in ("oui", "vrai", "true", "1")
        return lieux_cascade_attributions(date=params.get("date", ""), ecrire=ecrire)
    return _pont_d_origine(texte)


try:
    outils_lieux._pont = _pont_avec_cascade
    print("[lieux cascade] pont greffé : action:cascade", flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[lieux cascade] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)
