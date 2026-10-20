# Tool packs

Tools are grouped into **folder packs** under `src/Kerniq/tools/packs/<pack_id>/`.

## Layout

```
packs/filesystem/
  manifest.toml
  __init__.py      # class Pack(ToolPack)
  tools.py
  resources/       # optional assets
```

## Contract

- `ToolPack.pack_id`, `name`, `include_in_plan`, `create_tools(workspace, **kwargs)`
- Each `Tool` implements `settings_schema`, `apply_settings`, `display_phrase`, and `include_in_plan`
- `include_in_plan` is the Plan-mode switch. A pack value is the default for tools that do not choose. A saved per-tool setting wins. `update_plan` is always offered in Plan mode. New tools stay out until the flag is turned on.
- `display_phrase` is English text after the call count (`files read`, `commands`). Kerniq passes that text on. Packs and tools do not contain other languages and do not know which shell is showing them.
- Loader: `Kerniq.tools.loader.load_all_tools` / `register_builtin_tools`

## Built-in packs

| pack_id | include_in_plan | tools |
|---------|-----------------|--------|
| filesystem | no (readers opt in) | file_exists, read/write/create/edit/delete_file, list_directory, search_code, … |
| terminal | no | run_command |
| web | yes | web_search, fetch_url |
| plan | yes | update_plan |

## Compatibility

`from Kerniq.tools.filesystem import FileSystemTools` still works (shim).
