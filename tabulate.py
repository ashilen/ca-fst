#!/usr/bin/env python3
import os
import copy
from collections import defaultdict
import pprint
import argparse
from pyfoma.phonrule import Ruleset as _Ruleset

GRAMMAR = 'grammar'
PREDICTIONS = os.path.join(GRAMMAR, 'predictions')
CORRECT_MADE = os.path.join(PREDICTIONS, 'correct-made.txt')
CORRECT_MISSED = os.path.join(PREDICTIONS, 'correct-missed.txt')
INCORRECT_MADE = os.path.join(PREDICTIONS, 'incorrect-made.txt')

TABULATED = os.path.join(PREDICTIONS, 'incorrect-tabulated.txt')

BIG_GRAMMAR = os.path.join(GRAMMAR, 'lim.big.grammar.foma')


class Ruleset(_Ruleset):
    def applicable_rules_for_word(self, word):
        """Return the list of rules that apply in order."""
        _applicable_rules = []

        def transduce(prev, rule_idx=0):
            rule_name = self.rc[rule_idx]
            transducer = self.rules[rule_name]
            transduced = transducer[prev][0]

            if transduced != prev:
                _applicable_rules.append(rule_name)

            if rule_idx + 1 > len(self.rc) - 1:
                return transduced

            transduce(transduced, rule_idx + 1)

        transduce(word)

        return _applicable_rules


class Tabulator:
    UR = 'UR'
    SR = 'SR'
    RULES = 'RULES'

    def __init__(self, grammar_file_name):
        with open(CORRECT_MADE) as correct_made_f, \
             open(CORRECT_MISSED) as correct_missed_f, \
             open(INCORRECT_MADE) as incorrect_made_f:

            self.correct_made = self.to_dict(correct_made_f)
            self.correct_missed = self.to_dict(correct_missed_f)
            self.incorrect_made = self.to_dict(incorrect_made_f)

        with open(os.path.join(GRAMMAR, grammar_file_name)) as grammar_file:
            grammar_lines = [line.rstrip() for line in grammar_file]
            self.ruleset = Ruleset()
            self.ruleset.readrules(grammar_lines)

        self._rule_application_count = defaultdict(int)

    @property
    def prediction_dicts(self):
        return [
            # self.correct_made,
            # self.correct_missed,
            self.incorrect_made
        ]

    @property
    def rule_application_count(self):
        return self._rule_application_count

    def to_dict(self, f):
        lines = [line.split() for line in f.readlines()]
        return {
            ur: {Tabulator.UR: ur, Tabulator.SR: sr, Tabulator.RULES: []}
            for ur, sr in lines
        }

    def write_to_file(self, d, f):
        for k, v in d.items():
            f.write('%s\t%s\n' % (
                k, '\t'.join(v) if isinstance(v, tuple) else v
            ))

    def tabulate(self):
        for prediction_dict in self.prediction_dicts:
            urs = prediction_dict.keys()

            for ur in urs:
                ur_bytes = ur.encode()
                applicable_rules = self.ruleset.applicable_rules_for_word(
                    ur_bytes
                )

                for applicable_rule in applicable_rules:
                    self._rule_application_count[applicable_rule] += 1

                prediction_dict[ur][Tabulator.RULES] += applicable_rules

    def derivation_for_word(self, word):
        self.ruleset.applyrules(word.encode())

    def original(self):
        with open(TABULATED) as f:
            for line in f.readlines():
                ur = line.split()[0].encode()
                yield self.ruleset.applyrules(ur, printall=False)

    """
    def application_count(self):
        underlying_reps = [
            line.split()[0] for line
            in incorrect_predictions_f.readlines()
        ]

        for ur in underlying_reps:
            rule_application = r.applyrules(ur.encode(), printall=False)
            print(rule_application)
    """


def main():
    parser = argparse.ArgumentParser(
        description="Prediction tabulation utilities.")
    parser.add_argument("--word", type=str)
    parser.add_argument("--grammar", type=str)
    parser.add_argument("--original", action="store_true")
    args = parser.parse_args()

    tabulator = Tabulator(grammar_file_name=args.grammar)

    if args.word:
        derivation = tabulator.derivation_for_word(args.word)
        print(derivation)
    elif args.original:
        for derivation in tabulator.original():
            print(derivation)
            print("\n")
    else:
        tabulator.tabulate()
        pprint.pprint(tabulator.rule_application_count)


if __name__ == "__main__":
    main()
