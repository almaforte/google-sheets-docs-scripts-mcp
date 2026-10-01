"""Axes thérapeutiques : source unique et contrôle des divergences, 01.10.2026.

Décision d'Alberto du 01.10.2026 : à l'entrée, la source est la saisie d'onboarding ;
ensuite la référence est le Registre - Profil clinique, et Places disponibles en est la copie ;
la valeur « Clinique » vaut « Intégrative ». Le module comble les trous et les équivalences,
sans jamais écraser une valeur différente : un vrai conflit est seulement signalé.

Règles, dans cet ordre, pour chacun des trois champs Axe thérapie 1, Axe thérapie 2, Axe thérapie complémentaire :
e1. une valeur « Clinique » du profil ou de Places disponibles devient « Intégrative » ;
e2. profil vide et saisie d'onboarding remplie (Axe thérapie 1 seulement) : le profil prend la saisie ;
e3. profil vide et Places disponibles remplie : le profil prend Places disponibles ;
e4. Places disponibles vide et profil rempli : Places disponibles prend le profil ;
e5. profil et Places disponibles remplis et différents : aucune écriture, conflit signalé ;
e6. Axe thérapie 1 du profil différent de la saisie : aucune écriture, écart signalé ;
e7. personne de Places disponibles sans ligne au profil : sa ligne est créée, reprise de Places disponibles par intitulé, Axe thérapie 1 depuis la saisie s'il manque, au plus 10 par passage.
Une écriture ne remplace jamais qu'une cellule vide ou une valeur « Clinique » ; une cellule « - » n'est jamais écrite. Au plus 25 écritures par passage.

Outil : axes_controle(confirmer). Pont : lieux_cycle avec le sujet « action:axes [confirmer] ».
"""

from main import mcp, tolerant

import outils_lieux
import outils_zzzzz_onboarding_0_socle as socle
import outils_zzzzzz_places_membres as pm
from outils_zzzzz_onboarding_0_socle import ID_EFFECTIF, _verrou, maintenant, pont_de_fond, texte

AXES = {
    "CHAMPS": ["Axe thérapie 1", "Axe thérapie 2", "Axe thérapie complémentaire"],
    "EQUIVALENTS": {"clinique": "Intégrative"},
    "ONGLET_PROFIL": "Registre - Profil clinique",
    "ONGLET_SAISIE": "Saisie - Collaborateurs",
    "PLAFOND_ECRITURES": 25,
    "PLAFOND_PROFILS": 10,
    "SOURCE_PROFIL": "Places disponibles (Almaval - Patients)",
}

def _canon(v):
    valeur = texte(v).strip()
    if not valeur or valeur in ("-", "x"):
        return ""
    norm = pm._norm(valeur)
    if norm in AXES["EQUIVALENTS"]:
        return AXES["EQUIVALENTS"][norm]
    return valeur

def _meme_axe(a, b):
    return pm._norm(_canon(a)) == pm._norm(_canon(b))

