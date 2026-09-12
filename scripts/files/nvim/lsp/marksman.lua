-- marksman, binaire épinglé par le profil.
--
-- Navigation dans un ensemble de notes Markdown : suivi des liens, complétion
-- des références et des ancres, symboles de document, liens cassés signalés.
return {
  cmd = { 'marksman', 'server' },
  filetypes = { 'markdown', 'markdown.mdx' },
  root_markers = { '.marksman.toml', '.git' },
}
