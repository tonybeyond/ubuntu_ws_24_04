-- python-lsp-server, paquet Ubuntu python3-pylsp.
--
-- Il apporte la complétion, le survol, les définitions et le renommage via
-- Jedi. Les greffons de lint et de formatage sont coupés : ruff s'en occupe,
-- et les laisser produirait des diagnostics en double.
return {
  cmd = { 'pylsp' },
  filetypes = { 'python' },
  root_markers = { 'pyproject.toml', 'setup.py', 'setup.cfg', 'requirements.txt', '.git' },
  settings = {
    pylsp = {
      plugins = {
        pycodestyle = { enabled = false },
        pyflakes = { enabled = false },
        mccabe = { enabled = false },
        autopep8 = { enabled = false },
        yapf = { enabled = false },
        jedi_completion = { enabled = true, include_params = true },
        jedi_hover = { enabled = true },
        jedi_definition = { enabled = true, follow_imports = true },
        jedi_references = { enabled = true },
        jedi_signature_help = { enabled = true },
        jedi_symbols = { enabled = true, all_scopes = false },
        rope_autoimport = { enabled = false },
      },
    },
  },
}
