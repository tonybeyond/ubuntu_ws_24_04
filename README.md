# ubunturiri

Scripts de préparation d’une ISO personnelle Ubuntu Server 24.04 LTS AMD64 avec **GNOME sous X11, Pop Shell et Citrix Workspace** : **ubunturiri**.

Le projet conserve une base serveur minimale, le pavage des fenêtres, les palettes adaptées et un profil de raccourcis pour Citrix. Il repose sur Ubuntu et GNOME Xorg. Shadow.tech n’est pas intégré.

> **État : scripts testés localement, installation complète non validée.** Les tests unitaires ne remplacent pas une construction d’ISO, un démarrage en VM ni une connexion Citrix réelle. Ne pas utiliser sur un disque contenant des données sans sauvegarde.

## Configuration

| Élément | Choix |
| --- | --- |
| Base | ISO officielle Ubuntu Server 24.04 LTS AMD64, source `ubuntu-server-minimal` |
| Bureau | GNOME 46, GDM, session `gnome-xorg`, Wayland désactivé |
| Pavage | Pop Shell, sources épinglées compatibles GNOME 46 |
| Citrix | Paquet officiel `icaclient` AMD64 fourni à la construction |
| Langue et clavier | Français suisse : `fr_CH.UTF-8`, clavier `ch+fr` |
| Compte par défaut | `ubunturiri`, nom de machine `ubunturiri`, personnalisables |
| Apparence | Tokyo Night par défaut ; palettes adaptées au fond, au terminal et à Pop Shell |
| Audio et réseau | PipeWire, WirePlumber, NetworkManager, Bluetooth |
| Sécurité | Racine LUKS exigée, connexion automatique désactivée, pas de serveur SSH installé par ce profil |

L’installation GNOME utilise des paquets sélectionnés avec `--no-install-recommends`, et non le métapaquet Ubuntu Desktop complet. Des outils de compilation restent installés pour Pop Shell. Il ne s’agit pas d’une adaptation du projet original, ni d’une ISO live de bureau préconfiguré.

## Prérequis