def _creer_profils(calc, aujourdhui, confirmer):
    onglet = socle.lire_onglet_de(ID_EFFECTIF, AXES["ONGLET_PROFIL"], rafraichir=True, avec_calculees=False)
    entetes = onglet.entetes
    nb_lignes = len(onglet.grille)
    prop = onglet.prop
    
    p = calc["p"]
    saisie = calc["saisie"]
    personnes = calc["personnes"]
    
    profils_a_creer = []
    rangees = []
    
    a_traiter = calc["sansProfil"][:AXES["PLAFOND_PROFILS"]]
    
    for sp in a_traiter:
        ini = sp["initiales"]
        ligne_places_num = sp["lignePlaces"]
        
        ligne_places = next((l for l in p["lignes"] if l["numero"] == ligne_places_num), None)
        if not ligne_places:
            continue
            
        rangee = [""] * len(entetes)
        colonnes_remplies = 0
        
        for i, T in enumerate(entetes):
            if not T:
                continue
            
            val = ""
            if T == "Initiales":
                val = ini
            elif T == "Nom prénom":
                pers = personnes.get(ini)
                if pers and texte(pers.get("Nom prénom")):
                    val = texte(pers.get("Nom prénom"))
                else:
                    val = ligne_places["nom"]
            elif T == "Source":
                val = AXES["SOURCE_PROFIL"]
            elif T == "Repris le":
                val = aujourdhui.strftime("%Y-%m-%d")
            elif T == "Mis à jour dans Places disponibles le":
                c_maj = p["colonne"]("Mis à jour le")
                if c_maj and c_maj not in p["debordement"]:
                    val = ligne_places["valeurs"][c_maj - 1] if c_maj - 1 < len(ligne_places["valeurs"]) else ""
            else:
                cible = {"Âge patients dès": "Âge patients"}.get(T, T)
                c = p["colonne"](cible, visible=True) or p["colonne"](cible)
                if c and c not in p["debordement"]:
                    val = ligne_places["valeurs"][c - 1] if c - 1 < len(ligne_places["valeurs"]) else ""
                    
            if val:
                rangee[i] = val
                colonnes_remplies += 1
                
        idx_axe1 = entetes.index("Axe thérapie 1") if "Axe thérapie 1" in entetes else -1
        if idx_axe1 >= 0 and not rangee[idx_axe1]:
            s = saisie.get(ini, {})
            val_saisie = s.get("Axe thérapie", "")
            if val_saisie:
                rangee[idx_axe1] = _canon(val_saisie)
                colonnes_remplies += 1
                
        for champ in ["Axe thérapie 1", "Axe thérapie 2", "Axe thérapie complémentaire"]:
            if champ in entetes:
                idx = entetes.index(champ)
                if rangee[idx]:
                    rangee[idx] = _canon(rangee[idx])
                    
        profils_a_creer.append({
            "initiales": ini,
            "lignePlaces": ligne_places_num,
            "colonnesRemplies": colonnes_remplies,
            "_rangee": rangee
        })
        rangees.append(rangee)
        
    if not confirmer:
        for p_creer in profils_a_creer:
            p_creer.pop("_rangee", None)
        return profils_a_creer
        
    if not rangees:
        return []
        
    debut = nb_lignes + 1
    socle._assurer_dimensions(ID_EFFECTIF, prop, lignes=debut + len(rangees) - 1)
    socle._batch(ID_EFFECTIF, socle._requete_cellules(prop["sheetId"], debut - 1, 0, rangees))
    socle._oublier(ID_EFFECTIF, prop["title"])
    
    onglet_relu = socle.lire_onglet_de(ID_EFFECTIF, AXES["ONGLET_PROFIL"], rafraichir=True, avec_calculees=False)
    
    profils_crees = []
    for i, p_creer in enumerate(profils_a_creer):
        ligne_ecrite = debut + i
        relu = False
        for l in onglet_relu.lignes:
            if l["_ligne"] == ligne_ecrite:
                if texte(l.get("Initiales")).strip() == p_creer["initiales"]:
                    relu = True
                break
        profils_crees.append({
            "initiales": p_creer["initiales"],
            "ligne": ligne_ecrite,
            "relu": relu,
            "colonnesRemplies": p_creer["colonnesRemplies"]
        })
        
    return profils_crees

