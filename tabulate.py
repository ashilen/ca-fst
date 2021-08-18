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

    CORRECT = 'CORRECT'
    INCORRECT = 'INCORRECT'

    def __init__(self, grammar_file_name):
        with open(CORRECT_MADE) as correct_made_f, \
             open(CORRECT_MISSED) as correct_missed_f, \
             open(INCORRECT_MADE) as incorrect_made_f:

            self._correct_made = self.to_dict(correct_made_f)
            self._correct_missed = self.to_dict(correct_missed_f)
            self._incorrect_made = self.to_dict(incorrect_made_f)

        with open(os.path.join(GRAMMAR, grammar_file_name)) as grammar_file:
            grammar_lines = [line.rstrip() for line in grammar_file]
            self._ruleset = Ruleset()
            self._ruleset.readrules(grammar_lines)

        self._rule_application_count = defaultdict(lambda: defaultdict(int))

    @property
    def ruleset(self):
        return self._ruleset

    @property
    def correct_predictions(self):
        return self._correct_made
    @property
    def incorrect_predictions(self):
        return self._incorrect_made

    @property
    def prediction_dicts(self):
        return [
            self.correct_made,
            self.incorrect_made
        ]

    def rule_application_count(self, prediction_type='correct'):
        return self._rule_application_count[prediction_type]

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
        for prediction_dict, prediction_type in [
            (self.correct_predictions, Tabulator.CORRECT),
            (self.incorrect_predictions, Tabulator.INCORRECT)
        ]:
            urs = prediction_dict.keys()

            for ur in urs:
                ur_bytes = ur.encode()
                applicable_rules = self.ruleset.applicable_rules_for_word(
                    ur_bytes
                )

                for applicable_rule in applicable_rules:
                    self._rule_application_count[prediction_type][applicable_rule] += 1

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
    parser.add_argument("--correct", action="store_true")
    parser.add_argument("--incorrect", action="store_true")
    args = parser.parse_args()

    tabulator = Tabulator(grammar_file_name=args.grammar)

    if args.correct and args.incorrect:
        raise Exception('Das absurde!')

    if args.word:
        derivation = tabulator.derivation_for_word(args.word)
        print(derivation)
    elif args.original:
        for derivation in tabulator.original():
            print(derivation)
            print("\n")
    elif args.correct:
        tabulator.tabulate()
        pprint.pprint(tabulator.rule_application_count(Tabulator.CORRECT))
    elif args.incorrect:
        tabulator.tabulate()
        pprint.pprint(tabulator.rule_application_count(Tabulator.INCORRECT))
    else:
        tabulator.tabulate()
        pprint.pprint(tabulator.rule_application_count)


if __name__ == "__main__":
    main()