- Une machine ou VM **Ubuntu 24.04**, de préférence AMD64, pour construire. Le script refuse macOS, les autres distributions et l’exécution en root.
- Python **3.12 ou ultérieur** et les outils indiqués ci-dessous.
- Au moins **15 Gio libres**, seuil minimal contrôlé par le script ; prévoir davantage pour une VM de test.
- Une connexion Internet pour la construction **et pour l’installation**.
- Le paquet DEB AMD64 de Citrix Workspace, téléchargé depuis [Citrix](https://www.citrix.com/downloads/workspace-app/linux/), dans le respect de sa licence.

Ubuntu 24.04 figure dans les [prérequis Citrix Workspace pour Linux](https://docs.citrix.com/en-us/citrix-workspace-app-for-linux/system-requirements.html). Cela ne certifie pas ce profil personnalisé, Pop Shell ou toutes les fonctionnalités HDX. Vérifier les prérequis de la version exacte du client utilisée.

## Construire l’ISO

Dans Ubuntu 24.04 :

```bash
sudo apt update
sudo apt install git python3 xorriso openssl gpgv ubuntu-keyring
git clone https://github.com/tonybeyond/ubuntu_ws_24_04.git
cd ubuntu_ws_24_04
bash build-iso.sh --check
bash build-iso.sh --citrix-deb "/chemin/vers/icaclient_amd64.deb"
```

Remplacer le chemin du DEB par celui du fichier officiel téléchargé. Ne pas lancer `build-iso.sh` avec `sudo`.

Le script télécharge les sources épinglées et l’ISO Ubuntu courante de la série 24.04, vérifie la signature du manifeste Ubuntu et son SHA-256, puis demande deux fois le mot de passe utilisateur dans le terminal, sans l’afficher. Le mot de passe doit comporter au moins 12 caractères.

Après une construction réussie, les sorties prévues sont :

- `build/ubunturiri-ubuntu24.04-amd64.iso`
- `build/ubunturiri-ubuntu24.04-amd64.iso.sha256`

Le script réextrait la configuration et les fichiers embarqués pour les vérifier et contrôle la présence des entrées BIOS/UEFI. **Ce contrôle ne teste pas le démarrage.** Une sortie existante n’est pas écrasée.

### Options

```bash
bash build-iso.sh --help
bash build-iso.sh --citrix-deb "/chemin/vers/icaclient_amd64.deb" \
  --username moncompte \
  --hostname monposte \
  --output "$HOME/iso-privees/monposte.iso"
```

L’option `--iso /chemin/vers/ubuntu-24.04.x-live-server-amd64.iso` permet de réutiliser une ISO téléchargée. Son nom et son empreinte doivent correspondre à la version actuellement référencée dans le manifeste signé officiel : une ancienne révision sera refusée. La vérification nécessite toujours Internet.

## Installation et chiffrement

1. Tester d’abord l’ISO dans une VM AMD64 avec un disque jetable.
2. Démarrer sur le média et configurer le réseau dans Subiquity.
3. Sélectionner le disque cible, choisir **LVM et activer explicitement le chiffrement**.
4. Saisir une phrase de passe LUKS et vérifier le récapitulatif avant de confirmer l’effacement.
5. Laisser l’installation récupérer les paquets Ubuntu, installer Citrix et compiler Pop Shell.
6. À la fin, la machine s’éteint. Retirer le média, redémarrer, déverrouiller LUKS puis ouvrir la session utilisateur.

> **Attention : le contrôle obligatoire de LUKS intervient après le partitionnement et l’installation de la base, avant la configuration du bureau.** Il refuse la finalisation si la racine n’est pas chiffrée, mais ne prévient ni n’annule un effacement déjà confirmé. Le chiffrement n’est pas coché automatiquement.

Le contrôle suit les périphériques parents de la racine et exige LUKS ainsi qu’un déverrouillage sans fichier de clé dans `crypttab`. Utiliser le partitionnement guidé LVM chiffré ; les montages personnalisés séparés ne sont pas tous vérifiés. Les partitions d’amorçage peuvent rester non chiffrées : ce profil ne chiffre pas chaque secteur du disque.

### Protection des mots de passe

- **Compte utilisateur :** saisi à la construction, transmis à OpenSSL par l’entrée standard ; seule l’empreinte salée SHA-512-crypt est embarquée.
- **LUKS :** phrase de passe saisie dans l’installateur, distincte du processus de construction et absente de l’ISO préparée.
- **ISO privée :** le hash peut subir une attaque hors ligne et permet de reproduire le même compte sur d’autres installations. Ne pas publier l’ISO ni sa configuration d’installation.
- Aucun jeton GitHub ou autre secret d’accès n’est nécessaire au fonctionnement des scripts.

## Utilisation du bureau

| Raccourci | Action prévue |
| --- | --- |
| `Super + Entrée` | Ouvrir le terminal |
| `Super + Espace` | Vue d’ensemble GNOME |
| `Super + R` | Mode de manipulation des fenêtres Pop Shell |
| `Super + Y` | Activer ou désactiver le pavage Pop Shell |
| `Super + Maj + Y` | Palette suivante |
| `Super + Échap` | Basculer le mode clavier Citrix |
| `Super + L` | Verrouillage local, conservé en mode Citrix |

Dans la session utilisateur, sans `sudo` :

```bash
ubunturiri-theme-set --list
ubunturiri-theme-set tokyo-night
ubunturiri-theme-set --next
ubunturiri-citrix-mode
ubunturiri-citrix-mode --restore
```

Le mode Citrix sauvegarde puis suspend les raccourcis GNOME/Pop Shell sélectionnés. Une seconde activation les restaure ; la restauration est également demandée à l’ouverture de session. Il ne garantit pas la capture de toutes les touches par Citrix et ne suspend pas le verrouillage du poste.

Les palettes ne remplacent pas intégralement le thème GNOME Shell ni l’apparence des applications libadwaita. Aucun lanceur Pop Launcher séparé n’est installé : la vue d’ensemble GNOME sert de lanceur.

## Citrix : installation et limites

Le script vérifie le nom `icaclient` et l’architecture `amd64` du DEB, puis laisse APT résoudre ses dépendances dans Ubuntu 24.04. Ce contrôle n’authentifie pas le fournisseur du DEB : utiliser uniquement le téléchargement officiel. Aucun dépôt d’une autre version Ubuntu ni faux lien de bibliothèque n’est ajouté.

La présence du binaire `wfica` et ses dépendances dynamiques sont contrôlées. Les règles Pop Shell tentent de laisser flotter les fenêtres Citrix connues. Le fonctionnement du portail de connexion, des certificats d’entreprise, du multimoniteur, du son, du microphone, des périphériques USB, de Teams et du partage d’écran nécessite des essais dans l’environnement Citrix concerné.

Le paquet Citrix est embarqué dans l’ISO privée, mais **n’est pas fourni dans ce dépôt**. Sa redistribution reste soumise aux conditions de Citrix. Aucun navigateur web n’est explicitement ajouté par le profil : prévoir celui requis par le mode d’accès de l’entreprise.

## Structure du dépôt

| Fichier | Rôle |
| --- | --- |
| `build-iso.sh` | Point d’entrée de construction |
| `scripts/build_iso.py` | Téléchargements, vérifications, saisie du mot de passe, assemblage de l’ISO |
| `scripts/iso_config.py` | Configuration Subiquity, modification GRUB, contrôles du contenu et de LUKS |
| `scripts/install-desktop.sh` | Installation dans la cible ; ne pas exécuter directement sur le poste de travail |
| `scripts/session_setup.py` | Configuration GDM, GNOME, raccourcis et compte utilisateur |
| `scripts/theme.py` | Application des palettes |
| `scripts/citrix_mode.py` | Sauvegarde et restauration des raccourcis locaux |
| `tests/test_scripts.py` | Tests unitaires, avec simulation des appels système concernés |
| `tests/check_sources.py` | Contrôle complémentaire d’archives et d’index Ubuntu déjà téléchargés |

## Tests et validation

Depuis la racine du dépôt, avec Python 3.12 ou ultérieur :

```bash
python3 -m unittest discover -s tests -v
bash -n build-iso.sh scripts/install-desktop.sh
python3 -m py_compile scripts/*.py tests/*.py
```

Les contrôles locaux effectués lors de la préparation initiale comprennent **18 tests unitaires réussis**, la syntaxe Bash/Python, la vérification des clés Pop Shell sur les sources épinglées, le rendu de **22 palettes avec appels GNOME simulés** et la présence de **49 noms de paquets** dans les index Noble AMD64. Ces résultats ne prouvent ni la résolution APT complète ni le bon fonctionnement graphique.

Le contrôle complémentaire `python3 tests/check_sources.py DOSSIER` attend dans ce dossier les archives `pop-shell.tar.gz` et `fedoriri.tar.gz` correspondant aux commits ci-dessous, ainsi que `main.xz` et `universe.xz`, index `Packages.xz` Noble AMD64 des composants correspondants. Il ne les télécharge pas.

Avant toute utilisation quotidienne, restent à valider :

- Construction de l’ISO dans Ubuntu 24.04 et installation complète avec accès réseau.
- Démarrage BIOS et UEFI ; **Secure Boot non validé**.
- Déverrouillage LUKS et connexion avec le compte prévu après retrait du média.
- Session réellement X11, Pop Shell chargé, réseau et audio opérationnels.
- Parcours Citrix réel et fonctions nécessaires au poste.

## Sources et maintenance

- [Ubuntu Server 24.04](https://releases.ubuntu.com/24.04/) et [documentation Subiquity](https://canonical-subiquity.readthedocs-hosted.com/en/latest/reference/autoinstall-reference.html).
- [Pop Shell](https://github.com/pop-os/shell), commit `7898b65c20735057faf0797f8ed056704ca55f0d`, issu de `master_noble`.
- [Fedoriri](https://github.com/tonybeyond/fedoriri), commit `4b76ab021d09daa22eb48c7e61928fa13700eaed`, pour les palettes et l’esprit du projet.
- [Omarchy](https://github.com/basecamp/omarchy), mention de licence récupérée depuis `v4.0.0`.

Les mentions de licence Fedoriri, Omarchy et les fichiers de licence présents dans Pop Shell sont conservés dans le contenu embarqué. Chaque composant tiers garde ses conditions d’utilisation.

Les commits Pop Shell et Fedoriri sont épinglés dans `scripts/build_iso.py`. En revanche, l’ISO Ubuntu retenue et les paquets APT suivent les versions disponibles : les constructions ne sont pas reproductibles à l’octet près. Toute évolution de GNOME, Pop Shell ou Citrix exige une nouvelle validation.
