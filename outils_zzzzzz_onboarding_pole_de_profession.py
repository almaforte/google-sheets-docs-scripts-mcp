"""Almaval - onboarding : le pole des affectations cliniques lu dans la profession, 30.09.2026.

Decision d'Alberto du 30.09.2026, a propos d'Isabelle Barthelemy-Maeder dont
AlmaDesk n'affichait aucun pole : « pour le pole, faut simplement voir la
profession et attribuer le pole ». Les affectations cliniques de Saisie -
Affectations tiennent encore les postes generiques « Clinique > Therapeute »
et « Clinique > Therapeute en formation », qui n'ont pas de pole au
referentiel ; la colonne « Pole » du Registre - Affectations restait donc vide
pour tous les cliniciens.

Regle posee : pour une affectation du service Clinique sur l'un de ces deux
postes generiques, sans pole saisi, le pole est celui de la profession de
l'engagement (Registre - Engagements, colonne « Profession ») :
    Psychologue                -> Psychologie
    Medecin psychiatre         -> Medecine
    Infirmier                  -> Soins infirmiers
    Neuropsychologue           -> Neuropsychologie
    Approches complementaires  -> Approches complementaires
Les libelles sont ceux de Postes - Referentiel d'Almaval - Listes. « Medecine »
reste le mot des registres ; « Psychiatrie » n'est que le libelle affiche de
l'organigramme (decision du 29.09.2026).

La cle du poste, l'intitule de l'EPT, le responsable et le cahier des charges
ne changent pas : seul le pole est renseigne. Un pole deja saisi a la main
dans la porte n'est jamais remplace.

Ce module ne reecrit pas le moteur des postes : il enveloppe integrer_source
(et _construire_les_affectations_28, pour disposer de la connexion du passage
et lire les professions une seule fois). Son nom le fait charger apres
outils_zzzzz_onboarding_7_postes et apres l'enveloppe de l'intitule de l'EPT
(bootstrap importe les modules par ordre alphabetique) ; le moteur appelle
ces fonctions par leur nom de module a chaque passage, d'ou l'effet. Le
projet Apps Script d'onboarding porte la meme regle, fichier « 78 Pole de
profession dans les affectations ».
"""

try:
    import re as _re
    import unicodedata as _ud

    import outils_zzzzz_onboarding_7_postes as _postes

    _REGLES_POLE = [
        (_re.compile(r"neuropsych"), "Neuropsychologie"),
        (_re.compile(r"psycholog|psychotherapeut"), "Psychologie"),
        (_re.compile(r"psychiatr|medecin|pedopsych"), "Médecine"),
        (_re.compile(r"infirmi"), "Soins infirmiers"),
        (_re.compile(r"approche|complementaire|naturopath"), "Approches complémentaires"),
    ]

    def _norme(v):
        t = _ud.normalize("NFD", str(v or "")).encode("ascii", "ignore").decode("ascii")
        return t.lower().strip()

    def pole_de_profession(profession):
        p = _norme(profession)
        if not p:
            return ""
        for motif, pole in _REGLES_POLE:
            if motif.search(p):
                return pole
        return ""

    _contexte = {"p": None, "professions": None}

    def _professions():
        if _contexte["professions"] is None:
            carte = {}
            p = _contexte["p"]
            if p is not None:
                try:
                    lignes = p.feuille(_postes.CFG_POSTES["CLASSEUR_EFFECTIF"],
                                       _postes.CFG_POSTES["ONGLET_ENGAGEMENTS"]).lire().lignes
                    for l in lignes:
                        cle = _postes.po_texte(l.get("Clé engagement"))
                        if cle:
                            carte[cle] = _postes.po_texte(l.get("Profession"))
                except Exception as exc:  # noqa: BLE001
                    try:
                        p.avertir("pôle de profession : engagements non lus, " + str(exc)[:200])
                    except Exception:  # noqa: BLE001
                        pass
            _contexte["professions"] = carte
        return _contexte["professions"]

    _POSTES_GENERIQUES = {_postes.CFG_POSTES["POSTE_THERAPEUTE"], _postes.CFG_POSTES["POSTE_THERAPEUTE_FORMATION"]}
    _integrer_source_d_origine = _postes.integrer_source

    def _integrer_source_pole_de_profession(lignes_source, dt_ref, origine, cle_cible, map_cible, dict_referentiel):
        debut = len(map_cible)
        _integrer_source_d_origine(lignes_source, dt_ref, origine, cle_cible, map_cible, dict_referentiel)
        if _contexte["p"] is None:
            return
        lib = _postes.CFG_POSTES["LIB_POLE"]
        for aff in map_cible[debut:]:
            if _postes.po_texte(aff.get("Service")) != "Clinique":
                continue
            if _postes.po_texte(aff.get(lib)):
                continue
            if _postes.po_texte(aff.get("Clé poste")) not in _POSTES_GENERIQUES:
                continue
            pole = pole_de_profession(_professions().get(_postes.po_texte(aff.get("Clé engagement"))))
            if pole:
                aff[lib] = pole

    _construire_28_d_origine = _postes._construire_les_affectations_28

    def _construire_28_pole_de_profession(p):
        _contexte["p"] = p
        _contexte["professions"] = None
        try:
            return _construire_28_d_origine(p)
        finally:
            _contexte["p"] = None
            _contexte["professions"] = None

    _postes.integrer_source = _integrer_source_pole_de_profession
    _postes._construire_les_affectations_28 = _construire_28_pole_de_profession
    _postes.pole_de_profession = pole_de_profession
    print("[onboarding pole de profession] pole des affectations cliniques lu dans la profession", flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[onboarding pole de profession] non pose : " + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)
