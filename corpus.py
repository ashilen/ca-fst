import os
import re
import csv
import panphon
from lib.epi import ConfigurableEpitran
from collections import defaultdict
from pprint import pprint
import argparse


DATA_DIR = "data"


def separate(elements, prefix="", sep="|"):
    return "".join(
        ["%s%s%s" % (prefix, element, sep) for element in elements]
    )[:-1]


class RowIterable:
    def __iter__(self):
        return iter(self.rows)

    def __next__(self):
        return self.rows.__next__()

    def __len__(self):
        return self.rows.__len__()


class OrthBank(RowIterable):
    FILE = "adj.orth"
    PATH = os.path.join(DATA_DIR, FILE)

    FS = "AQ0FS0"   # fem sing
    FP = "AQ0FP0"   # fem plur
    MS = "AQ0MS0"   # masc sing
    MP = "AQ0MP0"   # masc plur
    NS = "AQ0CS0"   # neut sing
    NP = "AQ0CP0"   # neut plur

    # what are these?

    CN = "AQ0CN0"

    FSP = "AQ0FSP"
    FPP = "AQ0FPP"
    MSP = "AQ0MSP"
    MPP = "AQ0MPP"

    MN = "AQ0MN0"
    FN = "AQ0FN0"

    IGNORE = [NS, NP, CN, FSP, FPP, MSP, MPP, MN, FN]

    INFL = "infl"
    UR = "ur"
    KEY = "key"
    LEMMA = "lemma"

    def __init__(self):
        self.rows = list(csv.DictReader(
            open(self.PATH), delimiter=" ", fieldnames=[
                OrthBank.INFL, OrthBank.LEMMA, OrthBank.KEY]
        ))


class PhonBank(RowIterable):
    FILE = "adj.phon"
    PATH = os.path.join(DATA_DIR, FILE)

    # reverse this:
    # https://salsa.debian.org/tts-team/festival-ca/-/blob/master/src/data/unicode2sampa.sh
    ipa_map = {
        "ax": "ə",
        "L": "ʎ",
        "B": "β",
        "S": "ʃ",
        "E": "ɛ",
        "O": "ɔ",
        "D": "ð",
        "S": "ʃ",
        "tS": "t͡ʃ",
        "ts": "t͡ʃ",  # I assume
        "Z": "ʒ",
        "G": "ɣ",
        "g": "ɡ",
        "Z": "ʒ",
        "dZ": "d͡ʒ",
        "N": "ŋ",  # in env of g?
        "J": "ɲ",  # in env of y?
        "rr": "r",
        "r": "ɾ",
        "y": "j",
    }

    SYLL = "-"
    STRESS = "1"

    def __init__(self, incl_stress=True, incl_syllables=True):
        def preproc(row):
            row = row.split()

            if not incl_stress:
                row = map(lambda seg: seg.replace("1", ""), row)
            if not incl_syllables:
                row = map(lambda seg: seg.replace("-", ""), row)

            if incl_stress and incl_syllables:
                # Then let's move the stress to the beginning of its syllable.
                last_syl_marker_idx = -1
                for idx, unit in enumerate(row[:]):
                    last_syl_marker_idx = idx if unit == self.SYLL else last_syl_marker_idx
                    if self.STRESS in unit:
                        row[idx] = unit.replace(self.STRESS, "")
                        row.insert(last_syl_marker_idx + 1, self.STRESS)

            return " ".join([
                self.ipa_map[segment] if segment in self.ipa_map else segment
                for segment in row
            ])

        raw_rows = open(self.PATH).readlines()
        self.rows = [preproc(row) for row in raw_rows]

        self._phonemes = self.get_phonemes()
        self.feature_table = panphon.FeatureTable()

    def __getitem__(self, idx):
        return self.rows[idx]

    def get_phonemes(self):
        phonemes = set()
        for line in self:
            for phon in line.split():
                phonemes.add(phon)
        return phonemes

    @property
    def phonemes(self):
        return self._phonemes

    @property
    def features(self):
        return self.feature_phoneme_sets.keys()

    @property
    def phoneme_feature_sets(self):

        def fs(phon):
            fts = self.feature_table.word_fts(phon)

            if len(fts) != 1:
                return

            else:
                segment = fts[0]

            def markup(feat):
                return "%s%s" % ("+" if segment[feat] == 1 else "-", feat)

            # Only those features that are defined for the phoneme.
            return [markup(feat) for feat in segment
                    if segment[feat] in [-1, 1]]

        return {phon: fs(phon) for phon in self.phonemes if fs(phon)}

    @property
    def feature_phoneme_sets(self):
        features = defaultdict(set)
        for phon, fs in self.phoneme_feature_sets.items():
            for feature in fs:
                features[feature].add(phon)

        return features


