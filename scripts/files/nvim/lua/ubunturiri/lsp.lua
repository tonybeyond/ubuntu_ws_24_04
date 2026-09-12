-- LSP, configuration native de Neovim 0.11 et suivantes.
--
-- Chaque serveur a son fichier dans lsp/ ; vim.lsp.enable() les active. Il n'y
-- a ni nvim-lspconfig ni Mason : les trois serveurs sont installés par le
-- profil, avec le reste du système.
--
--   pylsp     complétion, survol, définitions, renommage  (paquet Ubuntu)
--   ruff      diagnostics et formatage Python             (binaire épinglé)
--   marksman  liens, ancres et navigation Markdown        (binaire épinglé)

vim.lsp.enable({ 'pylsp', 'ruff', 'marksman' })

vim.diagnostic.config({
  severity_sort = true,
  update_in_insert = false,
  virtual_text = { current_line = true },
  signs = {
    text = {
      [vim.diagnostic.severity.ERROR] = '✘',
      [vim.diagnostic.severity.WARN] = '▲',
      [vim.diagnostic.severity.INFO] = '»',
      [vim.diagnostic.severity.HINT] = '›',
    },
  },
  float = { border = 'rounded', source = true },
})

vim.api.nvim_create_autocmd('LspAttach', {
  desc = 'Raccourcis et complétion une fois un serveur attaché',
  group = vim.api.nvim_create_augroup('ubunturiri-lsp', { clear = true }),
  callback = function(event)
    local client = vim.lsp.get_client_by_id(event.data.client_id)
    if not client then
      return
    end

    -- Complétion intégrée depuis Neovim 0.11 : aucun greffon de complétion
    -- n'est nécessaire. <C-y> valide, <C-e> referme.
    if client:supports_method('textDocument/completion') then
      pcall(vim.lsp.completion.enable, true, client.id, event.buf, { autotrigger = true })
    end

    -- Surlignage de l'occurrence sous le curseur, effacé au déplacement.
    if client:supports_method('textDocument/documentHighlight') then
      local groupe = vim.api.nvim_create_augroup('ubunturiri-lsp-highlight', { clear = false })
      vim.api.nvim_create_autocmd({ 'CursorHold', 'CursorHoldI' }, {
        buffer = event.buf,
        group = groupe,
        callback = vim.lsp.buf.document_highlight,
      })
      vim.api.nvim_create_autocmd({ 'CursorMoved', 'CursorMovedI' }, {
        buffer = event.buf,
        group = groupe,
        callback = vim.lsp.buf.clear_references,
      })
    end

    local map = function(touches, action, description)
      vim.keymap.set('n', touches, action, { buffer = event.buf, desc = 'LSP : ' .. description })
    end

    map('grd', vim.lsp.buf.definition, 'définition')
    map('grD', vim.lsp.buf.declaration, 'déclaration')
    map('gri', vim.lsp.buf.implementation, 'implémentation')
    map('grt', vim.lsp.buf.type_definition, 'type')
    map('K', vim.lsp.buf.hover, 'survol')
    map('<leader>cr', vim.lsp.buf.rename, 'renommer')
    map('<leader>ca', vim.lsp.buf.code_action, 'action de code')
    map('<leader>cf', function()
      vim.lsp.buf.format({ async = true })
    end, 'formater')
  end,
})
