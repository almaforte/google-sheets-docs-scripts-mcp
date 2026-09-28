"""Almaval - AlmaDesk Admin : les droits d'acces tenus par l'organigramme et les groupes Google.

Raison d'etre

L'onglet « Portail - Droits » du classeur Almaval - Gestion dit qui entre
dans AlmaDesk Admin et ce qu'il voit. Tenu a la main, il se perime.
Decisions d'Alberto du 28.09.2026 : l'acces des RH se pilote par le
groupe Google equipe.rh@ ; puis, sur la conception validee le meme jour
(claude/almadesk-admin-conception-vues-par-organigramme-28092026.md), ce
que chacun voit se deduit de sa place dans l'organigramme : departement,
service, pole, et des groupes Google qui portent les services. Cet onglet
en devient le MIROIR, tenu par ce module.

Un droit est un evenement : une ligne par personne, par role et par
perimetre. L'application (ZAdmin 0 Droits) fait l'union des lignes
actives d'une adresse.

Ce que le passage produit, a partir de trois sources lues a chaque fois :

1. Les LIGNES DE GROUPE de Portail - Droits (une Adresse qui est un
   groupe Google, Actif x) : chaque membre (utilisateurs directs et
   groupes imbriques, un niveau, comptes de service exclus) recoit une
   ligne miroir avec le role, le departement, le service, le pole et les
   ecrans de la ligne de groupe. Source « <groupe> ».
2. L'onglet « Departements » d'Almaval - Listes : le responsable de
   chaque departement actif recoit une ligne « Responsable de
   departement ». Source « Listes : Departements ». Depuis le 28.09.2026,
   la Fonction transversale a un responsable, le responsable des
   operations (decision d'Alberto) : elle n'est plus sautee.
3. L'onglet « Services - Responsables » d'Almaval - Listes : le
   responsable de chaque service actif (initiales, traduites en adresse
   par la colonne « E-mail Almaval » de Saisie - Collaborateurs) recoit
   une ligne « Responsable de service », avec le departement du service
   (colonne « Departement (gouvernance 2026) »). Source « Listes :
   Services - Responsables ».

La colonne Nom porte le nom d'etat civil et le prenom d'usage, lus dans
Registre - Personnes du classeur Almaval - Collaborateurs - Effectif
(regle d'Alberto, rappelee le 28.09.2026 : « partout dans l'AlmaDesk ») ;
le Nom d'une ligne miroir existante est mis a jour s'il differe.

Regles :
- une ligne est identifiee par (adresse, role, departement, service,
  pole) ; une ligne miroir qui n'est plus produite passe Actif « - »
  avec la mention « N'est plus ... depuis le ... » ; une ligne miroir
  qui redevient produite repasse « x » ;
- une ligne tenue a la main (Remarque qui ne commence ni par « Miroir »
  ni par « Membre de » ni par « N'est plus ») n'est jamais touchee et
  prime sur la ligne miroir de meme cle, qui n'est alors pas ecrite ;
- les Codes de responsable d'une ligne existante ne sont jamais ecrases ;
- les super-administrateurs par defaut du code (am.forte@, gestion@) ne
  recoivent aucune ligne miroir : ils tiennent tout par le code et
  n'apparaissent pas dans l'organigramme des droits ;
- rien n'est supprime ; sans « confirmer », le passage simule et rend ce
  qu'il ecrirait ; apres ecriture, relecture et comptage.

4. Depuis le 28.09.2026 au soir (decision d'Alberto : « brancher les droits
   sur les groupes Google »), L'ARBRE DES REFERENTIELS : chaque service
   actif de « Services - Responsables » qui porte un Groupe Google, et
   chaque pole actif de « Services - Poles » qui en porte un. Un membre
   direct du groupe d'un pole est membre de ce pole, de tous les poles
   dont il descend (libelle « Locaux > Intendance » sous « Locaux ») et du
   service ; un membre direct du groupe du service est membre du service.
   Seuls les groupes DECLARES dans l'arbre donnent un droit : un groupe
   imbrique pour la diffusion (equipe.operations@ dans les equipes de
   support, equipe.qualite@ et equipe.secretariat@ dans les groupes de
   profession) ne fait entrer personne dans le service qui l'accueille.
   Source « <groupe du service ou du pole> ». Les lignes de groupe tenues
   a la main (point 1) restent lues, pour un role particulier comme
   l'Administrateur des Operations.

5. Aux points 1 et 4, seuls les comptes personnels Almaval actifs recoivent
   une ligne (_compte_personnel) : les adresses hors du domaine (superviseurs
   externes membres d'encadrement@), les comptes suspendus et les comptes de
   service sont ecartes, et un alias est ramene a l'adresse principale, qui
   est celle qu'AlmaDesk voit a la connexion.

Pont : lieux_cycle avec le sujet « action:portail_droits_groupes confirmer ».
"""

