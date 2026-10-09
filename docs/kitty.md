# Kitty

Terminal. Config: `kitty/kitty.conf`. Theme line:

```text
include themes/Matugen.conf
```

## Files

| Path                  | Purpose                          |
| --------------------- | -------------------------------- |
| `kitty.conf`          | Fonts, cursor, tabs, keybindings |
| `themes/Matugen.conf` | Generated palette (matugen)      |
| `kitty.conf.bak`      | Local backup, not active         |

## Notes

- Matugen `post_hook` sends `SIGUSR1` to kitty on palette change.
- `fastfetch/config.jsonc` logo type `kitty` requires kitty image protocol.
