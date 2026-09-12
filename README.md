# ubunturiri

Scripts de préparation d’une ISO personnelle Ubuntu Server 24.04 LTS AMD64 avec **GNOME sous X11, Pop Shell et Citrix Workspace** : **ubunturiri**.

Le projet conserve une base serveur minimale, le pavage des fenêtres, les palettes adaptées et un profil de raccourcis pour Citrix. Il repose sur Ubuntu et GNOME Xorg. Shadow.tech n’est pas intégré.

S’y ajoute une couche applicative : Ghostty, Neovim, LibreOffice francisé, NetBird, Brave Origin, et un shell bash monté comme l’environnement zsh de référence sous macOS — Starship, ble.sh, eza, zoxide, fzf. Voir [Applications et shell](#applications-et-shell).

> **État.** L’ISO se construit, s’installe jusqu’au bout et le poste démarre sur un bureau configuré : validé en VM AMD64 avec chiffrement LUKS. Restent non validés : **le parcours Citrix réel**, le **Secure Boot**, le multimoniteur, et le comportement sur matériel physique. `ubunturiri-doctor` contrôle après installation ce que le profil prétend avoir fait. Ne pas utiliser sur un disque contenant des données sans sauvegarde.

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
| Applications | Ghostty, Neovim, LibreOffice, NetBird, Brave Origin, Starship, ble.sh |
| Shell | bash avec Starship, ble.sh, eza, zoxide, fzf, fastfetch, aria2 |
| Sécurité | Racine LUKS exigée, connexion automatique désactivée, pas de serveur SSH installé par ce profil |

L’installation GNOME utilise des paquets sélectionnés avec `--no-install-recommends`, et non le métapaquet Ubuntu Desktop complet. Des outils de compilation restent installés pour Pop Shell. Il ne s’agit pas d’une adaptation du projet original, ni d’une ISO live de bureau préconfiguré.

## Prérequis

- Une machine ou VM **Ubuntu 24.04**, de préférence AMD64, pour construire. Un CT Ubuntu 24.04 dédié convient aussi pour préparer l’ISO. Le script refuse macOS et les autres distributions ; root est refusé par défaut, sauf avec `--allow-root`.
- Python **3.12 ou ultérieur** et les outils indiqués ci-dessous.
- Espace disque suffisant pour les fichiers temporaires et l'ISO finale. Le script vérifie dynamiquement après téléchargement de l'ISO Ubuntu et préparation du contenu (source + 2× payload + marge de 5% ou 512 Mio minimum). Les téléchargements sont repris en cas d'interruption (HTTP Range) ; une ISO partiellement téléchargée dans le cache n'est pas effacée et peut être complétée.
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

Remplacer le chemin du DEB par celui du fichier officiel téléchargé. Sur un poste classique, lancer `build-iso.sh` sans `sudo`.

### Construction en root dans un CT dédié

Depuis le dépôt déjà cloné, avec les dépendances installées :

```bash
git pull --ff-only
bash build-iso.sh --allow-root --check
bash build-iso.sh --allow-root --citrix-deb "/chemin/vers/icaclient_amd64.deb"
```

`--allow-root` autorise uniquement l’utilisateur root : les contrôles Ubuntu 24.04, Python et dépendances restent actifs. L’option ne détecte pas automatiquement un conteneur et ne l’isole pas davantage ; réserver son utilisation à un environnement dédié, sans montage de dossiers sensibles de l’hôte. Le compte créé dans le système installé reste `ubunturiri`, sauf option `--username`.

Le CT sert à préparer l’ISO. Le démarrage, l’installation chiffrée et le bureau doivent être validés dans une VM ou sur une machine de test.

### Déroulement de la construction

Le script télécharge les sources épinglées et l'ISO Ubuntu courante de la série 24.04, vérifie la signature du manifeste Ubuntu et son SHA-256. Il demande ensuite le nom d'utilisateur (défaut : ubunturiri) : appuyer sur Entrée pour accepter ou saisir un autre nom valide. Après la préparation des sources, le mot de passe utilisateur est demandé deux fois, sans l'afficher. Le mot de passe doit comporter au moins 8 caractères.

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

#### Téléchargements et cache

Les sources et l'ISO Ubuntu sont conservées dans `.cache/` à la racine du projet. En cas d'interruption (Ctrl+C, délai d'attente, erreur réseau), les fichiers partiellement téléchargés restent en place avec l'extension `.part`. Un nouveau lancement du script reprend le téléchargement à partir du dernier octet reçu, grâce au support HTTP Range. Si le serveur refuse la reprise (réponse 416 ou absence de Range), le fichier est retéléchargé en intégralité. Le cache n'est pas effacé automatiquement après la construction : le réutiliser pour plusieurs ISO réduit la consommation réseau.

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
| `Super + Entrée` | Ouvrir Ghostty, ou `gnome-terminal` en repli s’il est absent |
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

La police monospace de GNOME est réglée sur `JetBrainsMono Nerd Font Mono 11` ; les palettes `ubunturiri-theme-set` ne modifient pas la configuration Ghostty, qui a son propre thème dans `~/.config/ghostty/config`.

## Applications et shell

### Ce qui vient des dépôts Ubuntu

LibreOffice 24.2 (Writer, Calc, Impress, Draw, intégration GTK3), sa localisation française, `hunspell-fr`, `mythes-fr` et `hyphen-fr`, plus `eza`, `zoxide`, `fzf`, `ripgrep`, `fd-find`, `bat`, `jq`, `tmux` et `aria2`. Tous suivis par la sécurité Ubuntu, tous installés avec `--no-install-recommends`. Les noms sont déclarés dans `scripts/packages.py` et contrôlés contre les index Noble AMD64 par `tests/check_sources.py`.

Deux noms diffèrent de macOS : Ubuntu livre `bat` sous le binaire `batcat` et `fd-find` sous `fdfind`. Le bashrc fourni pose les alias correspondants.

### Composants épinglés, absents des dépôts Ubuntu

| Composant | Version | Raison |
| --- | --- | --- |
| Ghostty | 1.3.1~ppa2-noble1 | absent d'Ubuntu ; DEB du PPA `mkasberg/ghostty-ubuntu`, série noble |
| NetBird et NetBird UI | 0.78.1 | absent d'Ubuntu ; DEB de `pkgs.netbird.io` |
| Neovim | 0.12.5 | noble ne fournit que 0.9.5, sous le minimum de lazy.nvim et LazyVim |
| Starship | 1.25.1 | absent de tous les dépôts Ubuntu 24.04 |
| ble.sh | 0.4.0-devel3 | équivalent bash de zsh-autosuggestions et zsh-syntax-highlighting |
| fastfetch | 2.64.2 | absent de noble ; `neofetch` y est présent mais n'est plus maintenu |
| JetBrainsMono Nerd Font | 3.5.1 | `fonts-jetbrains-mono` de noble n'a pas les glyphes exigés par Starship |

Chacun est téléchargé **à la construction**, vérifié contre le SHA-256 déclaré dans `scripts/packages.py`, puis embarqué dans l'ISO et couvert par le manifeste existant. Aucun dépôt tiers n'est ajouté au système installé pour ces composants. En contrepartie ils ne reçoivent **pas de mise à jour automatique** : il faut relever les versions dans `packages.py` et reconstruire.

Ces empreintes sont une confiance à la première utilisation : elles figent ce qui a été téléchargé le jour du relevé, elles ne valident pas une signature amont, contrairement à l'ISO Ubuntu vérifiée par `gpgv`. Pour ghostty et NetBird, l'empreinte épinglée est identique au champ `SHA256` de l'index `Packages` publié par chaque dépôt.

Pour changer de version :

```bash
# modifier url et version dans scripts/packages.py, puis
python3 scripts/refresh_pins.py          # signale les écarts sans rien modifier
python3 scripts/refresh_pins.py --write  # réécrit les champs sha256
git diff scripts/packages.py
```

### Brave Origin : le seul dépôt tiers ajouté

Le paquet `brave-origin` dépend de `brave-keyring`, qui installe lui-même la clé du dépôt Brave : le dépôt finit configuré de toute façon, et un navigateur sans mise à jour automatique est un risque plus grand que l'ancre de confiance ajoutée. Le profil pose donc la clé depuis le contenu embarqué, écrit `/etc/apt/sources.list.d/brave-browser.sources` au format deb822 avec `Signed-By`, puis installe `brave-origin` depuis `https://brave-browser-apt-release.s3.brave.com`. La clé embarquée est octet pour octet celle du paquet `brave-keyring`.

Le binaire s'appelle `brave-origin-stable` ; le lanceur est `brave-origin.desktop`.

### NetBird

Le service `netbird.service` est activé mais **le poste n'est enrôlé dans aucun réseau** : aucune clé n'est embarquée dans l'ISO. Après le premier démarrage :

```bash
sudo netbird up --setup-key <CLÉ>
netbird status --detail
```

### Réseau : rendu netplan et attente au démarrage

Le profil bascule le rendu netplan vers NetworkManager, qui gère alors toutes les interfaces. `systemd-networkd` n'a plus rien à configurer, mais la base Ubuntu Server laisse `systemd-networkd-wait-online.service` activé : il attend un lien qui n'arrivera jamais et **retarde chaque démarrage jusqu'à son délai d'attente**, avec un `Job systemd-networkd-wait-online.service/start running` visible à l'écran.

`session_setup.py` masque donc cette unité et active `NetworkManager-wait-online.service` à la place. `systemd-networkd` lui-même n'est pas touché : seule l'attente est retirée.

Sur une machine déjà installée avec une ISO antérieure au correctif :

```bash
sudo systemctl mask systemd-networkd-wait-online.service
sudo systemctl enable NetworkManager-wait-online.service
```

### Diagnostic d'une installation qui échoue

`install-desktop.sh` annonce chaque étape et duplique toute sa sortie dans `/var/log/ubunturiri-install.log`, **à l'intérieur de la cible**. Un `trap ERR` nomme la ligne, la commande et le code de retour. Sans cela, Subiquity n'affiche qu'un rapport de plantage et la sortie réelle part dans le journal du système *live*, sous un identifiant `subiquity_log.<pid>`.

Depuis l'installateur, pendant que la cible est encore montée :

```bash
sudo tail -n 60 /target/var/log/ubunturiri-install.log
```

Après redémarrage, le même fichier est en `/var/log/ubunturiri-install.log`. Les recours d'origine restent valables :

```bash
sudo journalctl -t subiquity_log.<pid> --no-pager -o cat | tail -60
sudo tail -n 80 /var/log/installer/curtin-install.log
```

Si l'installation s'arrête en cours de route, GNOME peut quand même démarrer : le paquet `gdm3` s'active de lui-même. Ce n'est pas le signe d'une installation réussie — la configuration de session, Pop Shell, les raccourcis et le shell sont posés par les toutes dernières étapes du script.

#### Polices : ne pas contrôler via le cache fontconfig

Le contrôle `fc-list | grep` échouait dans le chroot de l'installateur alors que les polices étaient correctement extraites, et arrêtait l'installation juste après Starship. La vérification lit désormais la famille directement dans le fichier avec `fc-scan`, sans dépendre du cache ni de la configuration de fontconfig, et `fc-cache` n'est plus bloquant : fontconfig indexe le répertoire à l'ouverture de session.

### Shell

`scripts/files/bashrc` est le portage bash du `.zshrc` macOS : mêmes alias de navigation, de git, de `ls` vers `eza`, mêmes options fzf, même bascule `EDITOR` selon `SSH_CONNECTION`. Les équivalences :

| macOS, zsh | Ubuntu, bash |
| --- | --- |
| oh-my-zsh, plugin `z` | `zoxide` |
| `zsh-autosuggestions`, `zsh-syntax-highlighting` | `ble.sh` |
| `ENABLE_CORRECTION` | `shopt -s autocd cdspell dirspell` |
| alias `brew` (`bud`, `bug`, `bcu`) | `upcheck`, `upall`, `cleanup` sur APT |
| `flushdns` via `dscacheutil` | `resolvectl flush-caches` |
| `free` via `top -l 1` | `free -h` natif |

`ble.sh` doit être chargé en premier avec `--noattach` et rattaché par `ble-attach` en toute dernière instruction ; Starship s'initialise entre les deux. Lorsque bash est lancé avec `-c`, `ble.sh` renvoie 1 sans message : le bashrc teste donc le code de retour avant d'appeler `bleopt` et `ble-face`, sans quoi chaque shell non interactif affiche deux `command not found`.

Les ajouts personnels vont dans `~/.bashrc.local`, chargé en fin de fichier et préservé si le profil est réappliqué. Le `.bashrc` d'origine d'Ubuntu est sauvegardé en `~/.bashrc.ubuntu-origine`.

Le locale reste `fr_CH.UTF-8` ; le `export LC_ALL=en_US.UTF-8` du `.zshrc` macOS n'est pas repris, `en_US.UTF-8` n'étant pas générée par ce profil.

### Ghostty et terminfo sur les hôtes distants

`TERM=xterm-ghostty` n'existe pas dans la base terminfo des serveurs, ce qui casse `nano` et les retours chariot en SSH. La configuration fournie active `shell-integration-features = ssh-env,ssh-terminfo` : Ghostty bascule sur `xterm-256color` et tente d'installer son entrée terminfo sur l'hôte distant via `infocmp` et `tic`. Option disponible depuis Ghostty 1.2.0, documentée dans `ghostty(5)` livré avec le paquet.

## Contrôler le poste après installation

```bash
ubunturiri-doctor          # tous les contrôles
ubunturiri-doctor --quiet  # seulement ce qui ne va pas
```

Sort en 0 si tout passe, en 1 sinon, et chaque échec dit quoi faire. Les contrôles couvrent la session X11 et la configuration GDM, Pop Shell installé **et** activé, le rendu netplan et l’attente réseau, la police Nerd Font, Starship et ble.sh dans le compte, les versions des applications, le dictionnaire français, les trois serveurs LSP, les greffons Neovim verrouillés, les mises à jour automatiques, et les alertes du journal d’installation.

Cette commande existe pour une raison précise : une installation peut s’arrêter en cours de route sans que rien ne le montre. Le paquet `gdm3` s’active de lui-même, un bureau apparaît, et les dernières étapes du profil n’ont pourtant jamais tourné. Un bureau qui s’affiche ne prouve rien.

## Neovim

Configuration modulaire dans `~/.config/nvim`, dans l’esprit de [kickstart.nvim](https://github.com/nvim-lua/kickstart.nvim) : courte, commentée, faite pour être modifiée. Deux choix que seul Neovim 0.12 permet.

**Greffons : `vim.pack`, natif.** Aucun code d’amorçage, ni `lazy.nvim` ni `packer`. L’état exact de chaque greffon est figé dans `~/.config/nvim/nvim-pack-lock.json` : le mettre sous gestion de version rend la configuration reproductible d’une machine à l’autre.

```vim
:lua vim.pack.update()                      " mise à jour, avec revue avant application
:lua vim.pack.update(nil, {offline = true}) " lister l'existant, sans réseau
```

**LSP : configuration native.** Un fichier par serveur dans `~/.config/nvim/lsp/`, activé par `vim.lsp.enable()`. Ni `nvim-lspconfig` ni Mason : les trois serveurs sont installés avec le système. La complétion vient de `vim.lsp.completion`, intégrée depuis 0.11 — aucun greffon de complétion.

| Serveur | Rôle | Provenance |
| --- | --- | --- |
| `pylsp` | complétion, survol, définitions, renommage Python | paquet Ubuntu `python3-pylsp` |
| `ruff` | diagnostics et formatage Python | binaire épinglé 0.16.6 |
| `marksman` | liens, ancres et navigation Markdown | binaire épinglé 2026-02-08 |

Les greffons de lint de `pylsp` sont désactivés dans `lsp/pylsp.lua` : ruff s’en charge, et les laisser produirait des diagnostics en double.

Cinq greffons, pas davantage : `tokyonight.nvim` pour rester accordé au reste du profil, `nvim-treesitter`, `render-markdown.nvim` pour lire du Markdown mis en forme dans le tampon, `fzf-lua` qui s’appuie sur les `fzf` et `ripgrep` déjà installés, et `gitsigns.nvim`.

Neovim livre déjà les analyseurs Treesitter `markdown` et `markdown_inline` : le Markdown fonctionne sans rien télécharger. Les analyseurs Python, Bash, JSON, YAML et TOML sont récupérés au premier démarrage, ce qui **demande un accès réseau**. En cas d’échec, Neovim démarre quand même et la coloration retombe sur la syntaxe classique pour ces langages.

Les ajouts personnels vont dans `~/.config/nvim/lua/local.lua`, chargé en fin d’`init.lua` et jamais écrasé par une réapplication du profil.

Raccourcis ajoutés par le profil, en plus de ceux de Neovim (`grn`, `gra`, `grr`, `gO`) :

| Raccourci | Action |
| --- | --- |
| `<Espace><Espace>` | Ouvrir un fichier |
| `<Espace>fg` | Rechercher dans les fichiers |
| `<Espace>fd` `<Espace>fs` | Diagnostics, symboles du tampon |
| `<Espace>cf` `<Espace>cr` `<Espace>ca` | Formater, renommer, action de code |
| `<Espace>mr` | Markdown : basculer le rendu |
| `grd` `gri` `K` | Définition, implémentation, survol |

## Maintenance et empreinte disque

**Mises à jour de sécurité automatiques.** `unattended-upgrades` est installé et actif, sur les origines de sécurité Ubuntu **et** sur `Brave Software:stable` — sans quoi le navigateur, principale surface exposée du poste, ne serait pas couvert. Le redémarrage automatique est désactivé.

**Purge du contenu embarqué.** Une fois tout installé, les paquets, archives et sources embarqués ne servent plus : ils sont supprimés de `/opt/ubunturiri` en fin d’installation, soit environ 175 Mio rendus au disque. Restent les scripts Python, `themes/` que lit `theme.py` à chaque ouverture de session, et `files/`. Contrepartie assumée : une réinstallation hors ligne depuis ces paquets n’est plus possible, il faut repartir de l’ISO.

## Citrix : installation et limites

Le script vérifie le nom `icaclient` et l’architecture `amd64` du DEB, puis laisse APT résoudre ses dépendances dans Ubuntu 24.04. Ce contrôle n’authentifie pas le fournisseur du DEB : utiliser uniquement le téléchargement officiel. Aucun dépôt d’une autre version Ubuntu ni faux lien de bibliothèque n’est ajouté.

La présence du binaire `wfica` et ses dépendances dynamiques sont contrôlées. Les règles Pop Shell tentent de laisser flotter les fenêtres Citrix connues. Le fonctionnement du portail de connexion, des certificats d’entreprise, du multimoniteur, du son, du microphone, des périphériques USB, de Teams et du partage d’écran nécessite des essais dans l’environnement Citrix concerné.

Le paquet Citrix est embarqué dans l’ISO privée, mais **n’est pas fourni dans ce dépôt**. Sa redistribution reste soumise aux conditions de Citrix. Le profil installe Brave Origin comme navigateur ; si le mode d’accès de l’entreprise exige un navigateur précis, l’ajouter séparément.

## Structure du dépôt

| Fichier | Rôle |
| --- | --- |
| `build-iso.sh` | Point d’entrée de construction |
| `scripts/build_iso.py` | Téléchargements, vérifications, saisie du mot de passe, assemblage de l’ISO |
| `scripts/packages.py` | Listes de paquets APT, composants épinglés par URL et SHA-256, dépôt Brave |
| `scripts/refresh_pins.py` | Recalcul des empreintes après un changement de version |
| `scripts/shell_setup.py` | Pose du bashrc, de starship.toml et de la configuration Ghostty |
| `scripts/doctor.py` | Contrôle post-installation, exposé sous `ubunturiri-doctor` |
| `scripts/files/` | bashrc, starship.toml, configuration Ghostty et arborescence Neovim |
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

Les contrôles locaux comprennent **77 tests unitaires réussis**, la syntaxe Bash/Python, la vérification des clés Pop Shell sur les sources épinglées, le rendu de **22 palettes avec appels GNOME simulés** et la présence de **71 noms de paquets** dans les index Noble AMD64. Ces résultats ne prouvent ni la résolution APT complète ni le bon fonctionnement graphique.

Contrôles supplémentaires de cette itération : la configuration Neovim a été exécutée par le **vrai Neovim 0.12.5 épinglé**, en mode headless, réseau ouvert — les cinq greffons s'installent, `pylsp` et `ruff` s'attachent à un fichier Python et remontent des diagnostics, `marksman` et `render-markdown` s'attachent à un fichier Markdown dont l'analyseur Treesitter démarre, le thème se charge. Le téléchargement des analyseurs Treesitter supplémentaires **n'a pas pu être vérifié** : le réseau de l'environnement de développement refuse `codeload.github.com` en HTTP 403. `ubunturiri-doctor` a été exécuté sur un système partiellement équipé et rend bien compte de l'état réel.

Contrôles supplémentaires effectués sur les composants ajoutés, hors ISO : téléchargement réel des 9 composants épinglés et correspondance de leurs SHA-256, préparation complète du contenu embarqué avec `verify_payload` (122 fichiers, 72,6 Mio), rejeu des commandes d'extraction `tar` de `install-desktop.sh`, validation de `starship.toml` par le binaire Starship 1.25.1 sans avertissement, contrôle de chaque clé de la configuration Ghostty contre `ghostty(5)` livré dans le paquet, et chargement du bashrc dans un bash interactif réel avec `ble.sh` rattaché. **L'installation dans une cible Ubuntu 24.04 reste à valider.**

Le contrôle complémentaire `python3 tests/check_sources.py DOSSIER` attend dans ce dossier les archives `pop-shell.tar.gz` et `fedoriri.tar.gz` correspondant aux commits ci-dessous, ainsi que `main.xz` et `universe.xz`, index `Packages.xz` Noble AMD64 des composants correspondants. Il ne les télécharge pas.

Avant toute utilisation quotidienne, restent à valider :

- Construction de l’ISO dans Ubuntu 24.04 et installation complète avec accès réseau.
- Démarrage BIOS et UEFI ; **Secure Boot non validé**.
- Déverrouillage LUKS et connexion avec le compte prévu après retrait du média.
- Session réellement X11, Pop Shell chargé, réseau et audio opérationnels.
- Parcours Citrix réel et fonctions nécessaires au poste.
- Résolution APT réelle des paquets ajoutés, notamment `brave-origin` dont la dépendance `libasound2` est satisfaite dans noble par le `Provides` versionné de `libasound2t64`.
- Rendu des glyphes Nerd Font dans Ghostty et GNOME Terminal, prompt Starship complet, autosuggestions ble.sh sur le matériel réel.
- Enrôlement NetBird et accès au réseau superposé.
- Chaîne `ssh-terminfo` de Ghostty contre un hôte distant sans entrée `xterm-ghostty`.

## Sources et maintenance

- [Ubuntu Server 24.04](https://releases.ubuntu.com/24.04/) et [documentation Subiquity](https://canonical-subiquity.readthedocs-hosted.com/en/latest/reference/autoinstall-reference.html).
- [Pop Shell](https://github.com/pop-os/shell), commit `7898b65c20735057faf0797f8ed056704ca55f0d`, issu de `master_noble`.
- [Fedoriri](https://github.com/tonybeyond/fedoriri), commit `4b76ab021d09daa22eb48c7e61928fa13700eaed`, pour les palettes et l’esprit du projet.
- [Omarchy](https://github.com/basecamp/omarchy), mention de licence récupérée depuis `v4.0.0`.

Les mentions de licence Fedoriri, Omarchy et les fichiers de licence présents dans Pop Shell sont conservés dans le contenu embarqué. Chaque composant tiers garde ses conditions d’utilisation.

Les commits Pop Shell et Fedoriri sont épinglés dans `scripts/build_iso.py`. En revanche, l’ISO Ubuntu retenue et les paquets APT suivent les versions disponibles : les constructions ne sont pas reproductibles à l’octet près. Toute évolution de GNOME, Pop Shell ou Citrix exige une nouvelle validation.