def calculer():
    personnes, engagements, cliniques, profils = pm._registres()
    index = {ini: pm._jetons_personne(p) for ini, p in personnes.items()}
    
    saisie_onglet = socle.lire_onglet(AXES["ONGLET_SAISIE"], rafraichir=True)
    saisie = {}
    doublons_saisie = []
    for l in saisie_onglet.lignes:
        ini = texte(l.get("Initiales")).strip()
        if not ini:
            continue
        if ini in saisie:
            if ini not in doublons_saisie:
                doublons_saisie.append(ini)
        else:
            saisie[ini] = l
            
    p = pm._lire_places()
    places_par_ini = {}
    sans_correspondance = []
    for l in p["lignes"]:
        inis = pm._correspondances(l["nom"], personnes, index)
        if len(inis) == 1:
            places_par_ini[inis[0]] = l
        else:
            sans_correspondance.append({"ligne": l["numero"], "nom": l["nom"]})
            
    personnes_vues = set(places_par_ini.keys()).union(profils.keys())
    
    ecritures = []
    conflits = []
    ecarts_saisie = []
    sans_profil = []
    
    for ini in personnes_vues:
        ligne_places = places_par_ini.get(ini)
        ligne_profil = profils.get(ini)
        ligne_saisie = saisie.get(ini, {})
        
        if ligne_places and not ligne_profil:
            sans_profil.append({"initiales": ini, "lignePlaces": ligne_places["numero"]})
            
        for champ in AXES["CHAMPS"]:
            val_profil = ligne_profil.get(champ, "") if ligne_profil else ""
            
            col_places = p["colonne"](champ)
            val_places = ""
            if ligne_places and col_places and col_places not in p["debordement"]:
                val_places = ligne_places["valeurs"][col_places - 1] if col_places - 1 < len(ligne_places["valeurs"]) else ""
                
            val_saisie = ligne_saisie.get("Axe thérapie", "") if champ == "Axe thérapie 1" else ""
            
            # e1. Équivalence
            if ligne_profil and pm._norm(val_profil) in AXES["EQUIVALENTS"]:
                ecritures.append({
                    "onglet": AXES["ONGLET_PROFIL"], "initiales": ini, "champ": champ,
                    "ligne": ligne_profil["_ligne"], "colonne": None,
                    "avant": val_profil, "apres": AXES["EQUIVALENTS"][pm._norm(val_profil)],
                    "motif": "équivalence Clinique = Intégrative"
                })
                val_profil = AXES["EQUIVALENTS"][pm._norm(val_profil)]
                
            if ligne_places and col_places and col_places not in p["debordement"] and pm._norm(val_places) in AXES["EQUIVALENTS"]:
                ecritures.append({
                    "onglet": "Places disponibles", "initiales": ini, "champ": champ,
                    "ligne": ligne_places["numero"], "colonne": col_places,
                    "avant": val_places, "apres": AXES["EQUIVALENTS"][pm._norm(val_places)],
                    "motif": "équivalence Clinique = Intégrative"
                })
                val_places = AXES["EQUIVALENTS"][pm._norm(val_places)]
                
            canon_profil = _canon(val_profil)
            canon_places = _canon(val_places)
            canon_saisie = _canon(val_saisie)
            
            # e2. Profil vide, saisie remplie
            if ligne_profil and not texte(val_profil).strip() and canon_saisie and champ == "Axe thérapie 1":
                ecritures.append({
                    "onglet": AXES["ONGLET_PROFIL"], "initiales": ini, "champ": champ,
                    "ligne": ligne_profil["_ligne"], "colonne": None,
                    "avant": val_profil, "apres": canon_saisie,
                    "motif": "profil complété depuis la saisie d'onboarding"
                })
                canon_profil = canon_saisie
                
            # e3. Profil vide, Places rempli
            elif ligne_profil and not texte(val_profil).strip() and canon_places:
                ecritures.append({
                    "onglet": AXES["ONGLET_PROFIL"], "initiales": ini, "champ": champ,
                    "ligne": ligne_profil["_ligne"], "colonne": None,
                    "avant": val_profil, "apres": canon_places,
                    "motif": "profil complété depuis Places disponibles"
                })
                canon_profil = canon_places
                
            # e4. Places vide, profil rempli
            if ligne_places and col_places and col_places not in p["debordement"] and not texte(val_places).strip() and canon_profil:
                ecritures.append({
                    "onglet": "Places disponibles", "initiales": ini, "champ": champ,
                    "ligne": ligne_places["numero"], "colonne": col_places,
                    "avant": val_places, "apres": canon_profil,
                    "motif": "Places disponibles alignée sur le profil"
                })
                
            # e5. Profil et Places remplis et différents
            if ligne_profil and ligne_places and canon_profil and canon_places and not _meme_axe(canon_profil, canon_places):
                conflits.append({
                    "initiales": ini, "champ": champ, "profil": val_profil, "places": val_places,
                    "lignePlaces": ligne_places["numero"], "ligneProfil": ligne_profil["_ligne"]
                })
                
            # e6. Axe thérapie 1 du profil rempli, saisie remplie et différente
            if ligne_profil and champ == "Axe thérapie 1" and canon_profil and canon_saisie and not _meme_axe(canon_profil, canon_saisie):
                ecarts_saisie.append({
                    "initiales": ini, "profil": val_profil, "saisie": val_saisie
                })
                
    return {
        "ecritures": ecritures, "conflits": conflits, "ecartsSaisie": ecarts_saisie,
        "sansProfil": sans_profil, "sansCorrespondance": sans_correspondance,
        "doublonsSaisie": doublons_saisie, "personnesVues": len(personnes_vues),
        "p": p, "profils": profils, "saisie": saisie, "personnes": personnes
    }

