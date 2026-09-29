"""Almaval - sorties : solde de vacances A LA DATE DE SORTIE, une seule source pour tous les ecrans, 29.09.2026.

Revision des taches 80, 90, 510 et 520 du module outils_zzzzz_onboarding_5b_sorties_taches,
chargee apres lui par l'ordre alphabetique des modules. Elle remplace, dans l'espace de
noms du module 5b, les fonctions _calculs_salaire, t080_solde_vacances, t090_heures,
t520_solde_vacances_versement, _corps_paie et executer_les_moteurs ; les lambdas du
registre MOTEURS et l'enveloppe greffee sur le module 5 les retrouvent par leur nom.

Pourquoi (constat du 29.09.2026, Juan Romero) : la tache 80 lisait le dernier mois pose
dans Mois - Temps (fin septembre, -5,43) alors que la sortie est au 31.10.2026, et ne
reecrivait jamais une valeur deja posee ; le montant du solde divisait le salaire mensuel
par 21,75 comme pour un plein temps alors que le solde est compte en jours de travail de
la personne ; une personne au salaire horaire recevait un montant alors que ses vacances
sont deja payees avec chaque salaire (supplement conges du contrat).

Ce que fait la revision :
  80  lit le solde au mois de la sortie dans BigQuery almaval_rh.v_conges_mois, la source
      unique de la BDU (Mois - Temps), d'AlmaDesk et de l'ADA (repli : Mois - Temps), avec
      sa decomposition cumulee ; ecrit la fiche « Solde de vacances a la sortie (jours) »
      des que la valeur change ; recalcule chaque nuit, meme Fait, jusqu'a un mois apres
      la sortie, tant que la tache n'est pas validee par les RH (marqueur « [validé »).
  520 montant = salaire mensuel effectif / (21,75 x EPT total) x jours ; Sans objet si le
      solde est nul (moins d'un vingtieme de jour) ou si la personne est au salaire horaire ; revue
      comme 80.
  510 le brouillon a la paie porte le solde a la date de sortie, la formule du jour de
      travail, et la phrase de cloture juste (versement, retenue, rien, salaire horaire).
  90  meme lecture qu'avant (dernier mois pose de Mois - Temps), mais sa remarque est
      remplacee au lieu d'etre empilee nuit apres nuit.
Un solde de moins d'un vingtieme de jour vaut zero : AlmaDesk l'affiche au dixieme de jour
(0,0 jour) et rien n'est verse ni retenu.
Les remarques du robot sur 80, 90 et 520 sont remplacees (jamais empilees) tant que la tache
n'est pas validee ; les parties ecrites par une personne sont gardees.
"""

import outils_zzzzz_onboarding_5b_sorties_taches as t5b

sorties = t5b.sorties
_s = t5b._s
_nombre = t5b._nombre
_nombre_js = t5b._nombre_js
_fr = t5b._fr
_chf = t5b._chf
_jour_texte = t5b._jour_texte
_tache = t5b._tache
_poser = t5b._poser
_echapper = t5b._echapper
COL = t5b.COL
CFG = t5b.CFG
meme_texte = t5b.meme_texte
en_jour = t5b.en_jour

RECALCULEES = (80, 520)
JOURS_DE_RECALCUL_APRES_SORTIE = 31
MARQUEUR_VALIDATION = "[validé"
PREFIXES_ROBOT = {
    80: ("Solde de vacances", "Aucun mois posé"),
    90: ("BDU Mois - Temps", "Aucun mois posé"),
    520: ("Solde de vacances", "Solde négatif", "Montant à verser", "Salaire horaire"),
}
SEUIL_JOURS_NUL = 0.05


# ------------------------------------------------ revision d'une tache deja reglee

def _validee(t):
    return t is not None and MARQUEUR_VALIDATION in _s(t.get("remarque"))


