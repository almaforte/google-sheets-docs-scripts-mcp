"""Almaval - l'arborescence des groupes Google, tenue par les referentiels.

Raison d'etre

Decision d'Alberto du 28.09.2026 : les groupes Google suivent l'organigramme.
Un groupe par departement (dpt.), qui contient les groupes de ses services
(service.), qui contiennent les groupes de leurs poles (sans prefixe), qui
contiennent ceux de leurs sous-poles (le pole devant : psy.assistants@,
locaux.entretien@). Le nom affiche suit l'arbre : « Administratif >
Logistique > Locaux > Intendance ». Les droits d'AlmaDesk Admin se branchent
sur ces memes groupes (outils_zzzzz_portail_droits, source 4). Alberto a
demande le 28.09.2026 que la creation soit protocolee et que les groupes se
nourrissent tout seuls quand l'organigramme evoluera : c'est ce passage, lance
chaque nuit par la tache « Almaval - Onboarding - Nuit ».

Les referentiels d'Almaval - Listes font foi, rien n'est ecrit en dur ici :

- « Départements » : Departement, Groupe, Actif ;
- « Services - Responsables » : Service, Departement (gouvernance 2026),
  Groupe Google, Actif ;
- « Services - Pôles » : Service, Pole, Departement, Groupe Google, Actif,
  Pole parent. Le parent d'un pole est la colonne « Pôle parent » si elle
  est remplie, sinon ce qui precede le dernier « > » du libelle, sinon le
  service.

Ce que le passage fait, avec « confirmer » (sinon il simule) :

1. ADRESSE : une ligne active sans groupe recoit une adresse selon la
   convention (dpt.<departement>, service.<service>, <pole>, ou
   <adresse du pole parent>.<sous-pole> ; pole.<pole> si le nom est deja
   pris par une boite), ecrite dans le referentiel ;
2. CREATION : un groupe cite qui n'existe pas est cree, administration@
   proprietaire, parametres de confidentialite de la maison (lecture par
   les membres, entree sur invitation, ecriture par le domaine, aucun
   membre externe) ;
3. IMBRICATION : chaque groupe est membre de son parent ; une imbrication
   directe dans un ancetre plus haut que le parent (redondante) est retiree ;
4. NOM : le nom affiche suit l'arbre ;
5. ALIMENTATION : un noeud qu'aucune regle du distributeur des groupes
   n'alimente (ni lui ni ses descendants) recoit les personnes affectees a
   un poste de ce service ou de ce pole (Saisie - Affectations, etat « En
   vigueur », engagement « En cours ») ; ajout seulement, les membres qui
   n'ont pas d'affectation sont signales, jamais retires.

Ce qu'il ne fait jamais : retirer une personne, supprimer un groupe,
toucher un groupe que les referentiels ne citent pas, retirer une
imbrication qui n'est pas redondante (celles qui servent la diffusion,
comme equipe.qualite@ dans les groupes de profession, restent).

Renommer une ADRESSE est un geste a part, groupe_renommer_adresse : Google
garde l'ancienne adresse en alias, les courriels et les partages suivent.

Ponts : lieux_cycle avec « action:arborescence_groupes [confirmer] » et
« action:groupe_renommer_adresse groupe=... adresse=... [confirmer] ».
"""

import datetime
import re
import unicodedata

import main
import outils_annuaire
import outils_lieux
import outils_zzzzz_portail_droits as droits

try:
    from outils_delegation import service as _service_delegue
except Exception:  # noqa: BLE001
    _service_delegue = None

DOMAINE = "almaval.ch"
PROPRIETAIRE = "administration@almaval.ch"
SEPARATEUR = " > "
ONGLET_REGLES = "Groupes - Règles"
ONGLET_AFFECTATIONS = "Saisie - Affectations"
ONGLET_ENGAGEMENTS = "Effectif - Engagements"
SCOPE_PARAMETRES = ["https://www.googleapis.com/auth/apps.groups.settings"]
PARAMETRES_MAISON = {"whoCanJoin": "INVITED_CAN_JOIN", "whoCanViewGroup": "ALL_MEMBERS_CAN_VIEW",
                     "whoCanViewMembership": "ALL_MEMBERS_CAN_VIEW", "whoCanPostMessage": "ALL_IN_DOMAIN_CAN_POST",
                     "allowExternalMembers": "false"}
