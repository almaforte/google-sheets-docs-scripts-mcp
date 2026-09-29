"""Annonce DSAS : retours des RH du 29.09.2026, greffés sur outils_zzzzz_onboarding_a_appairage_dsas.

Chargé juste après ce module (ordre alphabétique de bootstrap.py), il remplace
dans son espace de noms dsas_population et dsas_evolutions, et y ajoute les
aides de lecture des grilles. Règles posées par les RH et validées le
29.09.2026 :

  1. On déclare toute personne en formation rattachée à Vaud, psychologie
     clinique comprise : ORIENTATIONS_EXCLUES est vidé.
  2. Le rattachement est celui du contrat et suit les mutations : il se lit
     dans les régimes qui recouvrent le trimestre, à défaut dans
     l'engagement (Inan Nuriye, Vétois Matthieu).
  3. Une personne « En formation » à un moment du trimestre figure, même si
     elle est diplômée à la fin (Bober Anita) ; le passage du statut de
     formation à un autre statut donne « Fin d'encadrement au » la veille
     du régime suivant.
  4. Toute mutation de site se signale jour par jour, Genève compris
     (Vétois Matthieu) ; la colonne des lieux de pratique reste sans Genève.
  5. Une sortie s'écrit « Sortie et fin d'encadrement au ».
"""

import types

import outils_zzzzz_onboarding_a_appairage_dsas as _m

_m.DSAS["ORIENTATIONS_EXCLUES"] = []
_m.DSAS["SITES_EXCLUS"] = ["Genève", "Télétravail", "Non travaillé"]
_m.DSAS["SITES_HORS_MUTATION"] = ["Télétravail", "Non travaillé"]
_m._JOURS_NOMS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"]

# Les fonctions ci-dessous sont écrites ici puis réinstallées dans l'espace de
# noms du module d'origine, pour que dsas_calculer les appelle et qu'elles y
# trouvent DSAS, _s, dsas_date et les autres aides.
# ruff: noqa: F821


def dsas_regimes_du_trimestre(regs, q):
    """Les regimes qui recouvrent au moins un jour du trimestre."""
    out = []
    for r in regs or []:
        deb = dsas_date(r.get("Date de début du régime"))
        fin = dsas_date(r.get("Date de fin du régime"))
        if deb and dsas_j(deb) <= dsas_j(q["fin"]) and (not fin or dsas_j(fin) >= dsas_j(q["debut"])):
            out.append(r)
    return out


def dsas_grille(r):
    """Jour -> lieu d'un regime (matin, sinon apres-midi), hors teletravail et jours non travailles."""
    out = {}
    if not r:
        return out
    for k, nom in enumerate(_JOURS_NOMS):
        for j in (DSAS["JOURS"][2 * k], DSAS["JOURS"][2 * k + 1]):
            v = _s(r.get(j)).strip()
            if v and v not in DSAS["SITES_HORS_MUTATION"]:
                out[nom] = v
                break
    return out


def _liste_fr(mots):
    return mots[0] if len(mots) == 1 else ", ".join(mots[:-1]) + " et " + mots[-1]


def dsas_grille_texte(g):
    """« Crissier lundi, jeudi et vendredi, Morges mercredi »."""
    lieux = []
    for nom in _JOURS_NOMS:
        if nom in g and g[nom] not in lieux:
            lieux.append(g[nom])
    return ", ".join(l + " " + _liste_fr([n for n in _JOURS_NOMS if g.get(n) == l]) for l in lieux)


def dsas_population(q, donnees):
    par_ini, a_verifier, exclus_orientation = {}, 0, 0
    for e in donnees["engagements"]:
        ini = _s(e.get("Initiales")).strip()
        if not ini or ini in DSAS["INITIALES_EXCLUES"]:
            continue
        regs_q = dsas_regimes_du_trimestre(donnees["regimes"].get(ini, []), q)
        en_formation = "formation" in _s(e.get("Statut")).lower() \
            or any("formation" in _s(r.get("Statut")).lower() for r in regs_q)
        if not en_formation:
            continue
        prof = _s(e.get("Profession")).strip()
        if prof not in DSAS["FONCTIONS"]:
            continue
        deb = dsas_date(e.get("Date de début"))
        if not deb or dsas_j(deb) > dsas_j(q["fin"]):
            continue
        fin = dsas_date(e.get("Date de fin"))
        if fin and dsas_j(fin) < dsas_j(q["debut"]):
            continue
        # Canton de rattachement : celui des regimes du trimestre, qui suivent
        # les mutations ; a defaut, celui de l'engagement (29.09.2026).
        cantons = [_s(r.get("Canton d'exercice")).strip() for r in regs_q]
        cantons = [c for c in cantons if c and c != "-"]
        canton = DSAS["CANTON"] if DSAS["CANTON"] in cantons else (cantons[-1] if cantons
                                                                     else _s(e.get("Canton d'exercice")).strip())
        if canton != DSAS["CANTON"]:
            if not canton or canton == "-":
                a_verifier += 1
            continue
        p = donnees["personnes"].get(ini)
        if not p:
            a_verifier += 1
            continue
        aff = dsas_affectation(p, str(q["annee"]), donnees)
        if aff and _s(aff.get("Orientation")).strip() in DSAS["ORIENTATIONS_EXCLUES"]:
            exclus_orientation += 1
            continue
        x = par_ini.get(ini)
        if not x:
            par_ini[ini] = {"e": e, "p": p, "ini": ini, "prof": prof, "deb": deb, "fin": fin,
                            "nomPrenom": _s(e.get("Nom prénom") or p.get("Nom prénom")).strip()}
        else:
            if dsas_j(deb) < dsas_j(x["deb"]):
                x["deb"] = deb
            x["fin"] = None if (not fin or not x["fin"]) else (fin if dsas_j(fin) > dsas_j(x["fin"]) else x["fin"])
    return {"liste": list(par_ini.values()), "aVerifier": a_verifier, "exclusOrientation": exclus_orientation}


