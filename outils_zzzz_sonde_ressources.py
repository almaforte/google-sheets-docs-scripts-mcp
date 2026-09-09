"""SONDE TEMPORAIRE - a supprimer des que la liste d'outils se debloque.

Elle ne declare aucun outil. Elle s'execute a l'import et ecrit dans le
journal de deploiement, seul canal qui ne depend pas de la liste d'outils
vue par le client, laquelle reste en retard sur ce que le serveur sert.

But unique : savoir si la delegation au niveau du domaine porte bien le
scope admin.directory.resource.calendar, et voir ce qui existe deja en
batiments, ressources et caracteristiques.
"""

import json
import traceback

MARQUE = "[sonde-ressources]"


def _dire(quoi, valeur):
    try:
        texte = json.dumps(valeur, ensure_ascii=False)[:2500]
    except Exception:
        texte = str(valeur)[:2500]
    print(MARQUE + " " + quoi + " : " + texte, flush=True)


try:
    from outils_delegation import service, sujet_par_defaut

    SCOPES = ["https://www.googleapis.com/auth/admin.directory.resource.calendar"]
    _dire("sujet impersonne", sujet_par_defaut())

    api = service("admin", "directory_v1", SCOPES).resources()

    try:
        b = api.buildings().list(customer="my_customer", maxResults=200).execute()
        batiments = b.get("buildings", [])
        _dire("nombre de batiments", len(batiments))
        _dire(
            "batiments",
            [
                {
                    "id": x.get("buildingId"),
                    "nom": x.get("buildingName"),
                    "etages": x.get("floorNames"),
                    "adresse": (x.get("address") or {}).get("addressLines"),
                    "localite": (x.get("address") or {}).get("locality"),
                }
                for x in batiments
            ],
        )
    except Exception as e:
        _dire("ECHEC batiments", str(e)[:1200])

    try:
        r = api.calendars().list(customer="my_customer", maxResults=200).execute()
        ressources = r.get("items", [])
        _dire("nombre de ressources", len(ressources))
        _dire(
            "ressources",
            [
                {
                    "id": x.get("resourceId"),
                    "nom": x.get("resourceName"),
                    "adresse": x.get("resourceEmail"),
                    "categorie": x.get("resourceCategory"),
                    "type": x.get("resourceType"),
                    "capacite": x.get("capacity"),
                    "batiment": x.get("buildingId"),
                    "etage": x.get("floorName"),
                }
                for x in ressources
            ],
        )
    except Exception as e:
        _dire("ECHEC ressources", str(e)[:1200])

    try:
        f = api.features().list(customer="my_customer", maxResults=200).execute()
        _dire(
            "caracteristiques",
            [x.get("name") for x in f.get("features", [])],
        )
    except Exception as e:
        _dire("ECHEC caracteristiques", str(e)[:1200])

except Exception:
    print(MARQUE + " ECHEC GLOBAL " + traceback.format_exc()[:2000], flush=True)