URL_DISTRIBUTEUR = "https://script.google.com/a/macros/almaval.ch/s/AKfycbz8L3CfrnA3Z8sKcphk8AZOtPd9sR1UWVwSdaxnPmlsPmNMBmp8U5N7pDUsuPbG_4uc/exec"


def _s(v):
    return "" if v is None else str(v)


def _slug(texte):
    t = unicodedata.normalize("NFKD", _s(texte)).encode("ascii", "ignore").decode("ascii").lower()
    t = t.replace("&", " ")
    t = re.sub(r"[^a-z0-9]+", ".", t).strip(".")
    return re.sub(r"\.+", ".", t)


def _serial_aujourdhui():
    return (datetime.date.today() - datetime.date(1899, 12, 30)).days


def _nombre(v):
    try:
        return float(_s(v).replace(",", "."))
    except ValueError:
        return None


# ---------------------------------------------------------------- lecture


def _lire_referentiels():
    """Les trois referentiels, avec le numero de ligne et la colonne du groupe pour l'ecriture d'une adresse."""
    ent_d, dep = droits._tableau(droits._lire(droits.ID_LISTES, "'" + droits.ONGLET_DEPARTEMENTS + "'!A1:H40"))
    ent_s, srv = droits._tableau(droits._lire(droits.ID_LISTES, "'" + droits.ONGLET_SERVICES + "'!A1:L80"))
    ent_p, pol = droits._tableau(droits._lire(droits.ID_LISTES, "'" + droits.ONGLET_POLES + "'!A1:L200"))
    departements = [{"departement": _s(l.get("Département")).strip(), "groupe": _s(l.get("Groupe")).strip().lower(),
                     "_ligne": l["_ligne"]}
                    for l in dep if _s(l.get("Département")).strip() and droits._actif(l.get("Actif"))]
    services = [{"service": _s(l.get("Service")).strip(), "groupe": _s(l.get("Groupe Google")).strip().lower(),
                 "departement": _s(l.get("Département (gouvernance 2026)") or l.get("Département")).strip(), "_ligne": l["_ligne"]}
                for l in srv if _s(l.get("Service")).strip() and droits._actif(l.get("Actif"))]
    poles = []
    for l in pol:
        service, pole = _s(l.get("Service")).strip(), _s(l.get("Pôle")).strip()
        if not service or not pole or not droits._actif(l.get("Actif")):
            continue
        parent = _s(l.get("Pôle parent")).strip()
        if not parent and SEPARATEUR in pole:
            parent = pole.rsplit(SEPARATEUR, 1)[0].strip()
        poles.append({"service": service, "pole": pole, "departement": _s(l.get("Département")).strip(),
                      "groupe": _s(l.get("Groupe Google")).strip().lower(), "parent": parent,
                      "segment": pole.rsplit(SEPARATEUR, 1)[-1].strip(), "_ligne": l["_ligne"]})
    colonnes = {"dep": ent_d.index("Groupe") + 1 if "Groupe" in ent_d else 0,
                "srv": ent_s.index("Groupe Google") + 1 if "Groupe Google" in ent_s else 0,
                "pol": ent_p.index("Groupe Google") + 1 if "Groupe Google" in ent_p else 0}
    return departements, services, poles, colonnes