import datetime
import zoneinfo

import main
import outils_annuaire
import outils_lieux

ID_GESTION = "19RFsMg0XxgqZz101L2zAAFeGC-oyTWBNN5YnmkZvRvE"
ID_LISTES = "116ly05SHkVj2sZXQxiFla4g8MDrRkOSQsmd-Cx3-ZVY"
ID_EFFECTIF = "1gqCyEB8D5tJDlHQN3DPc66yQ6WfUIt1E9O1ROGiN15c"
ONGLET_PERSONNES = "Registre - Personnes"
ONGLET = "Portail - Droits"
ONGLET_SAISIE = "Saisie - Collaborateurs"
ONGLET_SERVICES = "Services - Responsables"
ONGLET_DEPARTEMENTS = "Départements"
ONGLET_POLES = "Services - Pôles"
COLONNES = ["Adresse", "Nom", "Rôle", "Département", "Service", "Pôle", "Codes de responsable", "Écrans", "Groupe source", "Actif", "Remarque"]
ROLES = ("Super-administrateur", "Administrateur", "Responsable de département", "Responsable de service", "Membre")
PREFIXE_MIROIR = "Miroir"
PREFIXE_ANCIEN = "Membre de "
PREFIXE_PARTI = "N'est plus"
COMPTES_DE_SERVICE = {"rh@almaval.ch", "administration@almaval.ch", "gestion@almaval.ch", "contact@almaval.ch",
                      "formation@almaval.ch", "comptabilite@almaval.ch", "inventaire@almaval.ch", "logistique@almaval.ch",
                      "qualite@almaval.ch", "noreply@almaval.ch", "listecontacts@almaval.ch", "consulting@almaval.ch", "it@almaval.ch"}
ADMIN_PAR_DEFAUT = {"am.forte@almaval.ch", "gestion@almaval.ch"}
FUSEAU = zoneinfo.ZoneInfo("Europe/Zurich")


def _appeler(outil, **kwargs):
    fn = getattr(outil, "fn", outil)
    return fn(**kwargs)


def _s(v):
    return "" if v is None else str(v)


def _horodatage():
    return datetime.datetime.now(FUSEAU).strftime("%d.%m.%Y %H:%M")


def _lettre(index_1):
    return main._col_letter(index_1)


def _lire(spreadsheet_id, plage):
    lu = _appeler(main.get_values, spreadsheet_id=spreadsheet_id, range_a1=plage)
    if isinstance(lu, dict) and lu.get("erreur"):
        raise ValueError("lecture refusee (" + plage + ") : " + _s(lu.get("detail")))
    return lu.get("valeurs", []) if isinstance(lu, dict) else []


