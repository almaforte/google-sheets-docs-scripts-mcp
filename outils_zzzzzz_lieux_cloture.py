"""Almaval - moteur des lieux : cloture du chantier, 27.09.2026.

Demande d'Alberto du 27.09.2026 : « le chantier de la gestion des lieux
doit absolument etre finalise », avec autorisation de lever tout blocage.
Trois gestes restaient dans le moteur, nommes par les controles des 23,
25, 26 et 27.09.2026. Ce module les pose sans reecrire aucun fichier
existant. Son nom le fait charger apres tous les autres modules des
lieux, y compris outils_zzzzz_lieux_compte_unique.

1. LA GRILLE NE ROUVRE PLUS UNE ATTRIBUTION ECHUE.

   L'aplatissement de Propositions (outils_lieux.lieux_construire_
   attributions) rouvre une ligne Terminee des qu'il retrouve son occupant
   dans la grille : « Revenue dans la grille apres une cloture : nouvelle
   periode ». C'est juste quand une personne a ete retiree de la grille
   puis remise. C'est faux quand la ligne s'est fermee d'elle-meme a sa
   date de fin, fixee a la main ou par le registre RH, alors que la grille
   porte encore le nom : la ligne renait le lendemain, datee du jour. C'est
   le mecanisme de la boucle Schembari du 25.09.2026, et il attendait sept
   personnes dont la fin tombe le 30.09 ou le 31.10.2026 : Pannatier
   Virginie, Albanese Lavinia, Romero Juan, Hofer Laure, Nobis Agathe.

   Le geste : la lecture de la grille faite pour l'aplatissement ecarte
   toute occupation dont la ligne d'attribution a une date de fin passee,
   sauf si cette fin vient d'un retrait de la grille (remarque « Retiree
   de la grille » ou « Revenue dans la grille ») ou si la ligne Date de la
   grille donne une date nouvelle. La cellule de la grille est videe, pour
   que la grille dise la verite, et chaque cellule videe est ecrite au
   Journal. La ligne d'attribution reste Terminee a sa date.

1 bis. LES COLONNES L ET M SUIVENT LEUR LIGNE. Voir plus bas : l'aplatissement
   trie les lignes sans deplacer « Fin selon registre RH » ni « Origine » ;
   elles sont desormais relevees par cle avant et reposees par cle apres.

2. LA CASCADE A UNE MEMOIRE.

   La cascade du registre RH vers les attributions etait le seul moteur de
   la chaine qui n'ecrivait rien au Journal : ses chiffres du jour
   ecrasaient ceux de la veille dans « Cascade - Propositions », et il
   fallait une heure pour reconstituer une evolution. Elle ne comptait pas
   non plus les attributions surnumeraires : une personne attribuee a deux
   villes la meme demi-journee passait inapercue des lors que l'une des
   deux etait la bonne (cas Schembari Florine, jeudi, Crissier et Morges).

   Le geste : chaque passage a blanc laisse une ligne au Journal avec ses
   compteurs, et compte les demi-journees ou une meme personne a des
   attributions vivantes dans deux villes. Plusieurs bureaux dans une
   meme ville ne comptent pas : c'est un usage reel (Meierhofer Rita a
   Morges GR 94).
"""

from main import tolerant

import outils_lieux
import outils_lieux_cascade
import outils_lieux_registre
from outils_lieux_socle import (
    ID_LIEUX,
    ONGLET_ATTRIBUTIONS,
    ONGLET_GRILLE,
    _aujourdhui,
    _cellule,
    _colonne,
    _date,
    _feuilles,
    _journaliser,
    _lettre,
    _lire,
    _maintenant,
    _normaliser,
)

MARQUES_DE_RETRAIT = ("RETIREE DE LA GRILLE", "REVENUE DANS LA GRILLE")


def _appelable(objet):
    """La fonction derriere un outil, que FastMCP rende l'outil ou la fonction."""
    return getattr(objet, "fn", objet)


# ------------------------------------------------ 1. la grille ne rouvre plus