def _fiche(adresse, cache):
    """Adresse principale, nom, alias et membres directs (groupes et comptes), ou None si le groupe n'existe pas."""
    adresse = _s(adresse).strip().lower()
    if not adresse:
        return None
    if adresse in cache:
        return cache[adresse]
    try:
        g = outils_annuaire._groupes().groups().get(groupKey=adresse).execute()
    except Exception:  # noqa: BLE001
        cache[adresse] = None
        return None
    enfants, comptes, jeton = [], [], None
    while True:
        rep = outils_annuaire._groupes().members().list(groupKey=adresse, maxResults=200, pageToken=jeton).execute()
        for m in rep.get("members", []):
            e = _s(m.get("email")).strip().lower()
            if _s(m.get("type")).upper() == "GROUP":
                enfants.append(e)
            elif _s(m.get("type")).upper() == "USER":
                comptes.append({"adresse": e, "role": _s(m.get("role")).upper()})
        jeton = rep.get("nextPageToken")
        if not jeton:
            break
    f = {"adresse": _s(g.get("email")).strip().lower(), "nom": _s(g.get("name")).strip(),
         "alias": [_s(a).strip().lower() for a in (g.get("aliases") or [])], "enfants": enfants, "comptes": comptes}
    for a in [adresse, f["adresse"]] + f["alias"]:
        cache[a] = f
    return f


def _adresse_prise(adresse, cache):
    """Vrai si l'adresse est deja un groupe, un compte ou un alias."""
    if _fiche(adresse, cache) is not None:
        return True
    try:
        outils_annuaire._utilisateurs().users().get(userKey=adresse).execute()
        return True
    except Exception:  # noqa: BLE001
        return False


def _arbre(departements, services, poles):
    """Les noeuds voulus, cles par referentiel : niveau, chemin (liste de segments), parent (cle), groupe, ligne."""
    noeuds, anomalies = {}, []
    dep_actifs = {d["departement"] for d in departements}
    for d in departements:
        noeuds[("D", d["departement"])] = {"niveau": "Département", "chemin": [d["departement"]], "parent": None,
                                          "groupe": d["groupe"], "ligne": d["_ligne"], "table": "dep", "service": "", "pole": "",
                                          "departement": d["departement"]}
    for sv in services:
        if sv["departement"] not in dep_actifs:
            anomalies.append("Service hors département : " + sv["service"] + " (" + sv["departement"] + "), laissé hors de l'arbre")
            continue
        noeuds[("S", sv["service"])] = {"niveau": "Service", "chemin": [sv["departement"], sv["service"]], "parent": ("D", sv["departement"]),
                                       "groupe": sv["groupe"], "ligne": sv["_ligne"], "table": "srv", "service": sv["service"], "pole": "",
                                       "departement": sv["departement"]}
    par_service = {}
    for p in poles:
        par_service.setdefault(p["service"], []).append(p)
    for service, liste in par_service.items():
        if ("S", service) not in noeuds:
            anomalies.append("Pôles d'un service absent de l'arbre : " + service)
            continue
        base = noeuds[("S", service)]
        for p in liste:
            chaine = droits._chaine_pole(p["pole"], liste)
            if not chaine or chaine[-1] != p["pole"]:
                anomalies.append("Chaîne de pôles cassée : " + service + SEPARATEUR + p["pole"])
                continue
            if p["parent"] and p["parent"] not in [q["pole"] for q in liste]:
                anomalies.append("Pôle parent introuvable : " + service + SEPARATEUR + p["pole"] + " (parent " + p["parent"] + ")")
            segments = [next(q["segment"] for q in liste if q["pole"] == c) for c in chaine]
            parent = ("P", service, chaine[-2]) if len(chaine) > 1 else ("S", service)
            noeuds[("P", service, p["pole"])] = {"niveau": "Pôle", "chemin": base["chemin"] + segments, "parent": parent,
                                                "groupe": p["groupe"], "ligne": p["_ligne"], "table": "pol", "service": service,
                                                "pole": p["pole"], "segment": p["segment"], "departement": base["departement"]}
    return noeuds, anomalies


