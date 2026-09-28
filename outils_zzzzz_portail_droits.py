"""Almaval - AlmaDesk Admin : les droits d'acces tenus par les groupes Google.

Raison d'etre

L'onglet « Portail - Droits » du classeur Almaval - Gestion dit qui entre
dans AlmaDesk Admin et ce qu'il voit (Adresse, Nom, Role, Service, Codes
de responsable, Ecrans, Actif, Remarque). Tenu a la main, il se perime :
une personne qui rejoint ou quitte les RH n'y est pas reportee. Decision
d'Alberto du 28.09.2026 : « faut ouvrir l'acces a ces infos RH au groupe
google equipe.rh ». L'acces se pilote donc par les groupes Google, et cet
onglet en devient le miroir.

Comment

Une ligne de l'onglet dont l'Adresse est celle d'un GROUPE Google (par
exemple equipe.rh@almaval.ch) est une ligne de groupe : son Role, son
Service et ses Ecrans valent pour chacun de ses membres. Ce module lit
les membres du groupe (utilisateurs directs et groupes imbriques, un
niveau), et tient une ligne par membre :

1. un membre sans ligne recoit une ligne « miroir » (Role, Service,
   Ecrans du groupe, Codes vides, Actif x, Remarque « Membre de <groupe>,
   miroir du jj.mm.aaaa hh:mm ») ;
2. une ligne miroir dont l'adresse n'est plus membre passe Actif « - »
   avec la remarque « N'est plus membre de <groupe> depuis le … » ;
3. une ligne miroir dont le membre est revenu repasse Actif x ;
4. une ligne tenue a la main (remarque qui ne commence pas par « Membre
   de » ni « N'est plus membre de ») n'est jamais touchee : elle prime
   sur le groupe, c'est l'exception nommee.

Les Codes de responsable d'une ligne miroir ne sont jamais ecrases : un
code pose a la main y reste. Rien n'est supprime. Sans « confirmer », le
passage simule et rend ce qu'il ecrirait.

Le script Apps Script (ZAdmin 1 Sorties) continue de lire l'onglet tel
quel : une adresse de groupe ne se connecte jamais, sa ligne est inerte
pour lui ; ce sont les lignes miroir qui ouvrent l'ecran.

Pont : lieux_cycle avec le sujet « action:portail_droits_groupes confirmer ».
Passage de nuit : a enchainer dans la tache planifiee de l'onboarding.
"""

import datetime
import zoneinfo

import main
import outils_annuaire
import outils_lieux

ID_GESTION = "19RFsMg0XxgqZz101L2zAAFeGC-oyTWBNN5YnmkZvRvE"
ONGLET = "Portail - Droits"
COLONNES = ["Adresse", "Nom", "Rôle", "Service", "Codes de responsable", "Écrans", "Actif", "Remarque"]
PREFIXE_MIROIR = "Membre de "
PREFIXE_PARTI = "N'est plus membre de "
COMPTES_DE_SERVICE = {"rh@almaval.ch", "administration@almaval.ch", "gestion@almaval.ch", "contact@almaval.ch",
                      "formation@almaval.ch", "comptabilite@almaval.ch", "inventaire@almaval.ch"}
FUSEAU = zoneinfo.ZoneInfo("Europe/Zurich")


def _appeler(outil, **kwargs):
    fn = getattr(outil, "fn", outil)
    return fn(**kwargs)


def _s(v):
    return "" if v is None else str(v)


def _horodatage():
    return datetime.datetime.now(FUSEAU).strftime("%d.%m.%Y %H:%M")


def _lire_onglet():
    """Les lignes de l'onglet, cle par intitule, avec leur numero de ligne."""
    lu = _appeler(main.get_values, spreadsheet_id=ID_GESTION, range_a1="'" + ONGLET + "'!A1:H400")
    if isinstance(lu, dict) and lu.get("erreur"):
        raise ValueError("lecture de l'onglet refusee : " + _s(lu.get("detail")))
    valeurs = lu.get("valeurs", [])
    if not valeurs:
        raise ValueError("onglet vide ou introuvable : " + ONGLET)
    entetes = [_s(e).strip() for e in valeurs[0]]
    manquantes = [c for c in COLONNES if c not in entetes]
    if manquantes:
        raise ValueError("colonnes manquantes dans " + ONGLET + " : " + ", ".join(manquantes))
    lignes = []
    for i, brut in enumerate(valeurs[1:], start=2):
        rangee = list(brut) + [""] * (len(entetes) - len(brut))
        obj = {e: rangee[j] for j, e in enumerate(entetes) if e}
        obj["_ligne"] = i
        lignes.append(obj)
    return entetes, lignes


