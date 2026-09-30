"""Almaval - onboarding : lignes de rémunération posées après chaque report de mutation, 30.09.2026.

Décision d'Alberto du 30.09.2026 : la rémunération est désormais composite.
Les sept colonnes résumé de « Registre - Engagements » sont calculées depuis
l'onglet « Registre - Rémunérations » (une ligne par composante et par version).
Le moteur nocturne des mutations reporte les mutations au registre par ecr.objet,
qui saute les colonnes calculées : une hausse de salaire est donc marquée
« Appliquée » sans rien changer au registre des engagements.

Ce module d'extension intercepte le report d'une mutation, lit les valeurs
de rémunération, et pose ou clôt les lignes correspondantes dans
« Registre - Rémunérations » selon les règles de la spécification.
Il ne réécrit pas le moteur : il remplace sa fonction _appliquer_ligne_de_mutation_61
au chargement.
"""

import json
import re
import datetime

try:
    from outils_zzzzz_onboarding_0_socle import serial_de, date_de, maintenant, ligne_libre, ID_EFFECTIF, CFG_MUT, COL_MUTATIONS
    import outils_zzzzz_onboarding_6_mutations as _m6

    SIGNATURES = {
        "Salaire mensuel effectif": {
            "type_de_ligne": "Base", "objet": "Facturation propre", "finalite": "Production",
            "base_de_calcul": "Montant fixe mensuel", "ajustement": "", "destination": "Thérapies",
            "sens": "Almaval verse", "taux": "clinique", "unite_valeur": "montant"
        },
        "Dont salaire admin mensuel versé": {
            "type_de_ligne": "Base", "objet": "Fonction administrative", "finalite": "Soutien",
            "base_de_calcul": "Montant fixe mensuel", "ajustement": "", "destination": "Admin",
            "sens": "Almaval verse", "taux": "admin", "unite_valeur": "montant"
        },
        "Salaire horaire %": {
            "type_de_ligne": "Base", "objet": "Facturation propre", "finalite": "Production",
            "base_de_calcul": "Pourcentage du facturé propre", "ajustement": "", "destination": "Thérapies",
            "sens": "Almaval verse", "taux": "clinique", "unite_valeur": "fraction"
        },
        "Factoring": {
            "type_de_ligne": "Ajustement", "objet": "Facturation propre", "finalite": "Production",
            "base_de_calcul": "Pourcentage du facturé propre", "ajustement": "Factoring", "destination": "",
            "sens": "Almaval verse", "taux": None, "unite_valeur": "fraction"
        },
        "Contribution fixe mois": {
            "type_de_ligne": "Base", "objet": "Contribution aux services", "finalite": "",
            "base_de_calcul": "Montant fixe mensuel", "ajustement": "", "destination": "",
            "sens": "La personne verse", "taux": None, "unite_valeur": "montant"
        },
        "Commission sur assistants": {
            "type_de_ligne": "Base", "objet": "Encadrement d'assistants", "finalite": "Encadrement",
            "base_de_calcul": "Pourcentage du facturé des assistants encadrés", "ajustement": "", "destination": "",
            "sens": "Almaval verse", "taux": None, "unite_valeur": "fraction"
        }
    }

    def _convertir_nombre(v, est_fraction):
        if v is None or str(v).strip() == "":
            return None
        v_str = str(v).strip()
        v_clean = re.sub(r"[’'\s]", "", v_str).replace(",", ".")
        a_pourcent = "%" in v_clean
        v_clean = v_clean.replace("%", "")
        try:
            n = float(v_clean)
            if a_pourcent or (est_fraction and n > 1):
                n = n / 100
            return n
        except ValueError:
            return None

    def valeurs_de_la_mutation(ligne_mut):
        valeurs = {}
        texte_valeurs = str(ligne_mut.get(COL_MUTATIONS["VALEURS"]) or "")
        for ligne_texte in texte_valeurs.split("\n"):
            m = re.match(r"^(.+?) > (.+?) : (.*)$", ligne_texte)
            if m:
                onglet = m.group(1).strip()
                colonne = m.group(2).strip()
                valeur = m.group(3).strip()
                if onglet == "Registre - Engagements":
                    valeurs[colonne] = valeur
        
        colonnes_propres = {
            "Salaire mensuel effectif": "Nouveau salaire mensuel",
            "Dont salaire admin mensuel versé": "Dont salaire admin mensuel versé",
            "Salaire horaire %": "Salaire horaire %",
            "Factoring": "Factoring",
            "Contribution fixe mois": "Contribution fixe mois",
            "Commission sur assistants": "Commission sur assistants"
        }
        
        resultat = {}
        for comp, col_propre in colonnes_propres.items():
            v = valeurs.get(comp)
            if v is None or str(v).strip() == "":
                v = ligne_mut.get(col_propre)
            
            if v is None or str(v).strip() == "":
                continue
                
            v_str = str(v).strip().lower()
            if comp == "Factoring":
                if v_str in ("x", "oui"):
                    resultat[comp] = "x"
                elif v_str in ("-", "non", "0", "0.0", "0,0"):
                    resultat[comp] = 0
                else:
                    n = _convertir_nombre(v, True)
                    if n is not None:
                        resultat[comp] = n
            else:
                est_fraction = SIGNATURES[comp]["unite_valeur"] == "fraction"
                n = _convertir_nombre(v, est_fraction)
                if n is not None:
                    resultat[comp] = n
                    
        return resultat

    def reporter_lignes_de_remuneration(ecr, numero_mutation):
        bilan = {"cle": None, "date_effet": None, "composantes": [], "closes": 0, "creees": 0, "corrigees": 0, "anomalies": []}
        
        mutations = _m6._lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_MUTATIONS"])
        ligne_mut = next((l for l in mutations.lignes if l["_ligne"] == numero_mutation), None)
        if not ligne_mut:
            bilan["anomalies"].append("Mutation introuvable")
            return bilan
            
        cle_mut = _m6.cle_mutation_de(ligne_mut)
        cle_eng = str(ligne_mut.get(COL_MUTATIONS["CLE"]) or "").strip()
        bilan["cle"] = cle_eng
        
        d_effet_brut = _m6._date_ou_nulle(ligne_mut.get(COL_MUTATIONS["DATE"]))
        if not d_effet_brut:
            bilan["anomalies"].append("Pas de date d'effet")
            return bilan
        
        d_effet = datetime.datetime(d_effet_brut.year, d_effet_brut.month, d_effet_brut.day)
        bilan["date_effet"] = d_effet.strftime("%Y-%m-%d")
        
        valeurs = valeurs_de_la_mutation(ligne_mut)
        if not valeurs:
            return bilan
            
        engagements = _m6._lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_ENGAGEMENTS"])
        engagement = next((l for l in engagements.lignes if str(l.get("Clé engagement") or "").strip() == cle_eng), None)
        if not engagement:
            bilan["anomalies"].append("Engagement introuvable")
            return bilan
            
        ept_clinique = _m6._parse_float(str(engagement.get("EPT clinique") or "").replace(",", ".")) or 0.0
        ept_admin = _m6._parse_float(str(engagement.get("EPT admin") or "").replace(",", ".")) or 0.0
        entite_employeuse = str(engagement.get("Entité employeuse") or "").strip() or "Alma Valens Sàrl"
        
        remunerations = _m6._lire_onglet_de(ID_EFFECTIF, "Registre - Rémunérations")
        
        def correspond_signature(ligne, sig):
            def n(v): return str(v or "").strip().lower()
            return (n(ligne.get("Type de ligne")) == n(sig["type_de_ligne"]) and
                    n(ligne.get("Base de calcul")) == n(sig["base_de_calcul"]) and
                    n(ligne.get("Sens du flux de rémunération")) == n(sig["sens"]) and
                    n(ligne.get("Destination de l'EPT")) == n(sig["destination"]) and
                    n(ligne.get("Ajustement")) == n(sig["ajustement"]))
                    
        def est_en_vigueur(ligne, date_ref):
            d_debut = _m6._date_ou_nulle(ligne.get("Date de début"))
            d_fin = _m6._date_ou_nulle(ligne.get("Date de fin"))
            if d_debut and datetime.datetime(d_debut.year, d_debut.month, d_debut.day) > date_ref:
                return False
            if d_fin and datetime.datetime(d_fin.year, d_fin.month, d_fin.day) < date_ref:
                return False
            return True

        ordre_composantes = [
            "Dont salaire admin mensuel versé",
            "Salaire mensuel effectif",
            "Salaire horaire %",
            "Factoring",
            "Commission sur assistants",
            "Contribution fixe mois"
        ]
        
        # regle B2
        valeur_admin_recue = valeurs.get("Dont salaire admin mensuel versé")
        valeur_admin_vigueur = 0.0
        for l in remunerations.lignes:
            if str(l.get("Clé engagement") or "").strip() == cle_eng:
                if correspond_signature(l, SIGNATURES["Dont salaire admin mensuel versé"]):
                    if est_en_vigueur(l, d_effet):
                        v = _m6._parse_float(str(l.get("Valeur") or "").replace(",", "."))
                        if v is not None:
                            valeur_admin_vigueur = v
                            
        admin_a_utiliser = valeur_admin_recue if valeur_admin_recue is not None else valeur_admin_vigueur
        
        valeur_therapies_vigueur = 0.0
        for l in remunerations.lignes:
            if str(l.get("Clé engagement") or "").strip() == cle_eng:
                if correspond_signature(l, SIGNATURES["Salaire mensuel effectif"]):
                    if est_en_vigueur(l, d_effet):
                        v = _m6._parse_float(str(l.get("Valeur") or "").replace(",", "."))
                        if v is not None:
                            valeur_therapies_vigueur += v
                            
        if "Salaire mensuel effectif" in valeurs:
            total = valeurs["Salaire mensuel effectif"]
            valeurs["Salaire mensuel effectif"] = total - admin_a_utiliser
        elif "Dont salaire admin mensuel versé" in valeurs:
            valeurs["Salaire mensuel effectif"] = (valeur_therapies_vigueur + valeur_admin_vigueur) - admin_a_utiliser
            
        if "Factoring" in valeurs and valeurs["Factoring"] == "x":
            taux_factoring = 0.02
            params = _m6._lire_onglet_de(ID_EFFECTIF, "Paramètres - Rémunération")
            for l in params.lignes:
                if str(l.get("Paramètre") or "").strip() == "Taux de factoring":
                    v = _m6._parse_float(str(l.get("Valeur") or "").replace(",", "."))
                    if v is not None:
                        taux_factoring = v
                        break
            valeurs["Factoring"] = taux_factoring
            
        lignes_a_creer = []
        max_no_ligne = 0
        for l in remunerations.lignes:
            if str(l.get("Clé engagement") or "").strip() == cle_eng:
                no = _m6._parse_float(str(l.get("N° de ligne") or ""))
                if no is not None and no > max_no_ligne:
                    max_no_ligne = int(no)
                    
        for comp in ordre_composantes:
            if comp not in valeurs:
                continue
                
            v = valeurs[comp]
            if v is None or str(v).strip() == "":
                continue
                
            if comp == "Salaire mensuel effectif" and abs(v) < 0.0005:
                v = 0
                
            bilan["composantes"].append(comp)
            sig = SIGNATURES[comp]
            
            # regle C1
            candidates = []
            for l in remunerations.lignes:
                if str(l.get("Clé engagement") or "").strip() == cle_eng:
                    if correspond_signature(l, sig):
                        d_fin = _m6._date_ou_nulle(l.get("Date de fin"))
                        if not d_fin or datetime.datetime(d_fin.year, d_fin.month, d_fin.day) >= d_effet:
                            candidates.append(l)
                            
            en_vigueur = [l for l in candidates if est_en_vigueur(l, d_effet)]
            
            # regle C2
            if v == 0:
                for l in en_vigueur:
                    ecr.cellule(remunerations, l["_ligne"], "Date de fin", serial_de(d_effet - datetime.timedelta(days=1)))
                    notes = str(l.get("Notes") or "")
                    ecr.cellule(remunerations, l["_ligne"], "Notes", notes + f" | Close au {(d_effet - datetime.timedelta(days=1)).strftime('%d.%m.%Y')} par Moteur des mutations le {maintenant().strftime('%d.%m.%Y')} : mutation {cle_mut}")
                    bilan["closes"] += 1
                continue
                
            if comp == "Factoring":
                v = -abs(v)
                
            # regle C3
            deja_ok = False
            for l in en_vigueur:
                val_actuelle = _m6._parse_float(str(l.get("Valeur") or "").replace(",", "."))
                if val_actuelle is not None and abs(val_actuelle - v) < 0.0005:
                    deja_ok = True
                    break
            if deja_ok:
                continue
                
            # regle C4
            conflit_futur = False
            for l in candidates:
                d_debut = _m6._date_ou_nulle(l.get("Date de début"))
                if d_debut and datetime.datetime(d_debut.year, d_debut.month, d_debut.day) > d_effet:
                    ecr.cellule(remunerations, l["_ligne"], "Anomalie", f"Ligne future en conflit avec la mutation {cle_mut} du {d_effet.strftime('%d.%m.%Y')}")
                    bilan["anomalies"].append(f"Ligne future en conflit avec la mutation {cle_mut} du {d_effet.strftime('%d.%m.%Y')}")
                    conflit_futur = True
            if conflit_futur:
                continue
                
            # regle C5
            corrige_sur_place = False
            for l in en_vigueur:
                d_debut = _m6._date_ou_nulle(l.get("Date de début"))
                if d_debut and datetime.datetime(d_debut.year, d_debut.month, d_debut.day) == d_effet:
                    ancienne = str(l.get("Valeur") or "")
                    ecr.cellule(remunerations, l["_ligne"], "Valeur", v)
                    notes = str(l.get("Notes") or "")
                    ecr.cellule(remunerations, l["_ligne"], "Notes", notes + f" | Valeur corrigée de {ancienne} à {v} par Moteur des mutations le {maintenant().strftime('%d.%m.%Y')} : mutation {cle_mut}")
                    bilan["corrigees"] += 1
                    corrige_sur_place = True
            if corrige_sur_place:
                continue
                
            # regle C6
            nouveau_no_base = max_no_ligne + 1
            anciens_numeros = []
            for l in en_vigueur:
                ancienne = str(l.get("Valeur") or "")
                ancien_no = str(l.get("N° de ligne") or "")
                anciens_numeros.append(ancien_no)
                ecr.cellule(remunerations, l["_ligne"], "Date de fin", serial_de(d_effet - datetime.timedelta(days=1)))
                notes = str(l.get("Notes") or "")
                ecr.cellule(remunerations, l["_ligne"], "Notes", notes + f" | Close au {(d_effet - datetime.timedelta(days=1)).strftime('%d.%m.%Y')} par Moteur des mutations le {maintenant().strftime('%d.%m.%Y')} : mutation {cle_mut}, remplacée par la ligne {nouveau_no_base} à {v}")
                bilan["closes"] += 1
                
            max_no_ligne = nouveau_no_base
            
            nouvelle_ligne = {
                "Clé engagement": cle_eng,
                "N° de ligne": nouveau_no_base,
                "Type de ligne": sig["type_de_ligne"],
                "Base de calcul": sig["base_de_calcul"],
                "Ajustement": sig["ajustement"],
                "Destination de l'EPT": sig["destination"],
                "Sens du flux de rémunération": sig["sens"],
                "Valeur": v,
                "Date de début": serial_de(d_effet),
                "Pièce source": f"Mutation {cle_mut}",
                "Lien de la pièce": str(ligne_mut.get(COL_MUTATIONS["LIEN_AVENANT"]) or ""),
                "Saisi par": "Moteur des mutations",
                "Date de saisie": serial_de(maintenant()),
            }
            
            if en_vigueur:
                ref_l = en_vigueur[0]
                nouvelle_ligne["Objet de la ligne"] = str(ref_l.get("Objet de la ligne") or "")
                nouvelle_ligne["Finalité"] = str(ref_l.get("Finalité") or "")
                nouvelle_ligne["Type de prestation hors LAMal"] = str(ref_l.get("Type de prestation hors LAMal") or "")
                nouvelle_ligne["Entité Almaval"] = str(ref_l.get("Entité Almaval") or "")
                nouvelle_ligne["Taux d'EPT"] = _m6._parse_float(str(ref_l.get("Taux d'EPT") or "").replace(",", "."))
                nouvelle_ligne["Notes"] = f"Posée par Moteur des mutations le {maintenant().strftime('%d.%m.%Y')} depuis la mutation {cle_mut} ({str(ligne_mut.get(COL_MUTATIONS['TYPE']) or '')}), remplace {ancienne} (ligne {ancien_no})"
            else:
                objet_defaut = sig["objet"]
                if comp == "Contribution fixe mois":
                    obj_pers = None
                    for l in remunerations.lignes:
                        if str(l.get("Clé engagement") or "").strip() == cle_eng and est_en_vigueur(l, d_effet):
                            if str(l.get("Sens du flux de rémunération") or "").strip().lower() == "la personne verse":
                                obj_pers = str(l.get("Objet de la ligne") or "")
                                break
                    objet_defaut = obj_pers if obj_pers else "Contribution aux services"
                    
                nouvelle_ligne["Objet de la ligne"] = objet_defaut
                nouvelle_ligne["Finalité"] = sig["finalite"]
                nouvelle_ligne["Entité Almaval"] = entite_employeuse
                if sig["taux"] == "clinique":
                    nouvelle_ligne["Taux d'EPT"] = ept_clinique
                elif sig["taux"] == "admin":
                    nouvelle_ligne["Taux d'EPT"] = ept_admin
                nouvelle_ligne["Notes"] = f"Posée par Moteur des mutations le {maintenant().strftime('%d.%m.%Y')} depuis la mutation {cle_mut} ({str(ligne_mut.get(COL_MUTATIONS['TYPE']) or '')}), première ligne de la composante"
                
            if comp == "Factoring":
                base_no = None
                for l in remunerations.lignes:
                    if str(l.get("Clé engagement") or "").strip() == cle_eng and est_en_vigueur(l, d_effet):
                        if str(l.get("Base de calcul") or "").strip().lower() == "pourcentage du facturé propre" and str(l.get("Type de ligne") or "").strip().lower() == "base":
                            base_no = str(l.get("N° de ligne") or "")
                            break
                if base_no:
                    nouvelle_ligne["Rattachée à"] = base_no
                else:
                    bilan["anomalies"].append("Factoring sans base en pourcentage")
                    continue
                    
            lignes_a_creer.append(nouvelle_ligne)
            bilan["creees"] += 1
            
            # regle C7
            if comp == "Salaire horaire %" and anciens_numeros:
                for ancien_no in anciens_numeros:
                    for l in remunerations.lignes:
                        if str(l.get("Clé engagement") or "").strip() == cle_eng and est_en_vigueur(l, d_effet):
                            if str(l.get("Type de ligne") or "").strip().lower() == "ajustement" and str(l.get("Rattachée à") or "").strip() == ancien_no:
                                ecr.cellule(remunerations, l["_ligne"], "Date de fin", serial_de(d_effet - datetime.timedelta(days=1)))
                                notes = str(l.get("Notes") or "")
                                ecr.cellule(remunerations, l["_ligne"], "Notes", notes + f" | Close au {(d_effet - datetime.timedelta(days=1)).strftime('%d.%m.%Y')} par Moteur des mutations le {maintenant().strftime('%d.%m.%Y')} : mutation {cle_mut}")
                                bilan["closes"] += 1
                                
                                max_no_ligne += 1
                                ajust_ligne = {
                                    "Clé engagement": cle_eng,
                                    "N° de ligne": max_no_ligne,
                                    "Type de ligne": "Ajustement",
                                    "Rattachée à": nouveau_no_base,
                                    "Objet de la ligne": str(l.get("Objet de la ligne") or ""),
                                    "Finalité": str(l.get("Finalité") or ""),
                                    "Base de calcul": str(l.get("Base de calcul") or ""),
                                    "Ajustement": str(l.get("Ajustement") or ""),
                                    "Type de prestation hors LAMal": str(l.get("Type de prestation hors LAMal") or ""),
                                    "Valeur": _m6._parse_float(str(l.get("Valeur") or "").replace(",", ".")),
                                    "Destination de l'EPT": str(l.get("Destination de l'EPT") or ""),
                                    "Sens du flux de rémunération": str(l.get("Sens du flux de rémunération") or ""),
                                    "Entité Almaval": str(l.get("Entité Almaval") or ""),
                                    "Date de début": serial_de(d_effet),
                                    "Pièce source": str(l.get("Pièce source") or ""),
                                    "Lien de la pièce": str(l.get("Lien de la pièce") or ""),
                                    "Saisi par": str(l.get("Saisi par") or ""),
                                    "Date de saisie": str(l.get("Date de saisie") or ""),
                                    "Notes": f"Report de l'ajustement sur la nouvelle base, ligne {nouveau_no_base}"
                                }
                                lignes_a_creer.append(ajust_ligne)
                                bilan["creees"] += 1

        # regle C8
        if lignes_a_creer:
            derniere_cle = 2
            ligne_fin = 0
            for l in remunerations.lignes:
                if str(l.get("Clé engagement") or "").strip():
                    derniere_cle = max(derniere_cle, l["_ligne"])
                if str(l.get("Notes") or "").startswith("Ligne technique de fin de matrice"):
                    ligne_fin = l["_ligne"]
                    
            if ligne_fin == 0:
                ligne_fin = remunerations.derniere_ligne()
                
            ligne_cible = derniere_cle + 1
            lignes_libres = ligne_fin - ligne_cible
            
            if lignes_libres < len(lignes_a_creer):
                manquantes = len(lignes_a_creer) - lignes_libres
                if ecr.confirmer:
                    ecr.requetes_api(remunerations.id, remunerations.titre, [{
                        "insertDimension": {
                            "range": {
                                "sheetId": remunerations.sheet_id,
                                "dimension": "ROWS",
                                "startIndex": ligne_fin - 1,
                                "endIndex": ligne_fin - 1 + manquantes
                            },
                            "inheritFromBefore": True
                        }
                    }])
                    remunerations = _m6._lire_onglet_de(ID_EFFECTIF, "Registre - Rémunérations", rafraichir=True)
                    
            for i, nl in enumerate(lignes_a_creer):
                ligne_ecriture = ligne_cible + i
                for col, val in nl.items():
                    # Ne pas écrire dans Nom prénom, Unité, Indexation, En vigueur
                    if col not in ("Nom prénom", "Unité", "Indexation", "En vigueur"):
                        ecr.cellule(remunerations, ligne_ecriture, col, val)
                        
        return bilan

    _orig = _m6._appliquer_ligne_de_mutation_61

    def _avec_lignes(ecr, numero_mutation, regles):
        res = _orig(ecr, numero_mutation, regles)
        try:
            bilan = reporter_lignes_de_remuneration(ecr, numero_mutation)
            ecr.log("remuneration lignes : " + json.dumps(bilan, ensure_ascii=False, default=str))
        except Exception as err:
            ecr.log("remuneration lignes non posees pour la mutation " + str(numero_mutation) + " : " + str(err))
        return res

    _m6._appliquer_ligne_de_mutation_61 = _avec_lignes
    print("[onboarding remuneration] lignes de remuneration posees apres chaque report", flush=True)

except Exception as _exc:
    print("[onboarding remuneration] non posees : " + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)