def _reviser_tache(sortie, ordre, etat, remarque):
    """Remplace la remarque du robot d'une tache deja reglee (marquer_taches ne touche jamais une
    tache Fait ou Sans objet) et fait passer l'etat entre En cours, Fait et Sans objet. Les parties
    humaines de la remarque sont gardees ; une tache validee n'est jamais touchee."""
    ctx = sortie.ctx
    suivi = ctx.suivi()
    col = sorties.COL_SUIVI
    touchees = 0
    for l in suivi.lignes:
        if _nombre_js(l.get(col["ORDRE"])) != ordre:
            continue
        if not sorties._ligne_de_cette_sortie(l, col["INITIALES"], sortie.cle, sortie.init):
            continue
        ancienne = _s(l.get(col["REMARQUE"])).strip()
        if MARQUEUR_VALIDATION in ancienne:
            continue
        prefixes = PREFIXES_ROBOT.get(ordre, ())
        humaines = [p.strip() for p in ancienne.split(" | ") if p.strip() and not p.strip().startswith(prefixes)]
        nouvelle = " | ".join(humaines + ([remarque] if remarque else []))
        objet = {}
        if nouvelle != ancienne:
            objet[col["REMARQUE"]] = nouvelle
        actuel = _s(l.get(col["ETAT"])).strip()
        if etat and etat != actuel and {etat, actuel} <= {"En cours", "Sans objet", "Fait"}:
            objet[col["ETAT"]] = etat
            if etat in ("Fait", "Sans objet") and actuel == "En cours":
                objet[col["FAIT_LE"]] = sorties.serial_de(sorties.maintenant())
                objet[col["FAIT_PAR"]] = sorties.SORTIE67["FAIT_PAR"]
        if objet:
            sorties._poser_objet(ctx, suivi, l, l["_ligne"], objet)
            touchees += 1
    return touchees


def _poser_ou_reviser(sortie, ordre, etat, remarque):
    """Une tache deja entamee (En cours, Fait, Sans objet) voit la remarque du robot remplacee ;
    une tache pas encore entamee passe par marquer_taches du module 5, comme avant."""
    t = _tache(sortie, ordre)
    if t is not None and t["etat"] in ("En cours", "Fait", "Sans objet"):
        return _reviser_tache(sortie, ordre, etat, remarque)
    return _poser(sortie, ordre, etat, remarque)


# ------------------------------------------------ le solde a la date de sortie

def _solde_a_la_sortie(sortie):
    """Le solde au mois de la sortie, lu dans BigQuery almaval_rh.v_conges_mois (repli : Mois - Temps),
    avec sa decomposition cumulee depuis le premier mois compte."""
    def lire():
        if not sortie.date_sortie:
            return None
        mois = sortie.date_sortie.strftime("%Y%m")
        try:
            import outils_bigquery
            rep = t5b._appeler(outils_bigquery.bq_requete, project_id=t5b.PROJET_BQ, localisation="europe-west6", limite=400, sql=(
                "SELECT periode, acquis, IFNULL(formation_acquise, 0) formation_acquise, vacances_prises, formation_prise, "
                "IFNULL(formation_imputee_sur_vacances, formation_prise) formation_imputee, ajustements, solde_fin_de_mois, "
                "IFNULL(demandes_en_attente, 0) demandes_en_attente "
                "FROM `gestion-almaval.almaval_rh.v_conges_mois` WHERE initiales = '" + _s(sortie.init).replace("'", "") + "' "
                "AND periode <= '" + mois + "' ORDER BY periode"))
            lignes = rep.get("resultats") or []
            if lignes:
                def somme(k):
                    return round(sum(_nombre(x.get(k)) for x in lignes), 2)
                derniere = lignes[-1]
                return {"source": "BigQuery v_conges_mois", "periode": _s(derniere.get("periode")),
                        "solde": round(_nombre(derniere.get("solde_fin_de_mois")), 2),
                        "acquis": somme("acquis"), "formation_contrat": somme("formation_acquise"),
                        "vacances": somme("vacances_prises"), "formation": somme("formation_prise"),
                        "formation_imputee": somme("formation_imputee"), "ajustements": somme("ajustements"),
                        "attente": somme("demandes_en_attente"), "depuis": _s(lignes[0].get("periode"))}
        except Exception:  # noqa: BLE001
            pass
        candidats = [l for l in sortie.mois_temps() if _s(l.get("Période")) <= mois]
        if not candidats:
            return None
        m = candidats[-1]
        return {"source": "BDU Mois - Temps", "periode": _s(m.get("Période")), "solde": round(_nombre(m.get("Solde de vacances")), 2)}
    return sortie.memo("solde_sortie", lire)


def _au_salaire_horaire(sortie):
    e = sortie.engagement
    return meme_texte(e.get("Forme de la contrepartie"), "Salaire horaire") or meme_texte(e.get("Rémunération"), "Horaire")


