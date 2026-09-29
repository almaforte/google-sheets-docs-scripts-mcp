"""Almaval - moteur des lieux : la colonne Intendance, 29.09.2026.

DEMANDE D'ALBERTO, 29.09.2026 : « les menages ne doivent pas s'afficher
comme ca dans les bureaux, vous etes fous ! Ca doit rester dans la colonne
Menage, qui en plus devrait s'appeler maintenant Intendance pour etre
coherent avec notre organigramme ».

CE QUI SE PASSAIT. Les passages de menage sont ecrits comme des evenements
dans l'agenda Google de CHAQUE salle (« Menage, passage de 18h30 a 21h30 »).
Le moteur relit le ponctuel des agendas de salles et le superpose a la case
du bureau : la Vue actuelle, et sa copie Occupation bureaux d'Almaval -
Patients, montraient donc « Spicer Clare, Menage, passage de 18h30 a 21h30
18:30-21:30 » dans chaque bureau de Lausanne - Riponne le jeudi.

CE QUE FAIT CE MODULE, sans retoucher les gros modules :

1. LE MENAGE VA DANS SA COLONNE. Tout evenement ponctuel dont le titre
   commence par Menage, Intendance ou Nettoyage est retire de la case du
   bureau et depose dans la colonne Intendance du meme batiment, meme jour,
   meme demi-journee, une seule fois, sous la forme « Menage 18h30-21h30 »,
   celle qu'emploie deja le registre, trait d'union court compris : un
   libelle identique a celui du registre ne s'affiche qu'une fois. Vaut pour la vue du jour
   (_ponctuels_semaine du registre) et pour l'onglet masque « Occupation
   bureaux - Ponctuel » d'Almaval - Patients (_ponctuels_datees), que le
   script 10_occupation_date superpose a la date choisie.

2. LA COLONNE S'APPELLE INTENDANCE. Le moteur reconnaissait la colonne a
   son intitule exact « Menage ». « Intendance » est desormais compris
   comme le meme intitule : alias de bureau INTENDANCE -> MENAGE, et
   _normaliser rend MENAGE pour la chaine exacte INTENDANCE dans les
   modules des grilles. outils_lieux_admin est volontairement ecarte : il
   porte un service « Intendance » dans son propre dictionnaire, qui ne
   doit pas devenir « MENAGE ». L'occupant generique reste « Menage » :
   c'est l'activite, la colonne est le service qui la porte.
"""

import re as _re
import sys as _sys

import outils_lieux_socle as _socle

INTITULE = "Intendance"
_TITRES_MENAGE = ("MENAGE", "INTENDANCE", "NETTOYAGE")
_HORAIRE = _re.compile(r"(\d{1,2}):(\d{2})\s*[–-]\s*(\d{1,2}):(\d{2})\s*$")

_normaliser_origine = _socle._normaliser


def _normaliser_intendance(texte) -> str:
    cle = _normaliser_origine(texte)
    return "MENAGE" if cle == "INTENDANCE" else cle


def _est_menage(libelle) -> bool:
    cle = _normaliser_origine(libelle)
    return any(cle.startswith(t) for t in _TITRES_MENAGE)


def _libelle_menage(libelle) -> str:
    m = _HORAIRE.search(str(libelle or ""))
    if not m:
        return "Ménage"
    h0, m0, h1, m1 = m.groups()
    return "Ménage " + str(int(h0)).zfill(2) + "h" + m0 + "-" + str(int(h1)).zfill(2) + "h" + m1


_poses = []

# ------------------------------------------------ 2. Intendance = Menage
try:
    _socle.ALIAS_BUREAUX["INTENDANCE"] = "MENAGE"
    for _nom in list(_sys.modules):
        if not (_nom.startswith("outils_lieux") or (_nom.startswith("outils_z") and "lieux" in _nom)):
            continue
        if _nom in ("outils_lieux_admin", __name__):
            continue
        _m = _sys.modules.get(_nom)
        if _m is not None and getattr(_m, "_normaliser", None) is _normaliser_origine:
            _m._normaliser = _normaliser_intendance
            _poses.append(_nom)
except Exception as _exc:  # noqa: BLE001
    print("[lieux intendance] équivalence non posée : " + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)

# ------------------------------------------------ 1a. vue du jour
try:
    import outils_lieux_registre as _registre

    _semaine_amont = _registre._ponctuels_semaine

    def _ponctuels_semaine_intendance(date_iso, sujet=""):
        ponctuels, echecs, lus = _semaine_amont(date_iso, sujet=sujet)
        colonne = _socle._normaliser_bureau(INTITULE)
        sortie = {}
        for cle, libelles in (ponctuels or {}).items():
            morceaux = cle.split("|")
            for libelle in libelles:
                if _est_menage(libelle) and len(morceaux) == 4:
                    cible = "|".join([morceaux[0], colonne, morceaux[2], morceaux[3]])
                    texte = _libelle_menage(libelle)
                else:
                    cible, texte = cle, libelle
                liste = sortie.setdefault(cible, [])
                if texte not in liste:
                    liste.append(texte)
        return sortie, echecs, lus

    _registre._ponctuels_semaine = _ponctuels_semaine_intendance
    _poses.append("vue du jour")
except Exception as _exc:  # noqa: BLE001
    print("[lieux intendance] vue du jour non greffée : " + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)

# ------------------------------------------------ 1b. ponctuel date par date (Patients)
try:
    import outils_lieux_ponctuel as _ponctuel

    _datees_amont = _ponctuel._ponctuels_datees

    def _ponctuels_datees_intendance(depuis_iso, semaines, sujet=""):
        lignes, echecs, lus = _datees_amont(depuis_iso, semaines, sujet=sujet)
        sortie, vues = [], set()
        for ligne in lignes or []:
            ligne = list(ligne)
            if len(ligne) >= 6 and _est_menage(ligne[5]):
                ligne[4] = INTITULE
                ligne[5] = _libelle_menage(ligne[5])
            cle = tuple(str(x) for x in ligne[:6])
            if cle in vues:
                continue
            vues.add(cle)
            sortie.append(ligne)
        return sortie, echecs, lus

    _ponctuel._ponctuels_datees = _ponctuels_datees_intendance
    _poses.append("ponctuel daté")
except Exception as _exc:  # noqa: BLE001
    print("[lieux intendance] ponctuel daté non greffé : " + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)

# ------------------------------------------------ 3. l'horaire seul dans la case
# La remarque d'une ligne de menage du registre peut porter le marqueur
# technique « Registre seul » (Vevey, 29.09.2026) : il s'affichait dans la
# case, « Menage 18h30-20h30, Registre seul », et empechait de reconnaitre
# le meme passage venu de l'agenda. La case ne garde que l'horaire.
try:
    import outils_lieux as _ol

    _valeur_amont = _ol._valeur_affichee

    def _valeur_affichee_intendance(occupant, remarque):
        texte = str(remarque or "")
        if _normaliser_origine(occupant) == "MENAGE":
            texte = ", ".join(p.strip() for p in texte.split(",")
                              if p.strip() and _normaliser_origine(p) != "REGISTRE SEUL")
        return _valeur_amont(occupant, texte)

    _ol._valeur_affichee = _valeur_affichee_intendance
    _poses.append("horaire du ménage")
except Exception as _exc:  # noqa: BLE001
    print("[lieux intendance] horaire non greffé : " + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)

print("[lieux intendance] ménage des agendas déposé dans la colonne Intendance ; "
      "Intendance compris comme Ménage ; posé dans : " + ", ".join(_poses), flush=True)
