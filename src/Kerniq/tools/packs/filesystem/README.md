# Filesystem tool pack

One folder, one pack. Discovered from `src/Kerniq/tools/packs/`. The tools read and write files inside the workspace: `read_file`, `write_file`, `create_file`, `edit_file`, `delete_file`, `move_file`, `list_directory`, `create_directory`, `file_exists`, `get_file_info`, `search_code`, `view_image`, `zip`, and `unzip`.

`view_image` is offered only when the selected model (or the model that would be picked automatically) reports that it can see images. It sends a PNG, JPEG, GIF, WEBP, or BMP as a picture. `read_file` does not dump the bytes of those files.

Paths outside the workspace and symlink escapes are denied. Risk is declared on each tool and goes through the approval broker. `kerniq tools list` prints the tools that are actually loaded.
