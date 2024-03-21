# pylive

Static HTML page generator written in Python

(Yes, I want to rewrite it in Rust when I have more spare time left. ;-))

Basic principles are:

1. Blog-focused: Allow for writing new posts easily in Markdown format
2. Create pure static HTML pages that can be put everywhere
3. Allow users to fully personalize their website by using simple templates
4. Support for static files (that are not newly rendered every time)

Dislaimer: I wrote this generator to create a site that fits my needs. It might
not fit your needs but you are free to use this generator as a basis and add
your modifications.

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
[ -f requirements.txt ] && pip install -r requirements.txt
```
