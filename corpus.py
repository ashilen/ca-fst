import os
import re
import csv
import panphon
import epitran
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

    def __init__(self):
        self.rows = list(csv.DictReader(
            open(self.PATH), delimiter=" ", fieldnames=[
                OrthBank.INFL, OrthBank.UR, OrthBank.KEY]
        ))

        self.ur_map = self.get_ur_map()

    def get_ur_map(self):
        ur_map = defaultdict(dict)

        for idx, row in enumerate(self.rows):
            infl = row[OrthBank.INFL]
            ur = row[OrthBank.UR]
            key = row[OrthBank.KEY]

            ur_map[ur][key] = infl

        return ur_map

    def __getitem__(self, ur):
        return self.ur_map[ur]


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

        # preserve stress
        "ax1": "ə1",
        "E1": "ɛ1",
        "O1": "ɔ1",
    }

    def __init__(self, incl_stress=True, incl_syllables=True):
        def to_ipa(row):
            row = row.split()

            if not incl_stress:
                row = map(lambda seg: seg.replace("1", ""), row)
            if not incl_syllables:
                row = map(lambda seg: seg.replace("-", ""), row)

            return " ".join([
                self.ipa_map[segment] if segment in self.ipa_map else segment
                for segment in row
            ])

        raw_rows = open(self.PATH).readlines()
        self.rows = [to_ipa(row) for row in raw_rows]

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

        self.orth_ur_to_phon_infl = self.get_orth_ur_to_phon_infl()

        # Epitran applies some of its own rules unless instructed not to,
        # depriving us of the opportunity, unless we unset this preproc flag.
        # See https://github.com/dmort27/epitran/blob/master/epitran/data/pre/cat-Latn.txt
        self.epi = epitran.Epitran("cat-Latn", preproc=False)

    def orth_to_phon(self, orth):
        return self.epi.transliterate(orth)

    def get_orth_ur_to_phon_infl(self):
        orth_ur_to_phon_infl = defaultdict(dict)

        for idx, row in enumerate(self.orth_bank):
            ur = row[OrthBank.UR]
            key = row[OrthBank.KEY]

            # skip features that I don't know what they are
            if key in OrthBank.IGNORE: continue

            phonetic_infl = self.phon_bank[idx]
            phonetic_infl = re.sub("\s", "", phonetic_infl)

            orth_ur_to_phon_infl[ur][key] = phonetic_infl

        return orth_ur_to_phon_infl

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
            templates[phon_infl_key].format(
                ur=self.orth_to_phon(orth_ur),
                sr=phon_infl
            )
            for orth_ur, phon_infl_map in self.orth_ur_to_phon_infl.items()
            for phon_infl_key, phon_infl in phon_infl_map.items()
            if phon_infl_key in templates])

    def format_UR(self):
        templ = "{ur} {ADJ_INF};"
        return "\n".join([
            templ.format(
                ur=self.orth_to_phon(orth_ur),
                ADJ_INF=self.ADJ_INF)
            for orth_ur, phon_infl_map in self.orth_ur_to_phon_infl.items()
        ])

    def ur_orth_to_phon(self):
        templ = "{orth} {phon}"
        return "\n".join([
            templ.format(
                orth=orth_ur,
                phon=self.orth_to_phon(orth_ur))
            for orth_ur, phon_infl_map in self.orth_ur_to_phon_infl.items()
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
    """Expects file in .orth format that contains phonemes."""

    FILE = "small.adj.orth-phon"
    PATH = os.path.join(DATA_DIR, FILE)


class SmallCorpus(Corpus):
    def __init__(self):
        self.orth_bank = SmallOrthPhonBank()
        self.orth_ur_to_phon_infl = self.get_orth_ur_to_phon_infl()

    def get_orth_ur_to_phon_infl(self):
        orth_ur_to_phon_infl = defaultdict(dict)

        for idx, row in enumerate(self.orth_bank):
            ur = row[OrthBank.UR]
            key = row[OrthBank.KEY]
            infl = row[OrthBank.INFL]

            orth_ur_to_phon_infl[ur][key] = infl

        return orth_ur_to_phon_infl

    def orth_to_phon(self, orth):
        return orth