def _est_groupe(adresse):
    try:
        outils_annuaire._groupes().groups().get(groupKey=adresse).execute()
        return True
    except Exception:  # noqa: BLE001
        return False


def _membres_utilisateurs(groupe, profondeur=0, vus=None):
    """Les adresses des membres utilisateurs actifs, groupes imbriques compris (un niveau)."""
    vus = vus if vus is not None else set()
    if groupe in vus:
        return []
    vus.add(groupe)
    membres, jeton = [], None
    while True:
        rep = outils_annuaire._groupes().members().list(groupKey=groupe, maxResults=200, pageToken=jeton).execute()
        membres.extend(rep.get("members", []))
        jeton = rep.get("nextPageToken")
        if not jeton:
            break
    adresses = []
    for m in membres:
        a = _s(m.get("email")).strip().lower()
        if not a or _s(m.get("status")).upper() not in ("", "ACTIVE"):
            continue
        if _s(m.get("type")).upper() == "GROUP":
            if profondeur < 1:
                adresses.extend(_membres_utilisateurs(a, profondeur + 1, vus))
            continue
        if a in COMPTES_DE_SERVICE:
            continue
        adresses.append(a)
    resultat = []
    for a in adresses:
        if a not in resultat:
            resultat.append(a)
    return resultat


def _nom_complet(adresse):
    try:
        u = outils_annuaire._utilisateurs().users().get(userKey=adresse).execute()
        return _s((u.get("name") or {}).get("fullName")).strip() or adresse.split("@")[0]
    except Exception:  # noqa: BLE001
        return adresse.split("@")[0]


def _lettre(index_1):
    return main._col_letter(index_1)


