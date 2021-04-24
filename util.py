import argparse
from corpus import Corpus

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Corpus utilities.")
    parser.add_argument("-features", action="store_true",
                        help="Print feature keys.")
    parser.add_argument("-feature-defs", action="store_true",
                        help="Print formatted feature definitions.")
    parser.add_argument("-phoneme-defs", action="store_true",
                        help="Print formatted phoneme definitions.")
    parser.add_argument("-lexicon", action="store_true",
                        help="Print the lexicon.")
    parser.add_argument("-ur-orth-to-phon", action="store_true",
                        help="Print the lexicon.")

    args = parser.parse_args()

    corpus = Corpus()

    if args.feature_defs:
        print(corpus.format_feature_defs())

    elif args.phoneme_defs:
        print(corpus.format_phoneme_defs())

    elif args.features:
        print(corpus.phon_bank.features)

    elif args.lexicon:
        print(corpus.format_lexicon())

    elif args.ur_orth_to_phon:
        print(corpus.ur_orth_to_phon())