def _tableau(valeurs, ligne_entete=1):
    """Lignes cle par intitule, avec _ligne (numero dans l'onglet)."""
    if len(valeurs) < ligne_entete:
        return [], []
    entetes = [_s(e).strip() for e in valeurs[ligne_entete - 1]]
    lignes = []
    for i, brut in enumerate(valeurs[ligne_entete:], start=ligne_entete + 1):
        rangee = list(brut) + [""] * (len(entetes) - len(brut))
        obj = {e: rangee[j] for j, e in enumerate(entetes) if e}
        obj["_ligne"] = i
        lignes.append(obj)
    return entetes, lignes


def _actif(v):
    return _s(v).strip().lower() == "x"


def _lire_droits():
    entetes, lignes = _tableau(_lire(ID_GESTION, "'" + ONGLET + "'!A1:L400"))
    manquantes = [c for c in COLONNES if c not in entetes]
    if manquantes:
        raise ValueError("Portail - Droits n'est pas en version 2 (colonnes manquantes : " + ", ".join(manquantes) + ") : lancer d'abord adminPreparerDroits")
    return entetes, lignes


def _lire_departements():
    _, lignes = _tableau(_lire(ID_LISTES, "'" + ONGLET_DEPARTEMENTS + "'!A1:G30"))
    return [{"departement": _s(l.get("Département")).strip(), "responsable": _s(l.get("Responsable")).strip(),
             "initiales": _s(l.get("Initiales")).strip(), "adresse": _s(l.get("Adresse")).strip().lower()}
            for l in lignes if _s(l.get("Département")).strip() and _actif(l.get("Actif"))]


def _lire_services():
    _, lignes = _tableau(_lire(ID_LISTES, "'" + ONGLET_SERVICES + "'!A1:L80"))
    out = []
    for l in lignes:
        nom = _s(l.get("Service")).strip()
        if not nom or not _actif(l.get("Actif")):
            continue
        out.append({"service": nom, "responsable": _s(l.get("Responsable")).strip(), "initiales": _s(l.get("Initiales")).strip(),
                    "departement": _s(l.get("Département (gouvernance 2026)") or l.get("Département")).strip(),
                    "groupe": _s(l.get("Groupe Google")).strip().lower()})
    return out


def _lire_poles():
    """Services - Poles : une ligne par pole actif (Service, Pole, Departement, Groupe Google, Pole parent).

    Le parent d'un pole est la colonne « Pôle parent » si elle est remplie (cas d'un libelle garde court
    pour les postes et les affectations, comme « Intendance » sous « Locaux »), sinon ce qui precede le
    dernier « > » du libelle (« Locaux > Entretien » est sous « Locaux »), sinon le service.
    """
    _, lignes = _tableau(_lire(ID_LISTES, "'" + ONGLET_POLES + "'!A1:L200"))
    out = []
    for l in lignes:
        service, pole = _s(l.get("Service")).strip(), _s(l.get("Pôle")).strip()
        if not service or not pole or not _actif(l.get("Actif")):
            continue
        parent = _s(l.get("Pôle parent")).strip()
        if not parent and " > " in pole:
            parent = pole.rsplit(" > ", 1)[0].strip()
        out.append({"service": service, "pole": pole, "departement": _s(l.get("Département")).strip(),
                    "groupe": _s(l.get("Groupe Google")).strip().lower(), "parent": parent,
                    "segment": pole.rsplit(" > ", 1)[-1].strip()})
    return out


def _chaine_pole(pole, poles_du_service):
    """Les libelles du pole et de ses ancetres, du plus haut au pole lui-meme."""
    par_libelle = {p["pole"]: p for p in poles_du_service}
    chaine, vus, courant = [], set(), pole
    while courant and courant in par_libelle and courant not in vus:
        vus.add(courant)
        chaine.insert(0, courant)
        courant = par_libelle[courant]["parent"]
    return chaine


def _descendants(pole, poles_du_service):
    """Le pole et tous ceux dont il est un ancetre."""
    return [q["pole"] for q in poles_du_service if pole in _chaine_pole(q["pole"], poles_du_service)]


