"""Almaval - onboarding : menu « Raison sociale » du Registre - Entites sur sa propre liste, 29.09.2026.

Les huit prestataires externes qui tiennent un poste de l'organigramme
(decision d'Alberto du 29.09.2026) sont inscrits au Registre - Entites de
l'Effectif. Le menu impose de leur colonne « Raison sociale » pointait
jusqu'ici la liste « Entite juridique » (fichier Apps Script « 13f Menus
des entites et des contrats de prestations »). Or cette liste sert aussi
la saisie des collaborateurs (Saisie - Collaborateurs > Entite juridique),
l'entite employeuse et l'entite beneficiaire des engagements, et les
bureaux. Y ajouter les prestataires les rendait choisissables comme
employeur d'un collaborateur, ce que la decision du 21.09.2026 exclut :
pas de melange entre collaborateurs et prestataires avant l'audit.

La liste « Entite juridique » redevient donc celle des seules societes du
groupe, et la colonne « Raison sociale » du Registre - Entites lit une
liste a part, « Raison sociale », qui porte les societes du groupe puis
les prestataires. Une societe nouvelle du groupe s'inscrit dans les deux
listes de l'onglet Valeurs d'Almaval - Listes ; un prestataire nouveau,
dans « Raison sociale » seulement.

Ce module ne reecrit pas le moteur : il corrige au chargement l'entree de
MENUS_IMPOSES du classeur Effectif, que repointer_un_classeur relit a
chaque passage. Son nom le fait charger apres outils_zzzzz_onboarding_4_
validations (bootstrap importe les modules par ordre alphabetique). Le
fichier Apps Script « 13f » porte la meme correction depuis le meme jour.
"""

try:
    import outils_zzzzz_onboarding_4_validations as _validations
    from outils_zzzzz_onboarding_0_socle import ID_EFFECTIF as _ID_EFFECTIF

    _corriges = 0
    for _menu in _validations.MENUS_IMPOSES.get(_ID_EFFECTIF, []):
        if _menu.get("onglet") == "Registre - Entités" and _menu.get("colonne") == "Raison sociale":
            _menu["liste"] = "Raison sociale"
            _corriges += 1
    print("[onboarding raison sociale] menu impose repointe sur la liste Raison sociale : " + str(_corriges), flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[onboarding raison sociale] non pose : " + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)