def _decomposition(s):
    if not s or s.get("source") != "BigQuery v_conges_mois":
        return ""
    depuis = s.get("depuis") or ""
    t = ("vacances acquises " + _fr(s["acquis"]) + " j depuis " + depuis[4:] + "." + depuis[:4]
         + ", vacances prises " + _fr(s["vacances"]) + " j")
    if s["formation"] or s["formation_contrat"]:
        if s["formation_contrat"]:
            t += (", formation prise " + _fr(s["formation"]) + " j, dont " + _fr(s["formation_imputee"])
                  + " j au-delà des journées de formation du contrat, imputés sur les vacances")
        else:
            t += ", formation prise " + _fr(s["formation"]) + " j, imputée sur les vacances (Conditions générales ch. 5)"
    if s["ajustements"]:
        t += ", ajustements " + _fr(s["ajustements"]) + " j"
    if s.get("attente"):
        t += " ; " + _fr(s["attente"]) + " j demandés et pas encore acceptés, non comptés"
    return t


# ------------------------------------------------ les calculs partages (80, 90, 120, 510, 520)

_calculs_d_origine = t5b._calculs_salaire


def _calculs_salaire(sortie):
    def calc():
        r = dict(_calculs_d_origine(sortie))
        e = sortie.engagement
        s = _solde_a_la_sortie(sortie)
        r["solde"] = s
        # « periode » reste le dernier mois pose (lu par 90 pour les heures) ; le solde a sa propre periode.
        r["periode_solde"] = s["periode"] if s else r.get("periode")
        if s:
            r["solde_vacances"] = s["solde"]
        ept = _nombre(e.get("EPT total"))
        r["ept"] = ept if 0 < ept <= 1.5 else 1.0
        r["horaire"] = _au_salaire_horaire(sortie)
        mensuel = r.get("mensuel") or 0.0
        # Le solde est compte en jours de travail de la personne (cinq semaines a 40 % = dix jours) :
        # un de ses jours vaut le salaire mensuel effectif / (21,75 x EPT total).
        r["journalier"] = round(mensuel / (t5b.JOURS_OUVRES_PAR_MOIS * r["ept"]), 2) if mensuel else 0.0
        solde = r.get("solde_vacances") or 0.0
        r["solde_nul"] = abs(solde) < SEUIL_JOURS_NUL
        r["montant_vacances"] = 0.0 if (r["horaire"] or r["solde_nul"]) else round(r["journalier"] * solde, 2)
        return r
    return sortie.memo("calculs_solde_sortie", calc)


# ------------------------------------------------ 80, 520 et le corps du brouillon 510

def t080_solde_vacances(sortie):
    c = _calculs_salaire(sortie)
    if c.get("solde_vacances") is None:
        return _poser_ou_reviser(sortie, 80, "", "Aucun mois posé dans BDU Mois - Temps pour " + sortie.cle + " : solde à calculer à la main")
    if _validee(_tache(sortie, 80)):
        return 0
    saisie = sortie.ctx.saisie()
    actuel = _s(sortie.ligne.get(COL["SOLDE_VACANCES"])).strip()
    if saisie.existe(COL["SOLDE_VACANCES"]) and (actuel == "" or abs(_nombre(actuel) - c["solde_vacances"]) >= 0.005):
        sorties._poser_objet(sortie.ctx, saisie, sortie.ligne, sortie.ligne["_ligne"], {COL["SOLDE_VACANCES"]: c["solde_vacances"]})
    s = c.get("solde") or {}
    texte_ = ("Solde de vacances à la sortie le " + _jour_texte(sortie.date_sortie) + " : " + _fr(c["solde_vacances"], 2) + " jour(s) ("
              + s.get("source", "BDU") + ", période " + _s(c.get("periode_solde")) + ")")
    d = _decomposition(s)
    if d:
        texte_ += " = " + d
    if c["horaire"]:
        texte_ += " ; salaire horaire : vacances déjà payées avec chaque salaire (supplément congés du contrat), aucun solde à verser ni à retenir"
    texte_ += " ; écrit dans la fiche (colonne « " + COL["SOLDE_VACANCES"] + " »), recalculé chaque nuit jusqu'à validation"
    return _poser_ou_reviser(sortie, 80, "Fait", texte_)