def passage_droits_groupes(confirmer=False):
    entetes, lignes = _lire_onglet()
    col = {c: entetes.index(c) + 1 for c in COLONNES}
    quand = _horodatage()
    par_adresse = {}
    for l in lignes:
        a = _s(l["Adresse"]).strip().lower()
        if a:
            par_adresse.setdefault(a, l)
    groupes = [l for l in lignes if _s(l["Adresse"]).strip() and _s(l["Actif"]).strip().lower() == "x" and _est_groupe(_s(l["Adresse"]).strip().lower())]
    rendu = {"quand": quand, "confirmer": bool(confirmer), "groupes": [], "ajouts": [], "reactivations": [], "departs": [], "mises_a_jour": [], "inchangees": 0, "ecritures": 0}
    ecritures = []  # (ligne, colonne, valeur)
    ajouts = []
    membres_par_groupe = {}
    for g in groupes:
        adresse_groupe = _s(g["Adresse"]).strip().lower()
        membres = _membres_utilisateurs(adresse_groupe)
        membres_par_groupe[adresse_groupe] = membres
        rendu["groupes"].append({"groupe": adresse_groupe, "role": _s(g["Rôle"]), "service": _s(g["Service"]), "ecrans": _s(g["Écrans"]), "membres": len(membres)})
        for a in membres:
            existante = par_adresse.get(a)
            if not existante:
                nom = _nom_complet(a)
                rangee = ["" for _ in entetes]
                rangee[col["Adresse"] - 1] = a
                rangee[col["Nom"] - 1] = nom
                rangee[col["Rôle"] - 1] = _s(g["Rôle"])
                rangee[col["Service"] - 1] = _s(g["Service"])
                rangee[col["Codes de responsable"] - 1] = ""
                rangee[col["Écrans"] - 1] = _s(g["Écrans"])
                rangee[col["Actif"] - 1] = "x"
                rangee[col["Remarque"] - 1] = PREFIXE_MIROIR + adresse_groupe + ", miroir du " + quand
                ajouts.append(rangee)
                rendu["ajouts"].append({"adresse": a, "nom": nom, "groupe": adresse_groupe})
                par_adresse[a] = {"_ligne": None, "Adresse": a, "Remarque": rangee[col["Remarque"] - 1], "Actif": "x"}
                continue
            remarque = _s(existante.get("Remarque")).strip()
            if not (remarque.startswith(PREFIXE_MIROIR) or remarque.startswith(PREFIXE_PARTI)):
                rendu["inchangees"] += 1  # ligne tenue a la main : elle prime
                continue
            if existante["_ligne"] is None:
                continue  # ajoutee dans ce passage par un autre groupe
            changements = {}
            if _s(existante.get("Actif")).strip().lower() != "x":
                changements["Actif"] = "x"
            for c in ("Rôle", "Service", "Écrans"):
                if _s(existante.get(c)).strip() != _s(g[c]).strip():
                    changements[c] = _s(g[c])
            nouvelle_remarque = PREFIXE_MIROIR + adresse_groupe + ", miroir du " + quand
            if remarque.startswith(PREFIXE_PARTI) or changements:
                changements["Remarque"] = nouvelle_remarque
            if changements:
                for c, v in changements.items():
                    ecritures.append((existante["_ligne"], col[c], v))
                (rendu["reactivations"] if remarque.startswith(PREFIXE_PARTI) else rendu["mises_a_jour"]).append({"adresse": a, "ligne": existante["_ligne"], "changements": changements})
            else:
                rendu["inchangees"] += 1
    # Les lignes miroir dont le membre est parti.
    tous_membres = set()
    for m in membres_par_groupe.values():
        tous_membres.update(m)
    for l in lignes:
        a = _s(l["Adresse"]).strip().lower()
        remarque = _s(l.get("Remarque")).strip()
        if not a or not remarque.startswith(PREFIXE_MIROIR):
            continue
        if a in tous_membres:
            continue
        groupe_source = remarque[len(PREFIXE_MIROIR):].split(",")[0].strip()
        if groupe_source and groupe_source not in membres_par_groupe:
            continue  # le groupe n'est plus suivi ici : on ne decide rien
        if _s(l.get("Actif")).strip() != "-":
            ecritures.append((l["_ligne"], col["Actif"], "-"))
        ecritures.append((l["_ligne"], col["Remarque"], PREFIXE_PARTI + groupe_source + " depuis le " + quand + ", miroir"))
        rendu["departs"].append({"adresse": a, "ligne": l["_ligne"], "groupe": groupe_source})
    rendu["ecritures"] = len(ecritures) + len(ajouts)
    if not confirmer:
        rendu["simulation"] = True
        return rendu
    for ligne, colonne, valeur in ecritures:
        rep = main._update_values(ID_GESTION, "'" + ONGLET + "'!" + _lettre(colonne) + str(ligne), [[valeur]], True)
        if isinstance(rep, dict) and rep.get("erreur"):
            raise ValueError("ecriture refusee en " + _lettre(colonne) + str(ligne) + " : " + _s(rep.get("detail")))
    if ajouts:
        rep = _appeler(main.append_rows, spreadsheet_id=ID_GESTION, range_a1="'" + ONGLET + "'!A1:H", values=ajouts)
        if isinstance(rep, dict) and rep.get("erreur"):
            raise ValueError("ajout refuse : " + _s(rep.get("detail")))
        rendu["plage_ajoutee"] = rep.get("updatedRange") if isinstance(rep, dict) else None
    # Relecture apres ecriture : chaque membre attendu a une ligne active.
    _, relu = _lire_onglet()
    presents = {_s(l["Adresse"]).strip().lower(): l for l in relu if _s(l["Adresse"]).strip()}
    manquants = [a for a in tous_membres if a not in presents or _s(presents[a].get("Actif")).strip().lower() != "x"]
    rendu["relecture"] = {"lignes": len(relu), "membres_attendus": len(tous_membres), "manquants_ou_inactifs": manquants}
    rendu["ok"] = not manquants
    return rendu


@main.mcp.tool()
@main.tolerant
def portail_droits_groupes(confirmer: bool = False):
    """Miroir des groupes Google dans Portail - Droits (AlmaDesk Admin) : une ligne par membre des groupes cites dans l'onglet ; simulation sans confirmer."""
    return passage_droits_groupes(confirmer=confirmer)


try:
    _pont_precedent_droits = outils_lieux._pont

    def _pont(texte_sujet: str):
        brut = str(texte_sujet or "").strip()
        mots = brut.split()
        premier = mots[0].lower() if mots else ""
        drapeaux = {m.lower() for m in mots[1:] if "=" not in m}
        if premier == "portail_droits_groupes":
            return main.tolerant(passage_droits_groupes)(confirmer=("confirmer" in drapeaux))
        return _pont_precedent_droits(brut)

    outils_lieux._pont = _pont
except Exception as _exc:  # noqa: BLE001
    print("[portail droits] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)
