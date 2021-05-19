### AS.050.625: A Grammar for Catalan Adjective Inflections

The repo is organized as follows. At the top level there's an interface to the corpus. Other components of the project are divided into directories:

[data](data) houses:
  - The large corpus, divided into orthographic and phonetic transcriptions, and further divided into `all` and `adj`.
  - A smaller corpus in a single orth/phon file.
  - Two directories, `map` and `pre`, which supply `epitran` with a grapheme-to-phoneme map and a set of rules to be applied in the course of mapping. Although note that rule application during transcription is currently disabled.

[lib](lib) contains any modifications to third party libraries, currently only `epitran`.

[util](util) contains rudimentary utilities for sorting files output by the grammar.

[grammar](grammar) has the grammar, divided into:
  - [grammar/big-grammar](big-grammar)
  - [grammar/small-grammar](small-grammar)
  - `features.foma`, `phonemes.foma`, and `test.grammar.foma`


To start from scratch, assuming you're on osx, install the python dependencies and foma:
```bash
pip install -r requirements.txt
brew install foma
```

Additions to the [grammar/big-grammar](big-grammar) can then be tested by running
```bash
foma -f test.grammar.foma
```

To regenerate the `features.foma`, UR, and SR lexicons that the grammar depends on, use the corpus interface:

#### python -m corpus
```bash
usage: corpus.py [-h] [-features] [-feature-defs] [-phoneme-defs] [-ur-lexicon] [-sr-lexicon] [-alphabet] [--small] [--syll]
                 [--stress]

Corpus utilities.

optional arguments:
  -h, --help     show this help message and exit
  -features      Print feature keys.
  -feature-defs  Print formatted feature definitions.
  -phoneme-defs  Print formatted phoneme definitions.
  -ur-lexicon    Print the UR lexicon.
  -sr-lexicon    Print the UR-to-SR lexicon.
  -alphabet      Print the alphabet.
  --small        Operate on the small lexicon (by default on the large).
  --syll         Preserve syllable structure.
  --stress       Preserve stress.
```
