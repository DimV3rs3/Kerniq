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

- `ToolPack.pack_id`, `name`, `create_tools(workspace, **kwargs)`
- Each `Tool` may define: `settings_schema`, `ui_icon`, `collapsible`, `chat_label`
- Loader: `Kerniq.tools.loader.load_all_tools` / `register_builtin_tools`

## Built-in packs

| pack_id | tools |
|---------|--------|
| filesystem | file_exists, read/write/create/edit/delete_file, list_directory, search_code, … |
| terminal | run_command |
| web | web_search, fetch_url |

## Compatibility

`from Kerniq.tools.filesystem import FileSystemTools` still works (shim).
