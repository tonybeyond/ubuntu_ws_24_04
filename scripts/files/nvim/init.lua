-- Configuration Neovim du profil ubunturiri, dans l'esprit de kickstart.nvim :
-- courte, commentée, lisible d'un bout à l'autre, et faite pour être modifiée.
--
-- Deux choix structurants, permis par Neovim 0.12 et par rien avant :
--
--   Greffons — vim.pack, natif. Aucun code d'amorçage, aucun gestionnaire
--   tiers. L'état exact de chaque greffon est figé dans
--   ~/.config/nvim/nvim-pack-lock.json : le mettre sous gestion de version
--   avec le reste rend la configuration reproductible d'une machine à l'autre.
--   Mise à jour : :lua vim.pack.update()
--
--   LSP — configuration native. Un fichier par serveur dans lsp/, activé par
--   vim.lsp.enable(). Ni lazy.nvim ni nvim-lspconfig.
--
-- Les ajouts personnels vont dans ~/.config/nvim/lua/local.lua, chargé en fin
-- de fichier et jamais écrasé par une réapplication du profil.

vim.g.mapleader = ' '
vim.g.maplocalleader = ' '

require('ubunturiri.options')
require('ubunturiri.plugins')
require('ubunturiri.lsp')
require('ubunturiri.keymaps')

pcall(require, 'local')
