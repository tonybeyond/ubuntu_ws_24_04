-- Greffons, installés et suivis par vim.pack.
--
-- Cinq, pas davantage : chacun couvre un besoin que Neovim ne remplit pas seul.
-- Le premier démarrage les clone, ce qui demande un accès réseau et prend
-- quelques secondes. Ensuite tout est local.
--
--   :lua vim.pack.update()                    met à jour, avec revue avant
--   :lua vim.pack.update(nil, {offline=true}) liste l'existant sans réseau

local gh = function(repo)
  return 'https://github.com/' .. repo
end

vim.pack.add({
  { src = gh('folke/tokyonight.nvim') },
  { src = gh('nvim-treesitter/nvim-treesitter'), version = 'main' },
  { src = gh('MeanderingProgrammer/render-markdown.nvim') },
  { src = gh('ibhagwan/fzf-lua') },
  { src = gh('lewis6991/gitsigns.nvim') },
})

-- Thème, accordé à la palette Tokyo Night du reste du profil.
require('tokyonight').setup({
  style = 'night',
  styles = { comments = { italic = true } },
})
vim.cmd.colorscheme('tokyonight-night')

-- Treesitter. Neovim livre déjà les analyseurs c, lua, vim, vimdoc, markdown
-- et markdown_inline : Markdown fonctionne sans rien installer. Les autres
-- sont récupérés une fois, au premier démarrage.
--
-- La branche main de nvim-treesitter expose install() et laisse le démarrage
-- de la coloration à vim.treesitter.start(). L'appel est protégé pour que la
-- configuration reste utilisable si l'API amont change.
-- Seuls les analyseurs absents sont demandés : après le premier démarrage,
-- cette liste est vide et l'appel ne coûte rien. Un échec de téléchargement
-- n'empêche pas Neovim de démarrer, la coloration retombe sur la syntaxe
-- classique de Vim pour le langage concerné.
local souhaites = { 'python', 'bash', 'json', 'yaml', 'toml', 'diff' }
local manquants = vim.tbl_filter(function(langue)
  return #vim.api.nvim_get_runtime_file('parser/' .. langue .. '.so', false) == 0
end, souhaites)

local ok_ts, ts = pcall(require, 'nvim-treesitter')
if #manquants > 0 and ok_ts and type(ts.install) == 'function' then
  pcall(ts.install, manquants)
end

vim.api.nvim_create_autocmd('FileType', {
  desc = 'Démarrer la coloration Treesitter quand un analyseur existe',
  group = vim.api.nvim_create_augroup('ubunturiri-treesitter', { clear = true }),
  pattern = { 'python', 'bash', 'sh', 'json', 'yaml', 'toml', 'markdown', 'lua', 'diff' },
  callback = function()
    pcall(vim.treesitter.start)
  end,
})

-- Rendu Markdown dans le tampon : titres, tableaux, blocs de code et cases à
-- cocher lisibles sans quitter l'éditeur. C'est la partie « de quoi lire ».
require('render-markdown').setup({
  completions = { lsp = { enabled = true } },
  heading = { sign = false },
  code = { sign = false, width = 'block', right_pad = 2 },
})

-- Sélecteur. fzf et ripgrep sont déjà installés par le profil, fzf-lua s'appuie
-- dessus plutôt que de réimplémenter la recherche.
require('fzf-lua').setup({
  'default',
  winopts = { height = 0.85, width = 0.85, preview = { layout = 'vertical' } },
})

-- Marques Git dans la colonne de signes, et navigation entre les blocs modifiés.
require('gitsigns').setup({
  signs = {
    add = { text = '+' },
    change = { text = '~' },
    delete = { text = '_' },
    topdelete = { text = '‾' },
    changedelete = { text = '~' },
  },
})
