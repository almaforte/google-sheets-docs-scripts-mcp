"""Annonce DSAS : retours des RH du 29.09.2026, greffés sur outils_zzzzz_onboarding_a_appairage_dsas.

Chargé juste après ce module (ordre alphabétique de bootstrap.py), il remplace
dans son espace de noms dsas_population et dsas_evolutions, et y ajoute les
aides de lecture des grilles.

Instruction définitive, validée le 29.09.2026 à 19 h par la direction et les
RH, qui remplace le critère du canton de rattachement posé le même jour :

  1. Toute personne en formation de psychothérapie ou de psychiatrie, avec un
     EPT clinique supérieur à zéro et au moins un lieu de travail sur le
     canton de Vaud pendant le trimestre, figure au tableau. Le canton de
     rattachement du contrat ne compte plus.
  2. Le seul taux écrit au tableau est l'EPT présent dans le canton de Vaud :
     l'EPT clinique multiplié par la part des demi-journées travaillées sur un
     site vaudois (Genève hors Vaud ; télétravail et jours non travaillés hors
     du calcul). Sans grille, la liste « Lieux de travail » puis le canton
     d'exercice servent de repli.
  3. La psychologie clinique reste hors du tableau : la question est posée à
     la DSAS dans le courriel (ORIENTATIONS_EXCLUES = Clinique).
  4. Une personne « En formation » à un moment du trimestre figure, même si
     elle est diplômée à la fin ; le passage du statut de formation à un autre
     statut donne « Fin d'encadrement au » la veille du régime suivant.
  5. Toute mutation de site se signale jour par jour, Genève compris ; la
     colonne des lieux de pratique reste sans Genève. Un changement de taux
     s'entend de l'EPT présent dans le canton de Vaud.
  6. Une sortie s'écrit « Sortie et fin d'encadrement au ».
"""

import types

import outils_zzzzz_onboarding_a_appairage_dsas as _m

_m.DSAS["ORIENTATIONS_EXCLUES"] = ["Clinique"]
_m.DSAS["HORS_VAUD"] = ["Genève"]
_m.DSAS["SITES_EXCLUS"] = ["Genève", "Télétravail", "Non travaillé"]
_m.DSAS["SITES_HORS_MUTATION"] = ["Télétravail", "Non travaillé"]
_m._JOURS_NOMS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"]
# 29.09.2026, demande d'Alberto : le brouillon pour la DSAS ne porte plus
# am.forte@ en copie, seulement formation@.
_m.DSAS_COURRIELS["DSAS_COPIE"] = "formation@almaval.ch"

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


def _grille_brute(r):
    """Les douze demi-journees d'une ligne (regime ou engagement)."""
    return [_s(r.get(j)).strip() for j in DSAS["JOURS"]] if r else []


def dsas_part_vaud(r, e):
    """Part des demi-journees travaillees sur un site vaudois, entre 0 et 1.
    Grille du regime, sinon celle de l'engagement, sinon « Lieux de travail »,
    sinon le canton d'exercice."""
    for grille in (_grille_brute(r), _grille_brute(e)):
        phys = [v for v in grille if v and v not in DSAS["SITES_HORS_MUTATION"]]
        if phys:
            return sum(1 for v in phys if v not in DSAS["HORS_VAUD"]) / len(phys)
    lieux = [l.strip() for l in _s(e.get("Lieux de travail")).split(",") if l.strip()]
    lieux = [l for l in lieux if l not in DSAS["SITES_HORS_MUTATION"]]
    if lieux:
        return sum(1 for l in lieux if l not in DSAS["HORS_VAUD"]) / len(lieux)
    canton = _s((r or {}).get("Canton d'exercice")).strip() or _s(e.get("Canton d'exercice")).strip()
    return 1.0 if canton == DSAS["CANTON"] else 0.0


def dsas_ept_vaud(r, e):
    """EPT clinique present dans le canton de Vaud, arrondi au centieme."""
    clin = dsas_nombre((r or {}).get("EPT clinique")) if r else None
    if clin is None:
        clin = dsas_nombre(e.get("EPT clinique"))
    if clin is None:
        clin = dsas_nombre((r or {}).get("EPT total")) if r else dsas_nombre(e.get("EPT total"))
    if not clin:
        return 0.0
    return round(clin * dsas_part_vaud(r, e) + 1e-9, 2)