_lire_la_grille_precedente = outils_lieux._lire_la_grille


def _registre_par_cle(sujet: str = ""):
    """{cle: {fin ISO, remarque}} des lignes d'Attributions."""
    lignes = _lire(ONGLET_ATTRIBUTIONS, sujet=sujet)
    if not lignes:
        return {}
    tetes = lignes[0]
    i_cle = _colonne(tetes, "Clé")
    i_fin = _colonne(tetes, "Date de fin")
    i_rem = _colonne(tetes, "Remarque")
    par_cle = {}
    for ligne in lignes[1:]:
        cle = str(_cellule(ligne, i_cle) or "").strip()
        if cle:
            par_cle[cle] = {"fin": _date(_cellule(ligne, i_fin)),
                            "remarque": str(_cellule(ligne, i_rem) or "")}
    return par_cle


def _cle_occupation(o) -> str:
    return "|".join([o["identifiant"] or ("MENAGE:" + o["batiment"]),
                     o["jour"], o["demi"], o.get("initiales") or o["occupant"]])


def _echeance_atteinte(o, ligne, jour: str) -> bool:
    if not ligne or not ligne["fin"] or ligne["fin"] >= jour:
        return False
    if o.get("date_proposee"):
        return False  # la ligne Date de la grille ouvre une periode nouvelle
    remarque = _normaliser(ligne["remarque"])
    return not any(m in remarque for m in MARQUES_DE_RETRAIT)


def _lire_la_grille_sans_echues(onglet=ONGLET_GRILLE, sujet: str = ""):
    """La lecture de la grille, moins les occupations dont l'attribution est echue."""
    occupations, anomalies = _lire_la_grille_precedente(onglet=onglet, sujet=sujet)
    if onglet != ONGLET_GRILLE:
        return occupations, anomalies
    try:
        registre = _registre_par_cle(sujet=sujet)
    except Exception as exc:  # noqa: BLE001
        print("[lieux cloture] registre illisible, grille lue telle quelle : "
              + type(exc).__name__ + " " + str(exc)[:200], flush=True)
        return occupations, anomalies
    jour = _aujourdhui()
    gardees, echues = [], []
    for o in occupations:
        ligne = registre.get(_cle_occupation(o))
        if _echeance_atteinte(o, ligne, jour):
            echues.append((o, ligne))
        else:
            gardees.append(o)
    if echues:
        donnees = [{"range": "'" + ONGLET_GRILLE + "'!" + _lettre(o["colonne"]) + str(o["ligne"] + 1),
                    "values": [[""]]} for o, _ in echues]
        try:
            _feuilles(sujet).values().batchUpdate(
                spreadsheetId=ID_LIEUX, body={"valueInputOption": "RAW", "data": donnees}).execute()
            etat = "Terminé"
        except Exception as exc:  # noqa: BLE001
            etat = "À vérifier"
            print("[lieux cloture] cellules echues non videes : "
                  + type(exc).__name__ + " " + str(exc)[:200], flush=True)
        try:
            _journaliser([[
                _maintenant(), ONGLET_GRILLE, "Échéance atteinte, cellule vidée", o["occupant"], "", "", etat,
                o["batiment"] + " / " + o["bureau"] + " / " + o["jour"] + " " + o["demi"].lower()
                + " : attribution close au " + ligne["fin"] + ", la grille ne la rouvre plus",
            ] for o, ligne in echues], sujet=sujet)
        except Exception:  # noqa: BLE001
            pass
    return gardees, anomalies


try:
    outils_lieux._lire_la_grille = _lire_la_grille_sans_echues
    print("[lieux cloture] aplatissement : les attributions échues ne renaissent plus", flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[lieux cloture] garde des échéances non posée : "
          + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)


# ------------------------------------------------ 1 bis. les colonnes L et M suivent leur ligne

