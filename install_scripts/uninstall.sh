# Remove all data that uv has stored
uv cache clean
rm -r "$(uv python dir)"
rm -r "$(uv tool dir)"
# Remove binaries
rm ~/.local/bin/uv ~/.local/bin/uvx