def dsas_population(q, donnees):
    par_ini, a_verifier, exclus_orientation = {}, 0, 0
    for e in donnees["engagements"]:
        ini = _s(e.get("Initiales")).strip()
        if not ini or ini in DSAS["INITIALES_EXCLUES"]:
            continue
        regs = donnees["regimes"].get(ini, [])
        regs_q = dsas_regimes_du_trimestre(regs, q)
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
        # Presence clinique dans le canton de Vaud pendant le trimestre.
        epts = [dsas_ept_vaud(r, e) for r in regs_q] if regs_q else [dsas_ept_vaud(None, e)]
        if max(epts) <= 0:
            continue
        p = donnees["personnes"].get(ini)
        if not p:
            a_verifier += 1
            continue
        aff = dsas_affectation(p, str(q["annee"]), donnees)
        if aff and _s(aff.get("Orientation")).strip() in DSAS["ORIENTATIONS_EXCLUES"]:
            exclus_orientation += 1
            continue
        # Taux du tableau : EPT present dans le canton de Vaud a la date de reference
        # (fin du trimestre ou sortie), sinon le dernier regime du trimestre present sur Vaud.
        ref = fin if fin and dsas_j(fin) < dsas_j(q["fin"]) else q["fin"]
        r_ref = dsas_regime_au(regs, ref)
        ept_ref = dsas_ept_vaud(r_ref, e) if (r_ref or not regs_q) else 0.0
        if ept_ref <= 0:
            ept_ref = next((v for v in reversed(epts) if v > 0), 0.0)
        e_vaud = dict(e)
        e_vaud["EPT total"] = ept_ref
        # Lieux de pratique : quand le regime de reference n'a pas de grille, la
        # grille de l'engagement passe avant « Lieux de travail », comme pour le taux
        # (cas d'un avenant qui ne nomme ni jours ni lieux, 29.09.2026).
        if not dsas_sites_du_regime(r_ref):
            sites_e = []
            for v in _grille_brute(e):
                if v and v not in DSAS["SITES_EXCLUS"] and v not in DSAS["SITES_HORS_MUTATION"] and v not in sites_e:
                    sites_e.append(v)
            if sites_e:
                e_vaud["Lieux de travail"] = ", ".join(sites_e)
        x = par_ini.get(ini)
        if not x:
            par_ini[ini] = {"e": e_vaud, "p": p, "ini": ini, "prof": prof, "deb": deb, "fin": fin,
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
        a, b = dsas_ept_vaud(regs[i - 1], x["e"]), dsas_ept_vaud(regs[i], x["e"])
        if a > 0 and b <= 0:
            veille = d - datetime.timedelta(days=1)
            ev.append([dsas_j(veille), "Fin d'activité dans le canton de Vaud au " + dsas_fmt(veille)])
        elif a <= 0 and b > 0:
            ev.append([dsas_j(d), "Début d'activité dans le canton de Vaud au " + dsas_fmt(d)])
        elif abs(a - b) > 1e-9:
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


# Courriel pour la DSAS, 29.09.2026 : le périmètre suit l'instruction définitive
# (lieu de travail dans le canton de Vaud, taux présent sur Vaud), et la question
# sur la psychologie clinique figure dans le brouillon tant que la DSAS n'y a pas
# répondu. QUESTION_CLINIQUE à False le jour où la réponse arrive.
_m.DSAS_COURRIELS["QUESTION_CLINIQUE"] = True
_corps_dsas_d_origine = _m.dsas_corps_dsas
_NOMBRES = {1: "Une", 2: "Deux", 3: "Trois", 4: "Quatre", 5: "Cinq", 6: "Six", 7: "Sept", 8: "Huit", 9: "Neuf", 10: "Dix"}


def _bloc_question_clinique(n):
    if not n or not _m.DSAS_COURRIELS.get("QUESTION_CLINIQUE"):
        return ""
    qui = ("Une personne de notre équipe suit" if n == 1
           else (_NOMBRES.get(n) or str(n)) + " de nos collaboratrices suivent")
    return ("<p><strong>Une question sur le périmètre</strong></p>"
            + "<p>" + qui + " une formation postgrade en psychologie clinique, et non en psychothérapie. "
            + "Sauf erreur de notre part, la "
            + _m.dsas_lien("https://www.fedlex.admin.ch/eli/cc/2012/268/fr", "loi sur les professions de la psychologie")
            + " distingue cinq domaines de titres postgrades fédéraux (art. 8), et seule la psychothérapie exercée "
            + "sous propre responsabilité professionnelle relève d'une autorisation cantonale (art. 22). "
            + "Votre modèle vise par ailleurs les psychothérapeutes assistant·e·s. La "
            + _m.dsas_lien("https://www.bag.admin.ch/fr/liste-des-filieres-de-formation-postgrade-accreditees",
                           "liste des filières de formation postgrade accréditées")
            + " permet de distinguer ces formations. Pourriez-vous s'il vous plaît nous indiquer si vous souhaitez "
            + "que ces personnes figurent aussi dans l'annonce trimestrielle ? Dans l'affirmative, nous les ajouterons "
            + "dès le prochain envoi.</p>")


def _corps_dsas(q, compte, url_tableau, dossier):
    html = _corps_dsas_d_origine(q, compte, url_tableau, dossier)
    html = html.replace(
        "personnes en formation rattachées au canton de Vaud et actives pendant le trimestre,",
        "personnes en formation qui ont exercé dans le canton de Vaud pendant le trimestre,")
    html = html.replace(
        "<li>Afin de vous offrir",
        "<li>Le taux indiqué est celui de l'activité exercée dans le canton de Vaud : pour une personne qui travaille "
        + "aussi sur notre site de Genève, seule la part vaudoise figure.</li><li>Afin de vous offrir", 1)
    bloc = _bloc_question_clinique(compte.get("exclusOrientation") or 0)
    if bloc:
        fin = "<p>Nous restons naturellement"
        html = html.replace(fin, bloc + fin, 1) if fin in html else html.replace("</div>", bloc + "</div>", 1)
    return html


_m.dsas_corps_dsas = _corps_dsas

for _f in (dsas_regimes_du_trimestre, dsas_grille, _liste_fr, dsas_grille_texte, _grille_brute, dsas_part_vaud,
           dsas_ept_vaud, dsas_population, dsas_evolutions):
    setattr(_m, _f.__name__, types.FunctionType(_f.__code__, _m.__dict__, _f.__name__, _f.__defaults__))
print("[dsas instruction définitive 29.09.2026] greffe posée", flush=True)