def _adresse_convenue(cle, n, noeuds, cache, prises):
    if n["niveau"] == "Département":
        base = "dpt." + _slug(n["chemin"][0])
    elif n["niveau"] == "Service":
        base = "service." + _slug(n["service"])
    else:
        parent = noeuds.get(n["parent"])
        if parent and parent["niveau"] == "Pôle" and parent.get("groupe"):
            base = parent["groupe"].split("@")[0] + "." + _slug(n["segment"])
        else:
            base = _slug(n["segment"])
    adresse = base + "@" + DOMAINE
    if adresse not in prises and _fiche(adresse, cache) is not None:
        return adresse  # le groupe de la convention existe deja et aucun autre noeud ne le cite : il est adopte, jamais double
    if adresse in prises or _adresse_prise(adresse, cache):
        adresse = ("pole." + base if n["niveau"] == "Pôle" else base + ".groupe") + "@" + DOMAINE
    return adresse


# ---------------------------------------------------------------- parametres de confidentialite


def _parametrer(adresse):
    """Pose les parametres de la maison : API Groups Settings par delegation, a defaut par le distributeur des groupes."""
    if _service_delegue is not None:
        try:
            _service_delegue("groupssettings", "v1", SCOPE_PARAMETRES, "").groups().patch(
                groupUniqueId=adresse, body=dict(PARAMETRES_MAISON)).execute()
            return "posés (Groups Settings)"
        except Exception as err:  # noqa: BLE001
            premier = _s(err)[:120]
    else:
        premier = "délégation indisponible"
    try:
        corps = {"action": "definirParametresGroupe", "groupe": adresse,
                 "parametres": {k: (v == "true" if v in ("true", "false") else v) for k, v in PARAMETRES_MAISON.items()}}
        rep = droits._appeler(main.run_web_app, url=URL_DISTRIBUTEUR, payload=corps)
        if isinstance(rep, dict) and (rep.get("erreur") or rep.get("error")):
            return "non posés : " + premier + " / distributeur : " + _s(rep.get("erreur") or rep.get("error"))[:120]
        return "posés (distributeur des groupes)"
    except Exception as err:  # noqa: BLE001
        return "non posés : " + premier + " / distributeur : " + _s(err)[:120]


# ---------------------------------------------------------------- alimentation par les affectations


def _groupes_des_regles(cache):
    _, regles = droits._tableau(droits._lire(droits.ID_LISTES, "'" + ONGLET_REGLES + "'!A1:H200"))
    out = set()
    for r in regles:
        g = _s(r.get("Groupe")).strip().lower()
        if g and droits._actif(r.get("Actif")):
            f = _fiche(g, cache)
            out.add(f["adresse"] if f else g)
    return out


def _affectations_en_vigueur():
    """[(adresse, service, pole)] des affectations en vigueur d'engagements en cours, a la date du jour."""
    _, engagements = droits._tableau(droits._lire(droits.ID_GESTION, "'" + ONGLET_ENGAGEMENTS + "'!A1:J600"))
    initiales = {}
    for e in engagements:
        cle = _s(e.get("Clé engagement")).strip()
        if cle and _s(e.get("État de l'engagement")).strip() == "En cours":
            initiales[cle] = _s(e.get("Initiales")).strip()
    table = droits._adresses_par_initiales()
    _, affectations = droits._tableau(droits._lire(droits.ID_GESTION, "'" + ONGLET_AFFECTATIONS + "'!A1:W800"))
    jour = _serial_aujourdhui()
    out, sans_adresse = [], set()
    for a in affectations:
        if _s(a.get("État")).strip() != "En vigueur":
            continue
        cle = _s(a.get("Clé engagement")).strip()
        if cle not in initiales:
            continue
        debut, fin = _nombre(a.get("Date de début")), _nombre(a.get("Date de fin"))
        if debut is not None and debut > jour:
            continue
        if fin is not None and fin < jour:
            continue
        adresse = table.get(initiales[cle], "")
        if not adresse:
            sans_adresse.add(initiales[cle])
            continue
        out.append((adresse, _s(a.get("Service")).strip(), _s(a.get("Pôle")).strip()))
    return out, sorted(sans_adresse)


