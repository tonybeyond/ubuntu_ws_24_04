-- ruff, binaire épinglé par le profil.
--
-- Diagnostics et formatage Python. Beaucoup plus rapide que les greffons
-- équivalents de pylsp, d'où leur désactivation dans lsp/pylsp.lua.
return {
  cmd = { 'ruff', 'server' },
  filetypes = { 'python' },
  root_markers = { 'pyproject.toml', 'ruff.toml', '.ruff.toml', '.git' },
}
