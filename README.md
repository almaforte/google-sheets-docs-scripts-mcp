# Serveur MCP Google Sheets, Docs et Apps Script — Almaval

Serveur FastMCP exposant Google Sheets, Docs, Drive et Apps Script à
Claude. Hébergé sur Railway, projet « Google Sheets & Apps Script ».

## Deux identités Google, séparées par API

Ce n'est pas un repli de l'une sur l'autre, c'est une séparation câblée.

**Sheets, Docs, Drive** passent par le compte de service avec délégation
à l'échelle du domaine : `GOOGLE_SERVICE_ACCOUNT_JSON` et
`IMPERSONATE_USER`, via `creds.with_subject(subject)`.

**Apps Script** passe par un jeton utilisateur :
`GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`,
`GOOGLE_OAUTH_REFRESH_TOKEN`. Google l'impose, l'API Apps Script
n'acceptant pas les comptes de service.

Conséquence pratique : changer `IMPERSONATE_USER` sans refaire le jeton
ne déplace que la moitié du serveur.

**Google Cloud**, depuis le 08.09.2026, est une troisième voie : le même
compte de service, mais SANS délégation, au scope `cloud-platform`. Voir
la section Google Cloud plus bas.

## Deux services sur ce même dépôt

`web` travaille sous am.forte. `web-contact` travaille sous
contact@almaval.ch, le compte qui exécute le système de documents
cliniques. Les secrets partagés sont posés en variables de référence
`${{web.…}}` : une seule source de vérité.

Un commit reconstruit **les deux**. Ne pas pousser en fin de journée.

## bootstrap.py, et le piège de la commande de démarrage

`main.py` fait plus de cent kilo-octets, et l'outil d'écriture dont
dispose Claude ne remplace que des fichiers entiers : le réémettre pour
ajouter quelques lignes risquait une troncature silencieuse.

`bootstrap.py` contourne l'obstacle sans rien réécrire. Il importe
`main`, qui enregistre ses outils au passage, ajoute les siens sur le
même serveur FastMCP, puis reconstruit l'application ASGI avec le même
chemin et le même contrôle de clé. `main.py` n'est pas modifié d'une
ligne.

Le même raisonnement vaut pour bootstrap.py lui-même : tout module
nommé `outils_*.py` posé à côté de lui est importé automatiquement au
démarrage. Ajouter une famille d'outils ne demande donc plus de toucher
au point d'entrée.

**Le Procfile ne fait pas foi.** Les deux services portent une commande
de démarrage explicite dans leurs réglages Railway, et elle l'emporte
sur le Procfile. Modifier le Procfile seul ne produit strictement aucun
effet, sans le moindre avertissement : le serveur redémarre, les
journaux sont identiques, et seule la liste des outils exposés trahit
que rien n'a changé. La commande doit valoir `python bootstrap.py` dans
Settings, Deploy, Custom Start Command.

Second piège dans la foulée : un `redeploy` rejoue la configuration du
déploiement d'origine. Après un changement de commande de démarrage, il
faut une vraie reconstruction, donc un commit.

Outils ajoutés dans bootstrap.py :

`update_web_app_deployment` publie une nouvelle version **sur un
déploiement existant**, donc sans changer son adresse. `deploy_web_app`,
lui, crée un déploiement de plus à chaque appel : nouvelle URL, et
l'ancienne adresse continue de servir du code périmé sans erreur
visible. C'est arrivé au portail de documents cliniques le 01.09.2026.
Dès qu'une adresse est en service, utiliser la mise à jour, jamais la
création.

`identite_du_serveur` répond sous quel compte le serveur travaille
réellement, des deux côtés. À interroger au moindre doute sur « qui a
écrit ce fichier ».

## Google Cloud

`outils_cloud.py` porte Service Usage et Resource Manager,
`outils_cloud_iam.py` les stratégies IAM, les comptes de service, le
trafic et les quotas. Vingt outils au total, préfixés `cloud_`, plus
`identite_cloud`.

Ils règlent une panne précise, constatée le 05.09.2026 : un projet Apps
Script créé par ce connecteur était inutilisable parce que l'API Drive
REST n'était pas activée sur son projet Cloud, et la seule issue passait
par la console. `cloud_activer_api` et
`cloud_preparer_projet_apps_script` la referment.

**L'identité est différente du reste du serveur.** Le compte de service
agit ici en son nom propre, sans `with_subject` : Google Cloud raisonne
en stratégies IAM posées sur des projets, pas en propriété de fichiers,
et une délégation de domaine n'y a aucun sens. Le périmètre réel du
serveur est donc exactement ce qu'IAM lui accorde, et se révoque en une
ligne.

**Amorçage, une seule fois.** Un compte de service ne détient rien tant
que personne ne lui a rien donné, et cet octroi ne peut pas passer par
l'API puisque c'est lui qui ouvre l'API. Rôles à poser sur
`claude-sheets@claude-multiple-mails.iam.gserviceaccount.com`, au niveau
de l'organisation plutôt que d'un projet, faute de quoi chaque nouveau
projet demandera un octroi de plus :

- `roles/browser`
- `roles/serviceusage.serviceUsageAdmin`
- `roles/resourcemanager.projectIamAdmin`
- `roles/iam.serviceAccountAdmin`
- `roles/monitoring.viewer`

`identite_cloud` sert de témoin : tant que les rôles manquent, il
renvoie zéro projet visible et le message d'erreur exact de Google.

**Une clé privée ne se promène pas.**
`cloud_creer_cle_compte_de_service` renvoie la clé en clair et exige
donc `confirmer=true`. À n'utiliser que si aucune autre voie n'existe.

## Sécurité

`MCP_PATH` est un chemin non devinable, `MCP_API_KEY` la clé attendue en
en-tête. **Si `MCP_API_KEY` est vide, le contrôle est entièrement
désactivé** et le serveur devient ouvert à qui connaît l'URL, avec
l'identité d'un compte du domaine. Elle doit toujours être posée.

Le volet Cloud élargit ce que vaut cette clé : elle ouvre désormais
aussi ce qu'IAM accorde au compte de service. Raison de plus pour ne
jamais la laisser vide, et pour ne donner au compte de service que les
rôles réellement utiles.

## À faire

Figer la version de Python (`.python-version`) et épingler les versions
dans `requirements.txt` : aujourd'hui, une reconstruction peut changer
d'environnement sans que personne ne l'ait demandé.
