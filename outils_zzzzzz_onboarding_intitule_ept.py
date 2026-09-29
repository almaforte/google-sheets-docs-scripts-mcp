"""Almaval - onboarding : intitule de l'EPT des affectations lu au referentiel, 29.09.2026.

Decision d'Alberto du 29.09.2026 : « EPT Relations - Relations externes -
Charge de projet est le correct ». Le moteur des postes (outils_zzzzz_
onboarding_7_postes, passage de 4 h 45 sous gestion@) composait l'intitule
de l'EPT de chaque affectation en collant le pole au service par une
espace : « EPT Relations Relations externes - Charge de projet », « EPT
Clinique ADC - Charge de projet ». Le referentiel des postes (Postes -
Referentiel d'Almaval - Listes, colonne « Intitule EPT ») porte la forme
juste, chaque niveau separe par un tiret : « EPT Service - Pole - Poste ».

L'intitule vient desormais du referentiel, source unique, par la cle du
poste. Si le poste n'y est pas (cle inconnue), il est compose dans la
meme grammaire, un pole imbrique « Locaux > Intendance » devenant
« Locaux - Intendance ».

Ce module ne reecrit pas le moteur : il enveloppe integrer_source au
chargement, comme outils_zzzzzz_onboarding_ecart_en_vigueur le fait pour
l'ecart. Son nom le fait charger apres outils_zzzzz_onboarding_7_postes
(bootstrap importe les modules par ordre alphabetique), et le moteur
appelle integrer_source par son nom de module a chaque passage, d'ou
l'effet du remplacement. Le fichier Apps Script « 28 Postes et
responsables » porte la meme correction depuis le meme jour.
"""

try:
    import outils_zzzzz_onboarding_7_postes as _postes

    _integrer_source_d_origine = _postes.integrer_source

    def _intitule_compose(service, pole, poste):
        niveaux = [s.strip() for s in str(pole or "").split(">") if s.strip()]
        milieu = (" - " + " - ".join(niveaux)) if niveaux else ""
        return "EPT " + str(service or "") + milieu + " - " + str(poste or "")

    def _integrer_source_intitule_du_referentiel(lignes_source, dt_ref, origine, cle_cible, map_cible,
                                                 dict_referentiel):
        debut = len(map_cible)
        _integrer_source_d_origine(lignes_source, dt_ref, origine, cle_cible, map_cible, dict_referentiel)
        for aff in map_cible[debut:]:
            ref = dict_referentiel.get(aff.get("Clé poste")) if dict_referentiel else None
            intitule = _postes.po_texte(ref.get("Intitulé EPT")) if ref else ""
            if not intitule:
                intitule = _intitule_compose(aff.get("Service"), aff.get(_postes.CFG_POSTES["LIB_POLE"]),
                                             aff.get("Poste"))
            aff["Intitulé EPT"] = intitule

    _postes.integrer_source = _integrer_source_intitule_du_referentiel
    print("[onboarding intitule EPT] intitule lu au referentiel des postes", flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[onboarding intitule EPT] non pose : " + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)
