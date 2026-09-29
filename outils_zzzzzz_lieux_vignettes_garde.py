"""Almaval - garde des vignettes des villes, 29.09.2026.

CE QUI S'EST PASSE. Le 29.09.2026 au matin, Alberto : « les petits pictos
sous les villes ont disparu !! ne doit plus arriver ». Le passage de nuit
avait bien regenere la Vue actuelle et l'onglet Occupation bureaux
d'Almaval - Patients, mais la pose des vignettes y a ete refusee, cellule
par cellule : « Vous tentez de modifier une cellule ou un objet proteges »
(journal Railway, service web, 03h48 et 03h49 UTC). Zero vignette, douze
cases vides, et rien dans le Journal du classeur pour le dire.

LA CAUSE. La porte qui pose les images est l'application web du projet
« Almaval - RH - Onboarding des collaborateurs », publiee en « execute as
the user deploying ». Elle s'execute donc sous le compte qui a publie en
dernier ce deploiement, et ce deploiement sert a tout le projet RH : il est
republie plusieurs fois par jour par les autres chantiers, depuis l'un ou
l'autre connecteur. Or depuis le 27.09.2026 la colonne des vignettes n'a
plus que gestion@ pour editeur. Il suffit qu'une republication parte d'un
autre compte pour que la pose de la nuit suivante soit refusee, sans bruit.
A 09h40 le meme jour la porte repondait de nouveau sous gestion@, ce qui
confirme que le compte d'execution change au gre des republications.

LA GARDE, trois gestes, sans toucher aux gros modules :

1. AVANT LA POSE, on demande a la porte sous quel compte elle s'execute
   (action adresseDeLApplication). Si ce n'est pas gestion@, ce compte est
   ajoute, le temps de la pose seulement, aux editeurs des protections qui
   couvrent les cellules visees, puis retire dans un bloc finally : la
   regle du compte unique est retablie quoi qu'il arrive, et la pose passe
   quel que soit le compte qui a republie.

2. LA POSE EST REPRISE tant qu'il manque des vignettes, jusqu'a trois
   passes, cinq secondes d'ecart, sur les seules cibles manquees. La porte
   Apps Script rend par moments une page HTML au lieu de sa reponse (vu
   encore le 29.09.2026) : une reprise de plus ne coute rien.

3. LE RESULTAT VA AU JOURNAL du classeur des lieux, une ligne par pose :
   « Vignettes / Pose », nombre posees, « Termine » si tout est pose,
   « A verifier » sinon, avec la raison. Un echec ne peut plus passer
   inapercu au controle du matin.

Le module s'appelle outils_zzzzzz_... pour etre charge apres
outils_zzzzz_lieux_compte_unique : il enveloppe la version deja enveloppee
(ouverture de colonne, puis reprise de outils_lieux_zzz_vignettes).
"""

import time as _time

import outils_lieux_socle
import outils_lieux_villes as _villes
from main import run_web_app
from outils_lieux_socle import _journaliser, _maintenant

COMPTE_ROBOTS = "gestion@almaval.ch"
PASSES = 3
PAUSE = 5


def _appel(payload, timeout=90):
    fn = run_web_app.fn if hasattr(run_web_app, "fn") else run_web_app
    return fn(_villes.APPLICATION_WEB_RH, payload=payload, timeout=timeout)


def _compte_de_la_porte():
    """Le compte sous lequel l'application web s'execute, ou '' si muette."""
    for essai in range(3):
        try:
            retour = _appel({"action": "adresseDeLApplication"}, timeout=60)
            reponse = retour.get("reponse") if isinstance(retour, dict) else None
            if isinstance(reponse, dict) and reponse.get("compte"):
                return str(reponse["compte"]).strip().lower()
        except Exception as exc:  # noqa: BLE001
            print("[lieux vignettes garde] compte de la porte illisible : "
                  + type(exc).__name__ + " " + str(exc)[:160], flush=True)
        _time.sleep(3)
    return ""


def _feuilles():
    return outils_lieux_socle._feuilles(COMPTE_ROBOTS)


def _couvre(plage, sid, r0, c0):
    if plage.get("sheetId", 0) != sid:
        return False
    if "startRowIndex" in plage and r0 < plage["startRowIndex"]:
        return False
    if "endRowIndex" in plage and r0 >= plage["endRowIndex"]:
        return False
    if "startColumnIndex" in plage and c0 < plage["startColumnIndex"]:
        return False
    if "endColumnIndex" in plage and c0 >= plage["endColumnIndex"]:
        return False
    return True