# ---------------------------------------------------------------- passage


def passage_arborescence(confirmer=False, retirer_redondances=True, alimenter=True):
    departements, services, poles, colonnes = _lire_referentiels()
    noeuds, anomalies = _arbre(departements, services, poles)
    cache = {}
    rendu = {"confirmer": bool(confirmer), "noeuds": len(noeuds), "adresses": [], "creations": [], "imbrications": [],
             "redondances_retirees": [], "noms": [], "alimentation": [], "hors_affectations": [], "anomalies": anomalies,
             "erreurs": []}

    # 1. Adresse des lignes sans groupe, selon la convention, ecrite dans le referentiel.
    prises = {n["groupe"] for n in noeuds.values() if n["groupe"]}
    ordre = sorted(noeuds.items(), key=lambda kv: len(kv[1]["chemin"]))
    for cle, n in ordre:
        if n["groupe"]:
            continue
        adresse = _adresse_convenue(cle, n, noeuds, cache, prises)
        prises.add(adresse)
        n["groupe"] = adresse
        rendu["adresses"].append({"chemin": SEPARATEUR.join(n["chemin"]), "adresse": adresse})
        if confirmer and colonnes[n["table"]]:
            onglet = {"dep": droits.ONGLET_DEPARTEMENTS, "srv": droits.ONGLET_SERVICES, "pol": droits.ONGLET_POLES}[n["table"]]
            rep = main._update_values(droits.ID_LISTES, "'" + onglet + "'!" + droits._lettre(colonnes[n["table"]]) + str(n["ligne"]), [[adresse]], True)
            if isinstance(rep, dict) and rep.get("erreur"):
                rendu["erreurs"].append("Écriture de l'adresse de " + SEPARATEUR.join(n["chemin"]) + " : " + _s(rep.get("detail"))[:160])

    # 2. Creation des groupes absents.
    for cle, n in ordre:
        if _fiche(n["groupe"], cache) is not None:
            continue
        nom = SEPARATEUR.join(n["chemin"])
        rendu["creations"].append({"adresse": n["groupe"], "nom": nom})
        if not confirmer:
            continue
        try:
            outils_annuaire._groupes().groups().insert(body={"email": n["groupe"], "name": nom,
                                                             "description": n["niveau"] + " " + nom + " de l'organigramme d'Almaval. Groupe créé et tenu par l'arborescence des groupes."}).execute()
            outils_annuaire._groupes().members().insert(groupKey=n["groupe"], body={"email": PROPRIETAIRE, "role": "OWNER"}).execute()
            rendu["creations"][-1]["parametres"] = _parametrer(n["groupe"])
            cache.pop(n["groupe"], None)
        except Exception as err:  # noqa: BLE001
            rendu["erreurs"].append("Création de " + n["groupe"] + " : " + _s(err)[:200])

    # 3. Imbrications, redondances et noms.
    def cles_de(f):
        return set([f["adresse"]] + f["alias"])

    for cle, n in ordre:
        f = _fiche(n["groupe"], cache)
        if f is None:
            if confirmer:
                rendu["erreurs"].append("Groupe introuvable après création : " + n["groupe"])
            continue
        if n["parent"]:
            pn = noeuds.get(n["parent"])
            p = _fiche(pn["groupe"], cache) if pn else None
            if p is None:
                if pn and not confirmer:
                    rendu["imbrications"].append({"parent": pn["groupe"], "enfant": f["adresse"], "apres_creation": True})
                else:
                    rendu["erreurs"].append("Parent introuvable pour " + f["adresse"])
            elif not cles_de(f).intersection(p["enfants"]):
                rendu["imbrications"].append({"parent": p["adresse"], "enfant": f["adresse"]})
                if confirmer:
                    try:
                        outils_annuaire._groupes().members().insert(groupKey=p["adresse"], body={"email": f["adresse"], "role": "MEMBER"}).execute()
                        p["enfants"].append(f["adresse"])
                    except Exception as err:  # noqa: BLE001
                        texte = _s(err)
                        if "412" in texte or "Condition not met" in texte:
                            texte = "412, le parent porte sans doute le libellé de groupe de sécurité : " + texte[:120]
                        rendu["erreurs"].append("Imbrication de " + f["adresse"] + " dans " + p["adresse"] + " : " + texte[:220])
            # Imbrication directe dans un ancetre plus haut que le parent : redondante.
            anc = noeuds.get(pn["parent"]) if pn and pn.get("parent") else None
            while anc:
                a = _fiche(anc["groupe"], cache)
                if a is not None:
                    doublon = cles_de(f).intersection(a["enfants"])
                    if doublon:
                        rendu["redondances_retirees"].append({"groupe": f["adresse"], "retire_de": a["adresse"]})
                        if confirmer and retirer_redondances:
                            try:
                                outils_annuaire._groupes().members().delete(groupKey=a["adresse"], memberKey=list(doublon)[0]).execute()
                                a["enfants"] = [e for e in a["enfants"] if e not in doublon]
                            except Exception as err:  # noqa: BLE001
                                rendu["erreurs"].append("Retrait de la redondance " + f["adresse"] + " dans " + a["adresse"] + " : " + _s(err)[:160])
                anc = noeuds.get(anc["parent"]) if anc.get("parent") else None
        nom = SEPARATEUR.join(n["chemin"])
        if f["nom"] != nom:
            rendu["noms"].append({"adresse": f["adresse"], "avant": f["nom"], "apres": nom})
            if confirmer:
                try:
                    outils_annuaire._groupes().groups().patch(groupKey=f["adresse"], body={"name": nom}).execute()
                    f["nom"] = nom
                except Exception as err:  # noqa: BLE001
                    rendu["erreurs"].append("Nom de " + f["adresse"] + " : " + _s(err)[:200])

    # 4. Alimentation par les affectations, pour les noeuds qu'aucune regle du distributeur n'alimente.
    if alimenter:
        try:
            regles = _groupes_des_regles(cache)
            affectations, sans_adresse = _affectations_en_vigueur()
            if sans_adresse:
                rendu["anomalies"].append("Affectations sans adresse Almaval (initiales) : " + ", ".join(sans_adresse))
            descendants = {}
            for cle, n in noeuds.items():
                chaine = [cle]
                for c2, m in noeuds.items():
                    x = m.get("parent")
                    while x:
                        if x == cle:
                            chaine.append(c2)
                            break
                        x = noeuds.get(x, {}).get("parent")
                descendants[cle] = chaine
            for cle, n in noeuds.items():
                if n["niveau"] == "Département":
                    continue
                groupes_sous = set()
                for c2 in descendants[cle]:
                    f2 = _fiche(noeuds[c2]["groupe"], cache)
                    if f2:
                        groupes_sous.add(f2["adresse"])
                if groupes_sous.intersection(regles):
                    continue
                f = _fiche(n["groupe"], cache)
                if f is None:
                    continue
                if n["niveau"] == "Service":
                    voulus = {a for a, s, p in affectations if s == n["service"] and not p}
                else:
                    voulus = {a for a, s, p in affectations if s == n["service"] and p in (n["pole"], n["segment"])}
                directs = {c["adresse"] for c in f["comptes"]}
                for a in sorted(voulus - directs):
                    rendu["alimentation"].append({"groupe": f["adresse"], "ajout": a})
                    if confirmer:
                        try:
                            outils_annuaire._groupes().members().insert(groupKey=f["adresse"], body={"email": a, "role": "MEMBER"}).execute()
                        except Exception as err:  # noqa: BLE001
                            if "already" not in _s(err).lower():
                                rendu["erreurs"].append("Ajout de " + a + " dans " + f["adresse"] + " : " + _s(err)[:160])
                if voulus:
                    for c in f["comptes"]:
                        if c["role"] == "MEMBER" and c["adresse"] not in voulus and c["adresse"] not in droits.COMPTES_DE_SERVICE:
                            rendu["hors_affectations"].append({"groupe": f["adresse"], "membre": c["adresse"]})
        except Exception as err:  # noqa: BLE001
            rendu["erreurs"].append("Alimentation par les affectations : " + _s(err)[:200])

    rendu["ok"] = not rendu["erreurs"]
    if not confirmer:
        rendu["simulation"] = True
    return rendu


