-- Options de base. Rien d'exotique : de quoi lire du texte long et écrire du
-- Python sans se battre avec les réglages par défaut de Vim.

local o = vim.opt

-- Repères
o.number = true
o.relativenumber = true
o.cursorline = true
o.signcolumn = 'yes'
o.colorcolumn = '88'
o.scrolloff = 8
o.sidescrolloff = 8

-- Recherche
o.ignorecase = true
o.smartcase = true
o.inccommand = 'split'
o.hlsearch = true

-- Indentation. 4 espaces conviennent à Python ; les autres langages sont
-- réglés par leur ftplugin ou par editorconfig.
o.expandtab = true
o.shiftwidth = 4
o.tabstop = 4
o.softtabstop = 4
o.smartindent = true

-- Lecture de texte long : retour à la ligne sur les mots, pas au milieu.
o.wrap = false
o.linebreak = true
o.breakindent = true

-- Fichiers. Pas de .swp ni de sauvegarde, mais un historique d'annulation
-- persistant, plus utile et moins encombrant.
o.swapfile = false
o.backup = false
o.undofile = true

-- Interface
o.termguicolors = true
o.splitright = true
o.splitbelow = true
o.showmode = false
o.mouse = 'a'
o.confirm = true
o.updatetime = 250
o.timeoutlen = 400

-- Presse-papier système. schedule() évite de ralentir le démarrage, le temps
-- que le fournisseur soit détecté.
vim.schedule(function()
  o.clipboard = 'unnamedplus'
end)

-- Caractères invisibles, utiles pour repérer les espaces en fin de ligne dans
-- du Markdown, où deux espaces changent le rendu.
o.list = true
o.listchars = { tab = '» ', trail = '·', nbsp = '␣' }

-- Surligner brièvement ce qui vient d'être copié.
vim.api.nvim_create_autocmd('TextYankPost', {
  desc = 'Surligner le texte copié',
  group = vim.api.nvim_create_augroup('ubunturiri-yank', { clear = true }),
  callback = function()
    vim.hl.on_yank()
  end,
})

-- Markdown et texte : ici le retour à la ligne visuel est souhaitable, et la
-- correction orthographique française a son intérêt.
vim.api.nvim_create_autocmd('FileType', {
  desc = 'Réglages de lecture pour les formats de texte',
  group = vim.api.nvim_create_augroup('ubunturiri-prose', { clear = true }),
  pattern = { 'markdown', 'text', 'gitcommit' },
  callback = function()
    vim.opt_local.wrap = true
    vim.opt_local.spell = true
    vim.opt_local.spelllang = { 'fr', 'en' }
    vim.opt_local.colorcolumn = ''
  end,
})