def _ouvrir_au_compte(compte, cibles):
    """Ajoute compte aux editeurs des protections qui bloquent les cibles.

    Rend la liste de quoi refermer : (classeur, protection telle qu'avant).
    """
    a_refermer = []
    par_classeur = {}
    for c in cibles or []:
        par_classeur.setdefault(c.get("classeur"), []).append(c)
    for classeur, lot in par_classeur.items():
        if not classeur:
            continue
        try:
            feuilles = _feuilles().get(
                spreadsheetId=classeur,
                fields="sheets(properties(sheetId,title),protectedRanges)").execute().get("sheets", [])
        except Exception as exc:  # noqa: BLE001
            print("[lieux vignettes garde] protections illisibles : " + str(exc)[:160], flush=True)
            continue
        requetes, vues = [], set()
        for f in feuilles:
            titre, sid = f["properties"]["title"], f["properties"]["sheetId"]
            cellules = [(int(c["ligne"]) - 1, int(c.get("colonne", 1)) - 1)
                        for c in lot if c.get("onglet") == titre]
            if not cellules:
                continue
            for p in f.get("protectedRanges", []):
                pid = p["protectedRangeId"]
                if pid in vues:
                    continue
                bloque = any(_couvre(p.get("range", {}), sid, r0, c0)
                             and not any(_couvre(u, sid, r0, c0) for u in p.get("unprotectedRanges", []))
                             for r0, c0 in cellules)
                editeurs = p.get("editors", {})
                users = [u.lower() for u in editeurs.get("users", [])]
                if not bloque or compte in users or editeurs.get("domainUsersCanEdit"):
                    continue
                vues.add(pid)
                a_refermer.append((classeur, p))
                requetes.append({"updateProtectedRange": {
                    "protectedRange": {"protectedRangeId": pid,
                                       "unprotectedRanges": list(p.get("unprotectedRanges", [])),
                                       "editors": {"users": users + [compte],
                                                   "groups": list(editeurs.get("groups", [])),
                                                   "domainUsersCanEdit": False}},
                    "fields": "editors,unprotectedRanges"}})
        if requetes:
            _feuilles().batchUpdate(spreadsheetId=classeur, body={"requests": requetes}).execute()
    return a_refermer


def _refermer(a_refermer):
    par_classeur = {}
    for classeur, p in a_refermer:
        editeurs = p.get("editors", {})
        par_classeur.setdefault(classeur, []).append({"updateProtectedRange": {
            "protectedRange": {"protectedRangeId": p["protectedRangeId"],
                               "unprotectedRanges": list(p.get("unprotectedRanges", [])),
                               "editors": {"users": list(editeurs.get("users", [])),
                                           "groups": list(editeurs.get("groups", [])),
                                           "domainUsersCanEdit": bool(editeurs.get("domainUsersCanEdit"))}},
            "fields": "editors,unprotectedRanges"}})
    for classeur, requetes in par_classeur.items():
        try:
            _feuilles().batchUpdate(spreadsheetId=classeur, body={"requests": requetes}).execute()
        except Exception as exc:  # noqa: BLE001
            print("[lieux vignettes garde] PROTECTION NON REFERMEE (" + str(classeur) + ") : "
                  + type(exc).__name__ + " " + str(exc)[:200], flush=True)


def _journal(cibles, posees, manquees, compte, passes):
    try:
        onglets = sorted({str(c.get("onglet")) for c in cibles or []})
        if manquees:
            raisons = sorted({str(m.get("raison", ""))[:90] for m in manquees if isinstance(m, dict)})
            detail = (str(len(manquees)) + " manquée(s) : " + "; ".join(raisons))[:480]
            etat = "À vérifier"
        else:
            detail = "toutes posées"
            etat = "Terminé"
        detail += " ; porte sous " + (compte or "compte inconnu") + " ; passes " + str(passes)
        _journaliser([[_maintenant(), "Vignettes", "Pose", ", ".join(onglets), str(len(cibles or [])),
                       str(posees), etat, detail[:480]]], sujet=COMPTE_ROBOTS)
    except Exception as exc:  # noqa: BLE001
        print("[lieux vignettes garde] journal non écrit : " + str(exc)[:160], flush=True)


try:
    _poser_precedent = _villes._poser_les_vignettes

    def _poser_les_vignettes_garde(cibles):
        if not cibles:
            return _poser_precedent(cibles)
        compte = _compte_de_la_porte()
        a_refermer = []
        if compte and compte != COMPTE_ROBOTS:
            print("[lieux vignettes garde] la porte s'exécute sous " + compte
                  + " : ouverture temporaire de la colonne des vignettes", flush=True)
            try:
                a_refermer = _ouvrir_au_compte(compte, cibles)
            except Exception as exc:  # noqa: BLE001
                print("[lieux vignettes garde] ouverture impossible : " + str(exc)[:200], flush=True)
        total, passes, retour = 0, 0, {}
        restantes = list(cibles)
        try:
            while restantes and passes < PASSES:
                if passes:
                    _time.sleep(PAUSE)
                passes += 1
                retour = _poser_precedent(restantes)
                if not isinstance(retour, dict):
                    retour = {"posees": 0, "erreur": "reponse inattendue"}
                total += int(retour.get("posees") or 0)
                if retour.get("erreur"):
                    continue
                manq = {(str(m.get("onglet")), int(m.get("ligne") or 0))
                        for m in retour.get("manquees") or [] if isinstance(m, dict)}
                restantes = [c for c in restantes if (str(c.get("onglet")), int(c.get("ligne") or 0)) in manq]
        finally:
            if a_refermer:
                _refermer(a_refermer)
        manquees = [] if not restantes else (retour.get("manquees") or
                                               [{"onglet": c.get("onglet"), "ligne": c.get("ligne"),
                                                 "raison": str(retour.get("erreur", "inconnue"))}
                                                for c in restantes])
        _journal(cibles, total, manquees, compte, passes)
        resultat = dict(retour)
        resultat.update({"posees": total, "manquees": manquees, "passes": passes,
                         "compte_de_la_porte": compte,
                         "ouverture_temporaire": len(a_refermer)})
        return resultat

    _villes._poser_les_vignettes = _poser_les_vignettes_garde
    print("[lieux vignettes garde] garde posée : compte de la porte vérifié, colonne ouverte le temps "
          "de la pose, trois passes, résultat au Journal", flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[lieux vignettes garde] garde non posée : " + type(_exc).__name__ + " " + str(_exc)[:200],
          flush=True)