@main.mcp.tool()
@main.tolerant
def arborescence_groupes(confirmer: bool = False, retirer_redondances: bool = True, alimenter: bool = True):
    """Arborescence des groupes Google tenue par Departements, Services - Responsables et Services - Poles : adresse par convention, creation, imbrication departement > service > pole > sous-pole, nom selon l'arbre, alimentation par les affectations ; ne retire jamais une personne ; simulation sans confirmer."""
    return passage_arborescence(confirmer=confirmer, retirer_redondances=retirer_redondances, alimenter=alimenter)


def renommer_adresse(groupe, adresse, confirmer=False):
    groupe, adresse = _s(groupe).strip().lower(), _s(adresse).strip().lower()
    if not groupe or "@" not in adresse or not adresse.endswith("@" + DOMAINE):
        return {"refuse": True, "raison": "groupe et adresse @" + DOMAINE + " attendus"}
    g = outils_annuaire._groupes().groups().get(groupKey=groupe).execute()
    avant = {"adresse": _s(g.get("email")).lower(), "alias": [_s(a).lower() for a in (g.get("aliases") or [])]}
    if avant["adresse"] == adresse:
        return {"deja_fait": True, "avant": avant}
    if not confirmer:
        return {"simulation": True, "avant": avant, "apres": adresse}
    if adresse in avant["alias"]:
        # L'adresse voulue est deja un alias de ce groupe : Google refuse de la prendre comme adresse principale tant qu'elle l'est.
        outils_annuaire._groupes().groups().aliases().delete(groupKey=avant["adresse"], alias=adresse).execute()
    outils_annuaire._groupes().groups().patch(groupKey=avant["adresse"], body={"email": adresse}).execute()
    relu = outils_annuaire._groupes().groups().get(groupKey=adresse).execute()
    apres = {"adresse": _s(relu.get("email")).lower(), "alias": [_s(a).lower() for a in (relu.get("aliases") or [])]}
    return {"avant": avant, "apres": apres, "ok": apres["adresse"] == adresse}


