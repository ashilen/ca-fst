import argparse
from corpus import Corpus, SmallCorpus

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