def dsas_evolutions(x, q, donnees, adresse_precedente, adresse_actuelle, nom_de):
    ev = []

    def dans_q(d):
        return bool(d) and dsas_j(q["debut"]) <= dsas_j(d) <= dsas_j(q["fin"])

    if dans_q(x["deb"]):
        ev.append([dsas_j(x["deb"]) - 0.5, "Entrée au " + dsas_fmt(x["deb"])])

    regs = donnees["regimes"].get(x["ini"], [])
    fin_par_statut = []
    for i in range(1, len(regs)):
        d = dsas_date(regs[i].get("Date de début du régime"))
        if not dans_q(d) or dsas_j(d) == dsas_j(x["deb"]):
            continue
        if x["fin"] and dsas_j(d) > dsas_j(x["fin"]):
            continue
        a, b = dsas_nombre(regs[i - 1].get("EPT total")), dsas_nombre(regs[i].get("EPT total"))
        if a is not None and b is not None and abs(a - b) > 1e-9:
            ev.append([dsas_j(d), "Changement de taux au " + dsas_fmt(d) + " (" + str(_js_round(a * 100)) + " % puis "
                       + str(_js_round(b * 100)) + " %)"])
        g0, g1 = dsas_grille(regs[i - 1]), dsas_grille(regs[i])
        if g0 and g1 and g0 != g1:
            ev.append([dsas_j(d), "Changement de site au " + dsas_fmt(d) + " : " + dsas_grille_texte(g1)
                       + " (auparavant " + dsas_grille_texte(g0) + ")"])
        st0, st1 = _s(regs[i - 1].get("Statut")).lower(), _s(regs[i].get("Statut")).lower()
        if "formation" in st0 and st1 and "formation" not in st1:
            veille = d - datetime.timedelta(days=1)
            fin_par_statut.append(dsas_j(veille))
            ev.append([dsas_j(veille), "Fin d'encadrement au " + dsas_fmt(veille)])

    # Encadrement, mois par mois, a partir du mois qui precede le trimestre.
    mois = []
    m0, a0 = q["mois"][0] - 1, q["annee"]
    if m0 < 0:
        m0, a0 = 11, q["annee"] - 1
    mois.append([a0, m0])
    for m in q["mois"]:
        mois.append([q["annee"], m])
    precedent = None
    for k, (an, mo) in enumerate(mois):
        debut_mois = _js_date(an, mo, 1)
        fin_mois = _js_date(an, mo + 1, 0)
        if dsas_j(fin_mois) < dsas_j(x["deb"]):
            precedent = None
            continue
        if x["fin"] and dsas_j(debut_mois) > dsas_j(x["fin"]):
            break
        cur = dsas_encadrant_du_mois(x["p"], str(an), mo, donnees)
        if cur is None:
            cur = precedent
        if k > 0 and dsas_j(debut_mois) > dsas_j(x["deb"]):
            sortie_ce_mois = bool(x["fin"]) and dsas_j(x["fin"]) <= dsas_j(fin_mois)
            if precedent and cur and precedent != cur:
                ev.append([dsas_j(debut_mois), "Changement d'encadrant au " + dsas_fmt(debut_mois) + " (" + nom_de(precedent)
                           + ", puis " + nom_de(cur) + ")"])
            elif precedent and not cur and not sortie_ce_mois and not fin_par_statut:
                veille = _js_date(an, mo, 0)
                ev.append([dsas_j(veille), "Fin d'encadrement au " + dsas_fmt(veille)])
        precedent = cur

    if adresse_precedente and adresse_actuelle and not dans_q(x["deb"]) \
            and dsas_norm(adresse_precedente) != dsas_norm(adresse_actuelle):
        ev.append([dsas_j(q["fin"]) - 0.2, "Changement d'adresse de domicile au cours du trimestre"])
    if dans_q(x["fin"]):
        ev.append([dsas_j(x["fin"]) + 0.5, "Sortie et fin d'encadrement au " + dsas_fmt(x["fin"])])
    ev.sort(key=lambda u: u[0])
    return [u[1] for u in ev]


for _f in (dsas_regimes_du_trimestre, dsas_grille, _liste_fr, dsas_grille_texte, dsas_population, dsas_evolutions):
    setattr(_m, _f.__name__, types.FunctionType(_f.__code__, _m.__dict__, _f.__name__, _f.__defaults__))
print("[dsas retours rh 29.09.2026] greffe posée", flush=True)
