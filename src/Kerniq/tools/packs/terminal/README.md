# Terminal tool pack

One folder, one pack. `run_command` executes in the workspace shell. Absolute paths, UNC paths, `..`, and encoded commands are denied. A user refusal comes back as `USER_DENIED` for those exact arguments and must not be retried as a tool error.

This is not an operating-system sandbox. The process has the rights of the user who started Kerniq.