# Constate le 27.09.2026 au premier passage apres la reprise : l'aplatissement
# d'origine reecrit les onze premieres colonnes d'Attributions triees par
# batiment et bureau, sans toucher « Fin selon registre RH » ni « Origine ».
# Des que le tri deplace une ligne, ces deux colonnes restent a la place de
# l'ancienne ligne et se collent a une autre. La consolidation qui suit lit
# alors une Origine « Main » etrangere et ajoute « Registre seul » a la
# remarque : 76 lignes ce matin-la, restituees depuis l'archive du jour.
# Le geste : relever les deux colonnes par cle avant l'aplatissement, et les
# reposer par cle juste apres, avant la consolidation.

COLONNE_FIN_RH = "Fin selon registre RH"
COLONNE_ORIGINE = "Origine"
_construction_precedente = outils_lieux_registre._construire_d_origine


def _lire_brut(sujet: str = ""):
    reponse = _feuilles(sujet).values().get(
        spreadsheetId=ID_LIEUX, range="'" + ONGLET_ATTRIBUTIONS + "'",
        valueRenderOption="UNFORMATTED_VALUE").execute()
    return reponse.get("values", [])


def _fin_et_origine_par_cle(lignes):
    tetes = lignes[0]
    i_cle, i_fin, i_ori = (_colonne(tetes, "Clé"), _colonne(tetes, COLONNE_FIN_RH),
                           _colonne(tetes, COLONNE_ORIGINE))
    par_cle = {}
    for ligne in lignes[1:]:
        cle = str(_cellule(ligne, i_cle) or "").strip()
        if cle:
            par_cle[cle] = [_cellule(ligne, i_fin), _cellule(ligne, i_ori)]
    return par_cle, i_cle, i_fin, i_ori


def _construction_alignee(sujet: str = ""):
    """L'aplatissement d'origine, suivi du realignement des colonnes L et M par cle."""
    try:
        avant, _, _, _ = _fin_et_origine_par_cle(_lire_brut(sujet=sujet))
    except Exception as exc:  # noqa: BLE001
        print("[lieux cloture] releve avant aplatissement impossible : "
              + type(exc).__name__ + " " + str(exc)[:200], flush=True)
        return _construction_precedente(sujet=sujet)
    resultat = _construction_precedente(sujet=sujet)
    try:
        lignes = _lire_brut(sujet=sujet)
        _, i_cle, i_fin, i_ori = _fin_et_origine_par_cle(lignes)
        if i_ori != i_fin + 1:
            raise RuntimeError("colonnes « Fin selon registre RH » et « Origine » non contiguës")
        voulues, ecarts = [], 0
        for ligne in lignes[1:]:
            cle = str(_cellule(ligne, i_cle) or "").strip()
            actuel = [_cellule(ligne, i_fin), _cellule(ligne, i_ori)]
            voulu = avant.get(cle, ["", "Grille"]) if cle else actuel
            if [str(x) for x in voulu] != [str(x) for x in actuel]:
                ecarts += 1
            voulues.append(voulu)
        if ecarts:
            _feuilles(sujet).values().update(
                spreadsheetId=ID_LIEUX,
                range="'" + ONGLET_ATTRIBUTIONS + "'!" + _lettre(i_fin) + "2:" + _lettre(i_ori)
                + str(len(lignes)),
                valueInputOption="RAW", body={"values": voulues}).execute()
        if isinstance(resultat, dict):
            resultat["colonnes_realignees"] = ecarts
    except Exception as exc:  # noqa: BLE001
        if isinstance(resultat, dict):
            resultat["colonnes_realignees"] = {"erreur": type(exc).__name__, "detail": str(exc)[:300]}
    return resultat