def t520_solde_vacances_versement(sortie):
    c = _calculs_salaire(sortie)
    if _validee(_tache(sortie, 520)):
        return 0
    if c.get("solde_vacances") is None:
        return _poser_ou_reviser(sortie, 520, "", "Solde de vacances inconnu (aucun mois posé dans la BDU)")
    jour = _chf(c["journalier"]) + " par jour de travail, soit " + _chf(c.get("mensuel") or 0) + " / (21,75 x " + _fr(c["ept"], 2) + ")"
    if c["horaire"]:
        return _poser_ou_reviser(sortie, 520, "Sans objet", "Salaire horaire : vacances payées avec chaque salaire (supplément congés du contrat), "
                                 "aucun solde à verser ni à retenir ; solde indicatif " + _fr(c["solde_vacances"]) + " jour(s)")
    if c["solde_nul"]:
        return _poser_ou_reviser(sortie, 520, "Sans objet", "Solde de vacances à la sortie de " + _fr(c["solde_vacances"]) + " jour(s), "
                                 "soit 0,0 jour au dixième de jour : rien à verser ni à retenir")
    if c["solde_vacances"] < 0:
        return _poser_ou_reviser(sortie, 520, "En cours", "Solde négatif de " + _fr(c["solde_vacances"]) + " jour(s), vacances prises en avance : retenue de "
                                 + _chf(-c["montant_vacances"]) + " (" + jour + ") à arbitrer, inscrite dans le brouillon à la paie (tâche 510)")
    return _poser_ou_reviser(sortie, 520, "En cours", "Montant à verser : " + _chf(c["montant_vacances"]) + " (" + _fr(c["solde_vacances"])
                             + " j x " + jour + "), inscrit dans le brouillon à la paie (tâche 510)")


def _texte_solde_paie(sortie, c):
    if c.get("solde_vacances") is None:
        return "à confirmer"
    base = _fr(c["solde_vacances"]) + " jour(s) au " + _jour_texte(sortie.date_sortie)
    if c["horaire"]:
        return base + ", vacances payées avec chaque salaire horaire (supplément congés du contrat) : aucun montant à verser ni à retenir"
    if c["solde_nul"]:
        return base + ", soit 0,0 jour au dixième de jour : aucun montant à verser ni à retenir"
    return (base + ", soit " + _chf(abs(c["montant_vacances"])) + (" à verser" if c["montant_vacances"] > 0 else " à retenir, vacances prises en avance")
            + " (" + _chf(c["journalier"]) + " par jour de travail = " + _chf(c.get("mensuel") or 0) + " / (21,75 x " + _fr(c["ept"], 2) + "))")


def _phrase_de_cloture(c):
    if c.get("solde_vacances") is None:
        return "en tenant compte du solde de vacances que nous vous confirmerons"
    if c["horaire"]:
        return "sans solde de vacances, les vacances étant payées avec chaque salaire horaire"
    if c["solde_nul"]:
        return "sans solde de vacances à verser ni à retenir"
    if c["montant_vacances"] > 0:
        return "avec le versement du solde de vacances"
    return "avec la retenue des vacances prises en avance"


def _corps_paie(sortie, c):
    p = sortie.personne()
    lignes = [
        ("Collaborateur", sortie.nom_prenom),
        ("Numéro de paie", _s(p.get("N° paie")) or "à compléter"),
        ("Date d'entrée", en_jour(sortie.engagement.get("Date de début"))),
        ("Date de sortie", _jour_texte(sortie.date_sortie)),
        ("Dernier jour travaillé", en_jour(sortie.ligne.get(COL["DERNIER_JOUR"])) or _jour_texte(sortie.date_sortie)),
        ("Libéré de l'obligation de travailler", _s(sortie.ligne.get(COL["LIBERE"])) or "non renseigné"),
        ("Motif", _s(sortie.ligne.get(COL["TYPE_FIN"])) or _s(sortie.ligne.get(COL["MOTIF_SORTIE"])) or "non renseigné"),
        ("Salaire mensuel effectif", _chf(c.get("mensuel") or 0) + (" (salaire horaire, moyenne indicative)" if c["horaire"] else "")),
        ("Dernier salaire", _chf(c.get("dernier_salaire") or 0) + ("" if c.get("dernier_mois_complet") else ", prorata")),
        ("Prorata du treizième", _chf(c.get("treizieme") or 0) if c.get("treizieme") else "sans objet"),
        ("Solde de vacances", _texte_solde_paie(sortie, c)),
        ("Heures à solder", (_fr((c.get("heures_sup") or 0) + (c.get("rattrapage") or 0)) + " h") if c.get("heures_sup") is not None else "à confirmer"),
        ("Éléments de paie signalés", c.get("elements_paie") or "aucun"),
    ]
    tableau = "".join("<tr><td>" + _echapper(k) + "</td><td>" + _echapper(v) + "</td></tr>" for k, v in lignes)
    return ("<p>Bonjour " + _echapper(CFG["NOM_PAIE"]) + ",</p>"
            "<p>Nous vous annonçons la sortie de " + _echapper(sortie.nom_prenom) + " au " + _jour_texte(sortie.date_sortie)
            + ". Voici les éléments du dernier décompte.</p>"
            "<p><strong>Éléments du dernier décompte</strong></p><table>" + tableau + "</table>"
            "<p>Merci d'établir le dernier décompte de salaire " + _phrase_de_cloture(c)
            + " et de nous transmettre la fiche finale ainsi que le certificat de salaire.</p>")