_DIRECTS = {}
_ANNUAIRE = {}
UNITES_DE_SERVICE = ("/comptes de service", "/liste contacts")


def _annuaire(rendu=None):
    """Comptes du domaine lus une seule fois par passage : adresse principale, alias, etat, unite."""
    if _ANNUAIRE:
        return _ANNUAIRE
    principaux, alias, jeton = {}, {}, None
    try:
        while True:
            rep = outils_annuaire._utilisateurs().users().list(domain="almaval.ch", maxResults=500, pageToken=jeton, projection="basic").execute()
            for u in rep.get("users", []):
                a = _s(u.get("primaryEmail")).strip().lower()
                if not a:
                    continue
                principaux[a] = {"suspendu": bool(u.get("suspended")), "unite": _s(u.get("orgUnitPath")).strip().lower()}
                for x in (u.get("aliases") or []) + (u.get("nonEditableAliases") or []):
                    alias[_s(x).strip().lower()] = a
            jeton = rep.get("nextPageToken")
            if not jeton:
                break
    except Exception as err:  # noqa: BLE001
        if rendu is not None:
            rendu["avertissements"].append("Annuaire illisible, filtre des comptes non appliqué : " + _s(err)[:120])
        _ANNUAIRE["ok"] = False
        return _ANNUAIRE
    _ANNUAIRE.update({"ok": True, "principaux": principaux, "alias": alias})
    return _ANNUAIRE


def _compte_personnel(adresse):
    """L'adresse principale d'un compte Almaval personnel et actif, sinon vide.

    Ecarte les adresses hors du domaine (superviseurs externes, par exemple), les comptes suspendus,
    les comptes de service (liste COMPTES_DE_SERVICE et unites Comptes de service ou Liste contacts),
    et ramene un alias a l'adresse principale, qui est celle que voit AlmaDesk a la connexion.
    """
    a = _s(adresse).strip().lower()
    if not a or not a.endswith("@almaval.ch"):
        return ""
    ann = _annuaire()
    if not ann.get("ok"):
        return "" if a in COMPTES_DE_SERVICE else a
    a = ann["alias"].get(a, a)
    fiche = ann["principaux"].get(a)
    if not fiche or fiche["suspendu"] or a in COMPTES_DE_SERVICE or fiche["unite"].startswith(UNITES_DE_SERVICE):
        return ""
    return a


def _utilisateurs_directs(groupe):
    """Les comptes membres DIRECTS d'un groupe (type USER, actifs), ramenes aux comptes personnels Almaval, voir _compte_personnel."""
    if groupe in _DIRECTS:
        return _DIRECTS[groupe]
    membres, jeton = [], None
    while True:
        rep = outils_annuaire._groupes().members().list(groupKey=groupe, maxResults=200, pageToken=jeton).execute()
        membres.extend(rep.get("members", []))
        jeton = rep.get("nextPageToken")
        if not jeton:
            break
    out = []
    for m in membres:
        a = _s(m.get("email")).strip().lower()
        if not a or _s(m.get("type")).upper() != "USER" or _s(m.get("status")).upper() not in ("", "ACTIVE"):
            continue
        a = _compte_personnel(a)
        if not a or a in out:
            continue
        out.append(a)
    _DIRECTS[groupe] = out
    return out