class Corpus(RowIterable):

    MASC = "+Masc"
    FEM = "+Fem"
    NEUT = "+Neut"
    SG = "+Sg"
    PL = "+Pl"
    ADJ_INF = "AdjInf"

    def __init__(self, preserve_syllables, preserve_stress):
        self.phon_bank = PhonBank(
            incl_syllables=preserve_syllables, incl_stress=preserve_stress)
        self.orth_bank = OrthBank()

        self.lemma_to_phon_infl = self.get_lemma_to_phon_infl()
        self.ur_to_infl = self.get_ur_to_infl()

        # Epitran applies some of its own rules unless instructed not to,
        # depriving us of the opportunity, unless we unset this preproc flag.
        # See https://github.com/dmort27/epitran/blob/master/epitran/data/pre/cat-Latn.txt
        file = "cat-Latn.csv"
        g2p_loc = os.path.join("..", DATA_DIR, "map", file)
        self.epi = ConfigurableEpitran("cat-Latn", preproc=False, g2p_loc=g2p_loc)

    def orth_to_phon(self, orth):
        return self.epi.transliterate(orth)

    def get_lemma_to_phon_infl(self):
        lemma_to_phon_infl = defaultdict(dict)

        for idx, row in enumerate(self.orth_bank):
            lemma = row[OrthBank.LEMMA]
            key = row[OrthBank.KEY]

            # skip features that I don't know what they are
            if key in OrthBank.IGNORE: continue

            phonetic_infl = self.phon_bank[idx]
            phonetic_infl = re.sub("\s", "", phonetic_infl)

            lemma_to_phon_infl[lemma][key] = phonetic_infl

        # filter examples that lack both MS and FS
        lemma_to_phon_infl = {
            lemma: infls for lemma, infls in lemma_to_phon_infl.items()
            if OrthBank.MS in infls and OrthBank.FS in infls}

        return lemma_to_phon_infl

    def get_ur_to_infl(self):
        """Derive underlying representations with some heuristics:

            - Assume UR is fem sing minus final phon, plus
              decontinuation of word final stops:

                ɣ -> ɡ, ð -> d, β -> b.

            - Or if the lemma has a final front vowel, assume that vowel.

            - Or if the lemma has a final back vowel, assume it's the masculine
              inflection that's underlying.

        We also have to re-syllabify, which amounts to removing the final
        syllable marker:
            1) dangling consonants become the coda of the previous
               syllable or
            2) the vowel was the entire syllable
        """

        def to_ur(infl_map, lemma):
            fem_sing_infl = infl_map[OrthBank.FS]

            decont_map = {
                "ɣ": "ɡ",
                "ð": "d",
                "β": "b"
            }

            # if lemma-final /e/, /ɛ/, /a/
            if lemma[-1] in ["e", "a"]:
                return fem_sing_infl
            elif lemma[-1] in ["o", "u"]:
                return infl_map[OrthBank.MS]

            ur = fem_sing_infl[:-1]
            new_final_char = ur[-1]
            if new_final_char in decont_map:
                ur = ur[:-1] + decont_map[new_final_char]

            # fixup final syllable
            ur = "".join(ur.rsplit("-", maxsplit=1))

            return ur

        return {
            to_ur(infl_map, lemma): infl_map
            for lemma, infl_map in self.lemma_to_phon_infl.items()
            if OrthBank.FS in infl_map}

    def format_UR_lexicon(self):
        root_templ = """
Multichar_Symbols {MASC} {FEM} d͡ʒ t͡ʃ

LEXICON Root

Adj ;

LEXICON Adj

{UR}

LEXICON {ADJ_INF}

{MASC}:0   #;
{FEM}:ə    #;
"""

        return root_templ.format(
            UR=self.format_UR(),
            MASC=self.MASC,
            FEM=self.FEM,
            ADJ_INF=self.ADJ_INF
        )

    def format_SR_lexicon(self):
        root_templ = """
Multichar_Symbols {MASC} {FEM} d͡ʒ t͡ʃ

LEXICON SR

{UR_to_SR}
"""
        return root_templ.format(
            UR_to_SR=self.format_UR_to_SR(),
            MASC=self.MASC,
            FEM=self.FEM,
        )

    def format_UR_to_SR(self):
        templates = {
            OrthBank.MS: "{{ur}}{MASC}:{{sr}}\t#;".format(MASC=self.MASC),
            OrthBank.FS: "{{ur}}{FEM}:{{sr}}\t#;".format(FEM=self.FEM)}

        return "\n".join([
            templates[infl_key].format(
                ur=ur,
                sr=infl_val
            )
            for ur, infl_map in self.ur_to_infl.items()
            for infl_key, infl_val in infl_map.items()
            if infl_key in templates])

    def format_UR(self):
        templ = "{ur} {ADJ_INF};"
        return "\n".join([
            templ.format(
                ur=ur,
                ADJ_INF=self.ADJ_INF)
            for ur in self.ur_to_infl.keys()
        ])

    def format_phonetic_defs(self, defs, prefix="", sep="|"):
        """Format feature to phoneme set tuples in the form:

        define +syll [ i | e | ɛ | a | ɔ | o | u ];

        """
        templ = "define {name} [{elements}];\n"

        return "".join([
            templ.format(name=name, elements=separate(elements, prefix=prefix, sep=sep))
            for name, elements in defs.items()
        ])

    def format_feature_defs(self):
        return self.format_phonetic_defs(self.phon_bank.feature_phoneme_sets)

    def format_phoneme_defs(self):
        return self.format_phonetic_defs(self.phon_bank.phoneme_feature_sets, prefix="%", sep="&")

    def format_alphabet(self):
        templ = "define {name} [{elements}];\n"

        alphabet = sorted(self.phon_bank.phoneme_feature_sets.keys())
        return templ.format(name="alph", elements=separate(alphabet))


