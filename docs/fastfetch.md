# Fastfetch

System info with kitty image protocol. Config: `fastfetch/config.jsonc`.

## Files

| Path                | Purpose                      |
| ------------------- | ---------------------------- |
| `config.jsonc`      | Logo + display + module list |
| `png/`              | 4 anime logos                |
| `snaps/`            | Preview screenshot           |
| `PROTECTED`         | Empty marker file            |
| `config.jsonc.back` | Inactive backup              |

## Logo

```jsonc
"logo": {
    "type": "kitty",
    "source": "~/.config/fastfetch/png/Satoru_gojo.png",
    "width": 26,
    "height": 15
}
```

Requires kitty terminal for image rendering.
