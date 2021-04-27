import os
import re
import csv
import panphon
from lib.epi import ConfigurableEpitran
from collections import defaultdict
from pprint import pprint

DATA_DIR = "data"


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

    ipa_map = {
        "ax": "ə",
        "L": "ʎ",
        "B": "β",
        "S": "ʃ",
        "E": "ɛ",
        "O": "ɔ",
        "D": "ð",
        "tS": "t͡ʃ",
        "ts": "t͡ʃ",  # I assume
        "Z": "ʒ",
        "G": "ɣ",
        "g": "ɡ",
        "Z": "ʒ",
        "dZ": "d͡ʒ",
        "N": "ŋ",  # g?
        "J": "ɲ",  # y?
        "rr": "r",
        "r": "ɾ",
    }

    def __init__(self, incl_stress=True, incl_syllables=True):
        def preproc(row):
            if not incl_stress:
                row = map(lambda seg: seg.replace("1", ""), row)
            if not incl_syllables:
                row = map(lambda seg: seg.replace("-", ""), row)

            if incl_stress and incl_syllables:
                # Then let's convert the stress notation to sziga's:
                # just place a ' at the beginning of the syllable in which "1"
                # occurs.
                sylls = row.split("-")
                row = "-".join([
                    "\' " + syll.replace("1", "") if "1" in syll else syll
                    for syll in sylls
                ])

            return " ".join([
                self.ipa_map[segment] if segment in self.ipa_map else segment
                for segment in row.split()
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

    def __init__(self):
        self.phon_bank = PhonBank()
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

        return lemma_to_phon_infl

    def get_ur_to_infl(self):
        """Employ some heuristics to derive underlying representations
        from the data:

        Assume UR is fem sing - final char, plus
        decontinuation of word final stops:
        ɣ -> ɡ, ð -> d, β -> b.

        This means we have to skip examples that lack
        a feminine alternation.

        We also have to re-syllabify and re-stress, a job
        we'll save for the grammar. Here, just strip the syllable
        and stress markers.
        """

        def fem_to_ur(word):
            decont_map = {
                "ɣ": "ɡ",
                "ð": "d",
                "β": "b"
            }

            word = word[:-1]
            new_final_char = word[-1]
            if new_final_char in decont_map:
                word = word[:-2] + decont_map[new_final_char]

            word = word.replace("-", "").replace("\'", "")

            return word

        return {
            fem_to_ur(infl_map[OrthBank.FS]): infl_map
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
            for ur, infl_map in self.ur_to_infl.items()
        ])

    def format_phonetic_defs(self, defs, prefix=""):
        """Format feature to phoneme set tuples in the form:

        define +syll [ i | e | ɛ | a | ɔ | o | u ];

        """
        templ = "define {name} [{elements}];\n"

        def pipe_separate(elements):
            return "".join(
                [" %s%s %s " % (prefix, element, "|") for element in elements]
            )[:-2]

        return "".join([
            templ.format(name=name, elements=pipe_separate(elements))
            for name, elements in defs.items()
        ])

    def format_feature_defs(self):
        return self.format_phonetic_defs(self.phon_bank.feature_phoneme_sets)

    def format_phoneme_defs(self):
        return self.format_phonetic_defs(self.phon_bank.phoneme_feature_sets, prefix="%")


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