class SmallOrthPhonBank(OrthBank):
    """Expects a file in .orth format that nevertheless contains phonemes."""

    FILE = "small.adj.orth-phon"
    PATH = os.path.join(DATA_DIR, FILE)

    def __init__(self):
        self.rows = list(csv.DictReader(
            open(self.PATH), delimiter=" ", fieldnames=[
                OrthBank.INFL, OrthBank.UR, OrthBank.KEY]
        ))


class SmallCorpus(Corpus):
    def __init__(self):
        self.orth_bank = SmallOrthPhonBank()
        self.ur_to_infl = self.get_ur_to_infl()

    def get_ur_to_infl(self):
        ur_to_infl = defaultdict(dict)

        for idx, row in enumerate(self.orth_bank):
            ur = row[OrthBank.UR]
            key = row[OrthBank.KEY]
            infl = row[OrthBank.INFL]

            ur_to_infl[ur][key] = infl

        return ur_to_infl


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Corpus utilities.")
    parser.add_argument("-features", action="store_true",
                        help="Print feature keys.")
    parser.add_argument("-feature-defs", action="store_true",
                        help="Print formatted feature definitions.")
    parser.add_argument("-phoneme-defs", action="store_true",
                        help="Print formatted phoneme definitions.")
    parser.add_argument("-ur-lexicon", action="store_true",
                        help="Print the UR lexicon.")
    parser.add_argument("-sr-lexicon", action="store_true",
                        help="Print the UR-to-SR lexicon.")
    parser.add_argument("-alphabet", action="store_true",
                        help="Print the alphabet.")
    parser.add_argument("--small", action="store_true",
                        help="Operate on the small lexicon.")
    parser.add_argument("--syll", action="store_true",
                        help="Preserve syllable structure.")
    parser.add_argument("--stress", action="store_true",
                        help="Preserve stress.")
    args = parser.parse_args()

    if args.small:
        corpus_class = SmallCorpus
    else:
        corpus_class = Corpus

    corpus = corpus_class(args.syll, args.stress)

    if args.feature_defs:
        print(corpus.format_feature_defs())

    elif args.phoneme_defs:
        print(corpus.format_phoneme_defs())

    elif args.features:
        print(corpus.phon_bank.features)

    elif args.ur_lexicon:
        print(corpus.format_UR_lexicon())

    elif args.sr_lexicon:
        print(corpus.format_SR_lexicon())

    elif args.alphabet:
        print(corpus.format_alphabet())
