"""Almaval - onboarding : les prestataires externes dans l'arbre des responsables, 29.09.2026.

Decision d'Alberto du 29.09.2026 (« oui ») : les postes de l'organigramme
tenus par un prestataire externe ne doivent plus paraitre vacants dans
l'arborescence des responsables (Vue - Arborescence des responsables de
l'Effectif, et sa jumelle sans les EPT dans Almaval - Organigramme pour le
secretariat).

Architecture respectee, decision du 21.09.2026 au soir : pas de melange
entre collaborateurs et prestataires avant l'audit integral. Un prestataire
n'entre donc ni dans Saisie - Affectations ni dans Registre - Affectations.
Il a son code dans Registre - Entites, son contrat dans Registre - Contrats
de prestations, et la repartition de son contrat par poste dans un onglet a
part, Registre - Affectations prestataires, une ligne par contrat et par
poste (cle du contrat, cle du poste, taux, dates).

Ce module ne reecrit pas le moteur : il enveloppe construire_l_arborescence
au chargement. Pendant la seule construction de l'arbre, la lecture de
Registre - Affectations rend en plus une ligne par affectation de
prestataire en vigueur : le titulaire est la raison sociale du fournisseur,
les initiales sont son code de trois lettres, le taux compte dans l'EPT du
poste. Le registre des affectations des collaborateurs n'est jamais ecrit
par ce module. Son nom le fait charger apres outils_zzzzz_onboarding_7_postes
(bootstrap importe les modules par ordre alphabetique), et le passage appelle
construire_l_arborescence par son nom de module, d'ou l'effet.
"""

try:
    import copy as _copy
    import re as _re

    import outils_zzzzz_onboarding_7_postes as _postes

    ONGLET_AFFECTATIONS_PRESTATAIRES = "Registre - Affectations prestataires"
    _CLE_CONTRAT = _re.compile(r"^[A-Z]{3}-\d+$")
    _construire_l_arborescence_d_origine = _postes.construire_l_arborescence

    def _lignes_des_prestataires(p):
        try:
            lu = p.feuille(_postes.CFG_POSTES["CLASSEUR_EFFECTIF"], ONGLET_AFFECTATIONS_PRESTATAIRES).lire()
        except Exception as exc:  # noqa: BLE001
            p.avertir("affectations des prestataires non lues : " + str(exc)[:200])
            return []
        lignes = []
        for l in lu.lignes:
            cle_contrat = _postes.po_texte(l.get("Clé contrat"))
            cle_poste = _postes.po_texte(l.get("Clé poste"))
            if not cle_poste or not _CLE_CONTRAT.match(cle_contrat):
                continue
            etat = _postes.po_texte(l.get("État"))
            if etat and etat != "En cours":
                continue
            fournisseur = _postes.po_sans_erreur(l.get("Fournisseur")) or cle_contrat
            lignes.append({
                "Clé affectation": cle_contrat + " | " + cle_poste,
                "Origine": "Prestataire externe",
                "Clé engagement": cle_contrat,
                "Nom prénom": fournisseur,
                "État de l'engagement": "En cours",
                "Clé poste": cle_poste,
                "Taux": l.get("Taux"),
                "Date de début": l.get("Date de début"),
                "Date de fin": l.get("Date de fin"),
            })
        return lignes

    def _construire_l_arborescence_avec_prestataires(p):
        extra = _lignes_des_prestataires(p)
        if not extra:
            return _construire_l_arborescence_d_origine(p)
        feuille_aff = p.feuille(_postes.CFG_POSTES["CLASSEUR_EFFECTIF"], _postes.CFG_POSTES["ONGLET_AFFECTATIONS"])
        lire_d_origine = feuille_aff.lire

        def lire_avec_prestataires(*args, **kwargs):
            lu = lire_d_origine(*args, **kwargs)
            augmente = _copy.copy(lu)
            augmente.lignes = list(lu.lignes) + extra
            return augmente

        feuille_aff.lire = lire_avec_prestataires
        try:
            bilan = _construire_l_arborescence_d_origine(p)
        finally:
            try:
                del feuille_aff.lire
            except AttributeError:
                feuille_aff.lire = lire_d_origine
        if isinstance(bilan, dict):
            bilan["prestataires"] = sorted({x["Nom prénom"] + " (" + x["Clé poste"] + ")" for x in extra})
        return bilan

    _postes.construire_l_arborescence = _construire_l_arborescence_avec_prestataires
    print("[onboarding arbre] prestataires externes lus dans " + ONGLET_AFFECTATIONS_PRESTATAIRES, flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[onboarding arbre] non pose : " + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)