@main.mcp.tool()
@main.tolerant
def groupe_renommer_adresse(groupe: str, adresse: str, confirmer: bool = False):
    """Change l'adresse d'un groupe ; Google garde l'ancienne en alias (courriels et partages suivent). Relit apres. Simulation sans confirmer."""
    return renommer_adresse(groupe, adresse, confirmer)


try:
    _pont_precedent_arbo = outils_lieux._pont

    def _pont(texte_sujet: str):
        brut = str(texte_sujet or "").strip()
        mots = brut.split()
        premier = mots[0].lower() if mots else ""
        drapeaux = {m.lower() for m in mots[1:] if "=" not in m}
        cles = dict(m.split("=", 1) for m in mots[1:] if "=" in m)
        if premier == "arborescence_groupes":
            return main.tolerant(passage_arborescence)(confirmer=("confirmer" in drapeaux),
                                                        retirer_redondances=("garder_redondances" not in drapeaux),
                                                        alimenter=("sans_alimentation" not in drapeaux))
        if premier == "groupe_renommer_adresse":
            return main.tolerant(renommer_adresse)(cles.get("groupe", ""), cles.get("adresse", ""), "confirmer" in drapeaux)
        return _pont_precedent_arbo(brut)

    outils_lieux._pont = _pont
except Exception as _exc:  # noqa: BLE001
    print("[arborescence groupes] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)