def _droits_par_arbre(services, poles, vouloir, rendu):
    """Source 4 : l'arbre Services - Responsables > Services - Poles, par leurs groupes Google."""
    _DIRECTS.clear()
    dep_service = {sv["service"]: sv["departement"] for sv in services}
    for sv in services:
        if not sv["groupe"] or "@" not in sv["groupe"]:
            continue
        les_poles = [p for p in poles if p["service"] == sv["service"] and p["groupe"] and "@" in p["groupe"]]
        try:
            membres_service = list(_utilisateurs_directs(sv["groupe"]))
        except Exception as err:  # noqa: BLE001
            rendu["avertissements"].append("Groupe du service " + sv["service"] + " illisible (" + sv["groupe"] + ") : " + _s(err)[:120])
            continue
        par_pole = {}
        for p in les_poles:
            try:
                par_pole[p["pole"]] = list(_utilisateurs_directs(p["groupe"]))
            except Exception as err:  # noqa: BLE001
                rendu["avertissements"].append("Groupe du pole " + sv["service"] + " > " + p["pole"] + " illisible (" + p["groupe"] + ") : " + _s(err)[:120])
                par_pole[p["pole"]] = []
        # Un pole compte aussi les membres de ses descendants (« Locaux » contient « Intendance » et « Locaux > Entretien »).
        membres_pole = {}
        for p in les_poles:
            tous = []
            for q in _descendants(p["pole"], les_poles):
                for a in par_pole.get(q, []):
                    if a not in tous:
                        tous.append(a)
            membres_pole[p["pole"]] = tous
        for tous in membres_pole.values():
            for a in tous:
                if a not in membres_service:
                    membres_service.append(a)
        departement = sv["departement"]
        for a in membres_service:
            vouloir(a, "Membre", departement, sv["service"], "", "", sv["groupe"])
        for p in les_poles:
            for a in membres_pole[p["pole"]]:
                vouloir(a, "Membre", departement or dep_service.get(p["service"], p["departement"]), sv["service"], p["pole"], "", p["groupe"])
        rendu["sources"]["Arbre : " + sv["service"]] = {"groupe": sv["groupe"], "membres": len(membres_service),
                                                         "poles": {p["pole"]: len(membres_pole[p["pole"]]) for p in les_poles}}


def _adresses_par_initiales():
    """Initiales -> adresse Almaval, lues dans Saisie - Collaborateurs (intitules en ligne 3)."""
    tetes = _lire(ID_GESTION, "'" + ONGLET_SAISIE + "'!A3:HZ3")
    entetes = [_s(e).strip() for e in (tetes[0] if tetes else [])]
    if "Initiales" not in entetes or "E-mail Almaval" not in entetes:
        raise ValueError("Saisie - Collaborateurs : colonnes Initiales ou E-mail Almaval introuvables en ligne 3")
    ci, ce = entetes.index("Initiales") + 1, entetes.index("E-mail Almaval") + 1
    init = _lire(ID_GESTION, "'" + ONGLET_SAISIE + "'!" + _lettre(ci) + "4:" + _lettre(ci) + "400")
    mails = _lire(ID_GESTION, "'" + ONGLET_SAISIE + "'!" + _lettre(ce) + "4:" + _lettre(ce) + "400")
    table = {}
    for k in range(max(len(init), len(mails))):
        i = _s(init[k][0]).strip() if k < len(init) and init[k] else ""
        m = _s(mails[k][0]).strip().lower() if k < len(mails) and mails[k] else ""
        if i and m and "@" in m and i not in table:
            table[i] = m
    return table


def _est_groupe(adresse):
    try:
        outils_annuaire._groupes().groups().get(groupKey=adresse).execute()
        return True
    except Exception:  # noqa: BLE001
        return False


def _membres_utilisateurs(groupe, profondeur=0, vus=None):
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
        a = _compte_personnel(a)
        if not a:
            continue
        adresses.append(a)
    resultat = []
    for a in adresses:
        if a not in resultat:
            resultat.append(a)
    return resultat


_NOMS = {}


