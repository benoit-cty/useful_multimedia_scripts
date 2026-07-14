# useful_multimedia_scripts
Repo of scripts I made and use to deal with my pictures and videos

## Rename and classify pictures

Install the picture-renaming command once with `uv`:

	uv tool install --editable /home/benoit/dev/useful_multimedia_scripts

Ensure `~/.local/bin` is in `PATH` (the `uv` installer reports the exact
command if it is not). It can then be run from any photo directory:

	rename-and-classify-pictures . "Holiday"

The command previews changes by default. JPEGs with matching RAW files are
placed in `jpg` and `raw`; unpaired JPEGs are placed in `jpg_only`; supported
videos (such as MP4, MOV, MKV, and AVI) are placed in `videos`. Add `--modify`
after the name to actually move and rename the files:

	rename-and-classify-pictures . "Holiday" --modify

The editable installation means changes made in this repository are used
immediately; `uv` also manages the required Pillow dependency.