try:
    outils_lieux_registre._construire_d_origine = _construction_alignee
    print("[lieux cloture] aplatissement : colonnes L et M réalignées par clé", flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[lieux cloture] réalignement non posé : " + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)


# ------------------------------------------------ 2. la cascade a une memoire

_cascade_precedente = _appelable(outils_lieux_cascade.lieux_cascade_attributions)


def _surnumeraires(date_iso: str, sujet: str = ""):
    """Les demi-journees ou une personne a des attributions vivantes dans deux villes."""
    c = outils_lieux_cascade
    from outils_lieux_noms import _referentiel_personnes
    ref = _referentiel_personnes(sujet=sujet)
    site_par_batiment, _ = c._sites_et_batiments(sujet=sujet)
    etat, _, _ = c._attributions_par_creneau(date_iso, site_par_batiment, ref, sujet=sujet)
    sortie = []
    for (initiales, jour, demi), lignes in sorted(etat.items()):
        sites = {_normaliser(l["site"] or l["batiment"]) for l in lignes}
        if len(sites) < 2:
            continue
        sortie.append({
            "initiales": initiales,
            "collaborateur": ref["personnes"].get(initiales, {}).get("nom_usage", initiales),
            "creneau": jour.capitalize() + " " + demi.lower(),
            "lieux": [(l["batiment"] + (" / " + l["bureau"] if l["bureau"] else "")
                       + " (ligne " + str(l["ligne"]) + ")") for l in lignes],
        })
    return sortie


def lieux_cascade_attributions(date: str = "", ecrire: bool = False, sujet: str = ""):
    """La cascade du registre RH vers les attributions, avec sa ligne de Journal.

    Meme cascade qu'avant. En plus, chaque passage a blanc laisse une ligne
    au Journal avec ses compteurs, et le resume compte les attributions
    surnumeraires : une personne attribuee a deux villes la meme
    demi-journee.
    """
    resume = _cascade_precedente(date=date, ecrire=ecrire, sujet=sujet)
    if not isinstance(resume, dict) or "erreur" in resume:
        return resume
    try:
        surnumeraires = _surnumeraires(resume.get("date_d_effet") or _aujourdhui(), sujet=sujet)
        resume["surnumeraires"] = len(surnumeraires)
        resume["surnumeraires_detail"] = surnumeraires[:25]
    except Exception as exc:  # noqa: BLE001
        surnumeraires = None
        resume["surnumeraires"] = {"erreur": type(exc).__name__, "detail": str(exc)[:300]}
    if not ecrire:
        detail = (str(resume.get("collaborateurs_lus", "")) + " collaborateurs, "
                  + str(resume.get("demi_journees_lues", "")) + " demi-journées, "
                  + str(resume.get("fermetures", "")) + " fermetures, "
                  + str(resume.get("ouvertures", "")) + " ouvertures dont "
                  + str(resume.get("ouvertures_sans_batiment", "")) + " sans bâtiment, "
                  + str(resume.get("deja_prevues_plus_tard", "")) + " à venir, "
                  + str(resume.get("batiments_sans_ville", "")) + " bâtiments sans ville, "
                  + (str(len(surnumeraires)) if surnumeraires is not None else "?")
                  + " demi-journées dans deux villes")
        if surnumeraires:
            detail += " : " + "; ".join(s["collaborateur"] + " " + s["creneau"] + " (" + ", ".join(s["lieux"]) + ")"
                                        for s in surnumeraires[:10])
        a_verifier = bool(surnumeraires) or bool(resume.get("fermetures")) or bool(resume.get("ouvertures"))
        try:
            _journaliser([[_maintenant(), "Cascade - Propositions", "Cascade du registre, à blanc",
                           resume.get("date_d_effet", ""), str(resume.get("demi_journees_lues", "")),
                           str(resume.get("lignes_du_rapport", "")),
                           "À vérifier" if a_verifier else "Terminé", detail[:1800]]], sujet=sujet)
        except Exception:  # noqa: BLE001
            pass
    return resume


_remplacee = False
try:
    _remplacee = outils_lieux_registre._remplacer_outil(
        "lieux_cascade_attributions", lieux_cascade_attributions)
    outils_lieux_cascade.lieux_cascade_attributions = tolerant(lieux_cascade_attributions)
except Exception as _exc:  # noqa: BLE001
    print("[lieux cloture] cascade non enveloppée : "
          + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)
print("[lieux cloture] cascade avec mémoire : " + ("oui" if _remplacee else "globale seule"), flush=True)