def _noms_registre(table_initiales):
    """Nom d'etat civil et prenom d'usage (regle d'Alberto, rappelee le 28.09.2026), par initiales et par adresse Almaval.

    Registre - Personnes : Nom, Prenom d'usage (a defaut Prenom), E-mail ; les adresses Almaval viennent aussi
    de Saisie - Collaborateurs (table_initiales : initiales -> adresse).
    """
    _, lignes = _tableau(_lire(ID_EFFECTIF, "'" + ONGLET_PERSONNES + "'!A1:AZ800"))
    par_init, par_adresse = {}, {}
    for l in lignes:
        init, nom = _s(l.get("Initiales")).strip(), _s(l.get("Nom")).strip()
        if not init or not nom:
            continue
        n = (nom + " " + (_s(l.get("Prénom d'usage")).strip() or _s(l.get("Prénom")).strip())).strip()
        par_init[init] = n
        mail = _s(l.get("E-mail")).strip().lower()
        if mail.endswith("@almaval.ch"):
            par_adresse[mail] = n
    for init, mail in (table_initiales or {}).items():
        if init in par_init and mail not in par_adresse:
            par_adresse[mail] = par_init[init]
    return par_init, par_adresse


def _nom_complet(adresse):
    if adresse in _NOMS:
        return _NOMS[adresse]
    nom = adresse.split("@")[0]
    try:
        u = outils_annuaire._utilisateurs().users().get(userKey=adresse).execute()
        nom = _s((u.get("name") or {}).get("fullName")).strip() or nom
    except Exception:  # noqa: BLE001
        pass
    _NOMS[adresse] = nom
    return nom


def _cle(adresse, role, departement, service, pole):
    return "|".join([_s(adresse).strip().lower(), _s(role).strip(), _s(departement).strip(), _s(service).strip(), _s(pole).strip()])


def _est_miroir(remarque):
    r = _s(remarque).strip()
    return r.startswith(PREFIXE_MIROIR) or r.startswith(PREFIXE_ANCIEN) or r.startswith(PREFIXE_PARTI)


