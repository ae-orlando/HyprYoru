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

- Wallpaper/theme changes signal Kitty with `SIGUSR1` once after the coordinated palette publish. Matugen's `post_hook` still handles direct Matugen runs.
- `fastfetch/config.jsonc` logo type `kitty` requires kitty image protocol.