def t090_heures(sortie):
    """Comme le module 5b (dernier mois pose de Mois - Temps), la remarque etant remplacee et non empilee."""
    c = _calculs_salaire(sortie)
    if c.get("heures_sup") is None:
        return _poser_ou_reviser(sortie, 90, "", "Aucun mois posé dans BDU Mois - Temps pour " + sortie.cle)
    if _validee(_tache(sortie, 90)):
        return 0
    total = (c["heures_sup"] or 0.0) + (c["rattrapage"] or 0.0)
    saisie = sortie.ctx.saisie()
    ecrit = ""
    if total and saisie.existe(COL["HEURES_SOLDE"]) and _s(sortie.ligne.get(COL["HEURES_SOLDE"])).strip() == "":
        sorties._poser_objet(sortie.ctx, saisie, sortie.ligne, sortie.ligne["_ligne"], {COL["HEURES_SOLDE"]: round(total, 2)})
        ecrit = " ; « " + COL["HEURES_SOLDE"] + " » = " + _fr(total) + " h écrit dans la fiche"
    return _poser_ou_reviser(sortie, 90, "En cours", "BDU Mois - Temps, période " + _s(c.get("periode")) + " : heures supplémentaires "
                             + _fr(c["heures_sup"]) + " h, rattrapage " + _fr(c["rattrapage"]) + " h, écart de pointage cumulé sur l'année "
                             + _fr(c["ecart_pointage"]) + " h" + ecrit + " ; l'arbitrage (heures à payer, à compenser ou négatives) reste humain, à inscrire dans « "
                             + COL["HEURES_SOLDE"] + " »" + (" ; éléments de paie : " + c["elements_paie"] if c.get("elements_paie") else ""))


# ------------------------------------------------ le crochet : 80 et 520 revues meme reglees

def executer_les_moteurs(ctx, ligne, cle, initiales, engagement):
    """Comme le crochet du module 5b, mais 80 et 520 sont revues chaque nuit meme Fait ou Sans
    objet, jusqu'a un mois apres la sortie, tant qu'elles ne sont pas validees par les RH."""
    sortie = t5b._Sortie(ctx, ligne, cle, initiales, engagement)
    rendu = {}
    if not sortie.date_sortie:
        return rendu
    dest, jours, regles = t5b._destinataires(ctx)
    for ordre, (quand, moteur) in t5b.MOTEURS.items():
        t = _tache(sortie, ordre)
        if t is None:
            continue
        if t["etat"] in ("Fait", "Sans objet"):
            j = sortie.jours_depuis_sortie()
            if ordre not in RECALCULEES or _validee(t) or (j is not None and j > JOURS_DE_RECALCUL_APRES_SORTIE):
                continue
        if not sortie.moment_venu(quand, jours.get(str(ordre), 0)):
            continue
        regle = regles.get(str(ordre), "")
        if regle:
            verdict, _lecture = sorties.evaluer_condition(regle, ligne, engagement)
            if verdict != "oui":
                rendu[str(ordre)] = {"etat": t["etat"], "touchee": False, "attente": "condition " + (verdict or "sans verdict")}
                continue
        try:
            n = moteur(sortie, dest.get(str(ordre), ""))
            apres = _tache(sortie, ordre) or {}
            rendu[str(ordre)] = {"etat": apres.get("etat", ""), "touchee": bool(n)}
        except Exception as exc:  # noqa: BLE001
            rendu[str(ordre)] = {"erreur": str(exc)[:200]}
            try:
                _poser(sortie, ordre, "", "Moteur en échec : " + str(exc)[:160])
            except Exception:  # noqa: BLE001
                pass
    return rendu


def _installer():
    if getattr(t5b, "_revision_solde_sortie", False):
        return
    t5b._calculs_salaire = _calculs_salaire
    t5b.t080_solde_vacances = t080_solde_vacances
    t5b.t520_solde_vacances_versement = t520_solde_vacances_versement
    t5b.t090_heures = t090_heures
    t5b._corps_paie = _corps_paie
    t5b.executer_les_moteurs = executer_les_moteurs
    t5b._revision_solde_sortie = True


_installer()
