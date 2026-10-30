# Fastfetch

System info with kitty image protocol. Config: `fastfetch/config.jsonc`.

## Files

| Path                | Purpose                      |
| ------------------- | ---------------------------- |
| `config.jsonc`      | Logo + display + module list |
| `png/`              | 12 logos                     |

## Logo

```jsonc
"logo": {
    "source": "~/.config/fastfetch/png/nobara-brown.png",
    "type": "auto",
    "width": 18,
    "padding": {
        "top": 1,
        "right": 3,
        "left": 1
    }
}
```

`type: "auto"` detects the best image protocol for the terminal; no kitty-specific setting is required.