def passage_droits_groupes(confirmer=False):
    entetes, lignes = _lire_droits()
    col = {c: entetes.index(c) + 1 for c in COLONNES}
    quand = _horodatage()
    rendu = {"quand": quand, "confirmer": bool(confirmer), "sources": {}, "ajouts": [], "reactivations": [], "mises_a_jour": [], "departs": [], "inchangees": 0, "ecritures": 0, "avertissements": []}
    _ANNUAIRE.clear()
    _annuaire(rendu)

    # Les lignes en place, par cle.
    en_place = {}
    for l in lignes:
        a = _s(l.get("Adresse")).strip().lower()
        if not a:
            continue
        en_place.setdefault(_cle(a, l.get("Rôle"), l.get("Département"), l.get("Service"), l.get("Pôle")), l)

    # Ce que le passage veut voir en place : {cle: {colonnes...}}.
    voulues = {}

    def vouloir(adresse, role, departement, service, pole, ecrans, source, nom=""):
        if _s(adresse).strip().lower() in ADMIN_PAR_DEFAUT:
            return  # le super-administrateur tient tout par le code : aucune ligne miroir, il n'apparait pas dans l'organigramme des droits
        k = _cle(adresse, role, departement, service, pole)
        if k in voulues:
            return
        voulues[k] = {"Adresse": adresse, "Nom": nom, "Rôle": role, "Département": _s(departement).strip(), "Service": _s(service).strip(), "Pôle": _s(pole).strip(),
                      "Écrans": _s(ecrans).strip(), "Groupe source": source}

    # 1. Les lignes de groupe.
    groupes = []
    for l in lignes:
        a = _s(l.get("Adresse")).strip().lower()
        if not a or not _actif(l.get("Actif")) or a in ADMIN_PAR_DEFAUT or "@" not in a:
            continue
        if not _est_groupe(a):
            continue
        groupes.append(l)
    for g in groupes:
        adresse_groupe = _s(g.get("Adresse")).strip().lower()
        membres = _membres_utilisateurs(adresse_groupe)
        role = _s(g.get("Rôle")).strip() or "Membre"
        if role not in ROLES or role == "Super-administrateur":
            role = "Membre"
        rendu["sources"][adresse_groupe] = {"membres": len(membres), "role": role, "departement": _s(g.get("Département")), "service": _s(g.get("Service")), "pole": _s(g.get("Pôle"))}
        for a in membres:
            vouloir(a, role, g.get("Département"), g.get("Service"), g.get("Pôle"), g.get("Écrans"), adresse_groupe)

    # 2. Les responsables de departement.
    departements = _lire_departements()
    for d in departements:
        if not d["adresse"]:  # Fonction transversale comprise depuis le 28.09.2026 : son responsable est le responsable des operations
            continue
        vouloir(d["adresse"], "Responsable de département", d["departement"], "", "", "", "Listes : " + ONGLET_DEPARTEMENTS, d["responsable"])
    rendu["sources"]["Listes : " + ONGLET_DEPARTEMENTS] = {"departements": len(departements)}

    # 3. Les responsables de service.
    services = _lire_services()
    table = _adresses_par_initiales()
    for d in departements:  # l'onglet Departements porte aussi initiales -> adresse, en complement de Saisie - Collaborateurs
        if d["initiales"] and d["adresse"] and d["initiales"] not in table:
            table[d["initiales"]] = d["adresse"]
    sans_adresse = []
    for sv in services:
        if not sv["initiales"]:
            continue
        a = table.get(sv["initiales"], "")
        if not a:
            sans_adresse.append(sv["service"] + " (" + sv["initiales"] + ")")
            continue
        vouloir(a, "Responsable de service", sv["departement"], sv["service"], "", "", "Listes : " + ONGLET_SERVICES, sv["responsable"])
    rendu["sources"]["Listes : " + ONGLET_SERVICES] = {"services": len(services), "responsables_sans_adresse": sans_adresse}

    # 4. L'arbre des services et des poles, par leurs groupes Google.
    _droits_par_arbre(services, _lire_poles(), vouloir, rendu)
    if sans_adresse:
        rendu["avertissements"].append("Responsables sans adresse Almaval dans Saisie - Collaborateurs : " + ", ".join(sans_adresse))

    # Les noms : nom d'etat civil et prenom d'usage, lus au registre.
    try:
        _, noms_adresse = _noms_registre(table)
    except Exception as err:  # noqa: BLE001
        noms_adresse = {}
        rendu["avertissements"].append("Registre - Personnes illisible, noms laisses tels quels : " + _s(err)[:160])
    for v in voulues.values():
        n = noms_adresse.get(_s(v["Adresse"]).strip().lower())
        if n:
            v["Nom"] = n

    # Confrontation.
    ecritures = []  # (ligne, colonne, valeur)
    ajouts = []
    for k, v in voulues.items():
        existante = en_place.get(k)
        if existante is None:
            nom = v["Nom"] or _nom_complet(v["Adresse"])
            rangee = ["" for _ in entetes]
            rangee[col["Adresse"] - 1] = v["Adresse"]
            rangee[col["Nom"] - 1] = nom
            rangee[col["Rôle"] - 1] = v["Rôle"]
            rangee[col["Département"] - 1] = v["Département"]
            rangee[col["Service"] - 1] = v["Service"]
            rangee[col["Pôle"] - 1] = v["Pôle"]
            rangee[col["Codes de responsable"] - 1] = ""
            rangee[col["Écrans"] - 1] = v["Écrans"]
            rangee[col["Groupe source"] - 1] = v["Groupe source"]
            rangee[col["Actif"] - 1] = "x"
            rangee[col["Remarque"] - 1] = PREFIXE_MIROIR + " : " + v["Groupe source"] + ", le " + quand
            ajouts.append(rangee)
            rendu["ajouts"].append({"adresse": v["Adresse"], "role": v["Rôle"], "departement": v["Département"], "service": v["Service"], "source": v["Groupe source"]})
            continue
        remarque = _s(existante.get("Remarque")).strip()
        if not _est_miroir(remarque):
            rendu["inchangees"] += 1  # tenue a la main : elle prime
            continue
        changements = {}
        if not _actif(existante.get("Actif")):
            changements["Actif"] = "x"
        for c in ("Écrans", "Groupe source"):
            if _s(existante.get(c)).strip() != v[c]:
                changements[c] = v[c]
        if v["Nom"] and _s(existante.get("Nom")).strip() != v["Nom"]:
            changements["Nom"] = v["Nom"]
        if remarque.startswith(PREFIXE_PARTI) or remarque.startswith(PREFIXE_ANCIEN) or changements:
            changements["Remarque"] = PREFIXE_MIROIR + " : " + v["Groupe source"] + ", le " + quand
        if changements:
            for c, val in changements.items():
                ecritures.append((existante["_ligne"], col[c], val))
            (rendu["reactivations"] if remarque.startswith(PREFIXE_PARTI) else rendu["mises_a_jour"]).append({"adresse": v["Adresse"], "ligne": existante["_ligne"], "changements": changements})
        else:
            rendu["inchangees"] += 1

    # Les lignes miroir qui ne sont plus produites.
    for k, l in en_place.items():
        remarque = _s(l.get("Remarque")).strip()
        if k in voulues or not _est_miroir(remarque) or remarque.startswith(PREFIXE_PARTI):
            continue
        a = _s(l.get("Adresse")).strip().lower()
        if a in ADMIN_PAR_DEFAUT:
            continue
        source = _s(l.get("Groupe source")).strip() or remarque
        if _actif(l.get("Actif")):
            ecritures.append((l["_ligne"], col["Actif"], "-"))
        ecritures.append((l["_ligne"], col["Remarque"], PREFIXE_PARTI + " produit par " + source + " depuis le " + quand + ", miroir"))
        rendu["departs"].append({"adresse": a, "ligne": l["_ligne"], "role": _s(l.get("Rôle")), "service": _s(l.get("Service")), "source": source})

    rendu["ecritures"] = len(ecritures) + len(ajouts)
    if not confirmer:
        rendu["simulation"] = True
        return rendu
    for ligne, colonne, valeur in ecritures:
        rep = main._update_values(ID_GESTION, "'" + ONGLET + "'!" + _lettre(colonne) + str(ligne), [[valeur]], True)
        if isinstance(rep, dict) and rep.get("erreur"):
            raise ValueError("ecriture refusee en " + _lettre(colonne) + str(ligne) + " : " + _s(rep.get("detail")))
    if ajouts:
        rep = _appeler(main.append_rows, spreadsheet_id=ID_GESTION, range_a1="'" + ONGLET + "'!A1:" + _lettre(len(entetes)), values=ajouts)
        if isinstance(rep, dict) and rep.get("erreur"):
            raise ValueError("ajout refuse : " + _s(rep.get("detail")))
        rendu["plage_ajoutee"] = rep.get("updatedRange") if isinstance(rep, dict) else None
    # Relecture : chaque ligne voulue est en place et active.
    _, relu = _lire_droits()
    presentes = {}
    for l in relu:
        a = _s(l.get("Adresse")).strip().lower()
        if a:
            presentes.setdefault(_cle(a, l.get("Rôle"), l.get("Département"), l.get("Service"), l.get("Pôle")), l)
    manquantes = [k for k in voulues if k not in presentes or not _actif(presentes[k].get("Actif"))]
    rendu["relecture"] = {"lignes": len(relu), "voulues": len(voulues), "manquantes_ou_inactives": manquantes}
    rendu["ok"] = not manquantes
    return rendu


@main.mcp.tool()
@main.tolerant
def portail_droits_groupes(confirmer: bool = False):
    """Miroir de l'organigramme et des groupes Google dans Portail - Droits (AlmaDesk Admin) : une ligne par membre des groupes cites, par responsable de departement et par responsable de service ; simulation sans confirmer."""
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
