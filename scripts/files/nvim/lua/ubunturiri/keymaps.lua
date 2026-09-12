-- Raccourcis. <leader> est l'espace.
--
-- Ce qui vient de Neovim n'est pas redéfini : grn, gra, grr et gO existent
-- déjà en standard. Seul ce que le profil ajoute figure ici.

local map = function(mode, touches, action, description)
  vim.keymap.set(mode, touches, action, { desc = description })
end

-- Effacer le surlignage de recherche.
map('n', '<Esc>', '<cmd>nohlsearch<CR>', 'Effacer le surlignage')

-- Recherche, avec fzf-lua. Les quatre qui servent vraiment.
map('n', '<leader><leader>', '<cmd>FzfLua files<CR>', 'Fichiers')
map('n', '<leader>fg', '<cmd>FzfLua live_grep<CR>', 'Rechercher dans les fichiers')
map('n', '<leader>fb', '<cmd>FzfLua buffers<CR>', 'Tampons ouverts')
map('n', '<leader>fh', '<cmd>FzfLua helptags<CR>', 'Aide')
map('n', '<leader>fd', '<cmd>FzfLua diagnostics_document<CR>', 'Diagnostics du tampon')
map('n', '<leader>fs', '<cmd>FzfLua lsp_document_symbols<CR>', 'Symboles du tampon')

-- Diagnostics.
map('n', '<leader>cd', vim.diagnostic.open_float, 'Diagnostic sous le curseur')
map('n', '<leader>cq', vim.diagnostic.setloclist, 'Diagnostics dans la liste')

-- Markdown : basculer le rendu dans le tampon.
map('n', '<leader>mr', '<cmd>RenderMarkdown toggle<CR>', 'Markdown : rendu')

-- Déplacement entre fenêtres sans passer par <C-w>.
map('n', '<C-h>', '<C-w><C-h>', 'Fenêtre à gauche')
map('n', '<C-l>', '<C-w><C-l>', 'Fenêtre à droite')
map('n', '<C-j>', '<C-w><C-j>', 'Fenêtre en bas')
map('n', '<C-k>', '<C-w><C-k>', 'Fenêtre en haut')

-- Garder la sélection après indentation.
map('v', '<', '<gv', 'Désindenter')
map('v', '>', '>gv', 'Indenter')

-- Déplacer les lignes sélectionnées.
map('v', 'J', ":m '>+1<CR>gv=gv", 'Descendre la sélection')
map('v', 'K', ":m '<-2<CR>gv=gv", 'Monter la sélection')