def passage_axes(confirmer=False):
    with _verrou:
        calc = calculer()
        ecritures = calc["ecritures"]
        
        a_ecrire = ecritures[:AXES["PLAFOND_ECRITURES"]]
        reportes = max(0, len(ecritures) - len(a_ecrire))
        
        p = calc["p"]
        onglet_profil = socle.lire_onglet_de(ID_EFFECTIF, AXES["ONGLET_PROFIL"], rafraichir=False, avec_calculees=False)
        
        # Résolution des colonnes pour le profil
        for e in a_ecrire:
            if e["onglet"] == AXES["ONGLET_PROFIL"]:
                if e["champ"] in onglet_profil.entetes:
                    e["colonne"] = onglet_profil.entetes.index(e["champ"]) + 1
                    
        # Filtrer les écritures sans colonne résolue
        a_ecrire = [e for e in a_ecrire if e["colonne"] is not None]
        
        faits = []
        if confirmer and a_ecrire:
            reqs_places = []
            reqs_profil = []
            
            sheet_id_places = p["prop"]["sheetId"]
            sheet_id_profil = onglet_profil.sheet_id
            
            for e in a_ecrire:
                req = socle._requete_cellules(
                    sheet_id_places if e["onglet"] == "Places disponibles" else sheet_id_profil,
                    e["ligne"] - 1, e["colonne"] - 1, [[e["apres"]]]
                )
                if e["onglet"] == "Places disponibles":
                    reqs_places.extend(req)
                else:
                    reqs_profil.extend(req)
                    
            if reqs_places:
                socle._batch(pm.ID_PLACES, reqs_places)
                socle._oublier(pm.ID_PLACES, p["prop"]["title"])
            if reqs_profil:
                socle._batch(ID_EFFECTIF, reqs_profil)
                socle._oublier(ID_EFFECTIF, onglet_profil.titre)
                
            # Relecture
            p_relu = pm._lire_places()
            profil_relu = socle.lire_onglet_de(ID_EFFECTIF, AXES["ONGLET_PROFIL"], rafraichir=True, avec_calculees=False)
            
            for e in a_ecrire:
                relu = ""
                if e["onglet"] == "Places disponibles":
                    for l in p_relu["lignes"]:
                        if l["numero"] == e["ligne"]:
                            if e["colonne"] - 1 < len(l["valeurs"]):
                                relu = l["valeurs"][e["colonne"] - 1]
                            break
                else:
                    for l in profil_relu.lignes:
                        if l["_ligne"] == e["ligne"]:
                            relu = l.get(e["champ"], "")
                            break
                            
                e["relu"] = relu
                e["conforme"] = _meme_axe(relu, e["apres"])
                faits.append(e)
                
        try:
            res_profils = _creer_profils(calc, maintenant().date(), confirmer)
            if confirmer:
                profils_crees = res_profils
            else:
                profils_a_creer = res_profils
        except Exception as exc:
            erreur_profils = str(exc)
                
        lien_places = "https://docs.google.com/spreadsheets/d/" + pm.ID_PLACES + "/edit#gid=" + str(p["prop"]["sheetId"])
        lien_profil = "https://docs.google.com/spreadsheets/d/" + ID_EFFECTIF + "/edit#gid=" + str(onglet_profil.sheet_id)
        
        ret = {
            "moteur": "axes",
            "confirme": bool(confirmer),
            "personnesVues": calc["personnesVues"],
            "aEcrire" if not confirmer else "ecrits": a_ecrire if not confirmer else faits,
            "reportesAuPassageSuivant": reportes,
            "conflits": calc["conflits"],
            "ecartsSaisie": calc["ecartsSaisie"],
            "sansProfil": calc["sansProfil"],
            "sansCorrespondance": calc["sansCorrespondance"],
            "doublonsSaisie": calc["doublonsSaisie"],
            "liens": {
                "places": lien_places,
                "profil": lien_profil
            }
        }
        
        if "erreur_profils" in locals():
            ret["erreurProfils"] = erreur_profils
        elif confirmer:
            ret["profilsCrees"] = profils_crees
        else:
            ret["profilsACreer"] = profils_a_creer
            
        return ret

@mcp.tool()
@tolerant
def axes_controle(confirmer: bool = False):
    """Axes thérapeutiques : source unique (saisie d'onboarding à l'entrée, puis Registre - Profil clinique, copié dans Places disponibles), comble les trous et l'équivalence Clinique = Intégrative, signale les conflits ; simulation sans confirmer."""
    return passage_axes(confirmer=confirmer)

try:
    _pont_precedent_axes = outils_lieux._pont

    def _pont(texte_sujet: str):
        brut = str(texte_sujet or "").strip()
        mots = brut.split()
        premier = mots[0].lower() if mots else ""
        drapeaux = {m.lower() for m in mots[1:] if "=" not in m}
        if premier == "axes":
            return pont_de_fond("axes", drapeaux, tolerant(passage_axes), dict(confirmer=("confirmer" in drapeaux)))
        return _pont_precedent_axes(brut)

    outils_lieux._pont = _pont
except Exception as _exc:  # noqa: BLE001
    print("[axes] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)
