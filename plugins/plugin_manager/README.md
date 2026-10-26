# Plugin manager

This plugin ships with Kerniq. It searches GitHub for other plugins, checks that a folder is a complete plugin, installs it, removes it, and shows when an installed copy is older than its source.

Search looks for the words you type plus `kerniq plugin` in the repository name, description, and README. A GitHub topic is not enough.

Its own tools are not offered to the model. Use the Plugins section in the Web UI, or `kerniq plugins check`, `kerniq plugins install`, `kerniq plugins updates`, and `kerniq plugins remove`.
