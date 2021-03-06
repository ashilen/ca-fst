#!/usr/bin/env python3
import os
import copy
import csv
from collections import defaultdict, OrderedDict
import pprint
import argparse
import itertools
from pyfoma.phonrule import Ruleset as _Ruleset

GRAMMAR = 'grammar'
PREDICTIONS = os.path.join(GRAMMAR, 'predictions')
CORRECT_MADE = os.path.join(PREDICTIONS, 'correct-made.txt')
CORRECT_MISSED = os.path.join(PREDICTIONS, 'correct-missed.txt')
INCORRECT_MADE = os.path.join(PREDICTIONS, 'incorrect-made.txt')

TABULATED = os.path.join(PREDICTIONS, 'incorrect-tabulated.txt')

BIG_GRAMMAR = os.path.join(GRAMMAR, 'big.grammar.foma')


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

    PREDICTION_TYPES = [CORRECT, INCORRECT]

    def __init__(self, grammar_file_name):
        with open(CORRECT_MADE) as correct_made_f, \
             open(CORRECT_MISSED) as correct_missed_f, \
             open(INCORRECT_MADE) as incorrect_made_f:

            self._correct_made = self.to_dict(correct_made_f)
            self._correct_missed = self.to_dict(correct_missed_f)
            self._incorrect_made = self.to_dict(incorrect_made_f)

        with open(grammar_file_name) as grammar_file:
            grammar_lines = [line.rstrip() for line in grammar_file]
            self._ruleset = Ruleset()
            self._ruleset.readrules(grammar_lines)

        self._rule_application_count = defaultdict(lambda: defaultdict(lambda: 0))

    @property
    def ruleset(self):
        return self._ruleset

    @property
    def missed_predictions(self):
        return self._correct_missed

    @property
    def correct_predictions(self):
        return self._correct_made

    @property
    def incorrect_predictions(self):
        return self._incorrect_made

    @property
    def prediction_dicts(self):
        return [
            self.correct_predictions,
            self.incorrect_predictions
        ]

    @property
    def prediction_dicts_map(self):
        return {
            Tabulator.CORRECT: self.correct_predictions,
            Tabulator.INCORRECT: self.incorrect_predictions
        }

    def rule_application_count(self, prediction_type=None):
        if prediction_type:
            return {
                rule: prediction[prediction_type]
                for rule, prediction in self._rule_application_count.items()
            }
        else:
            return self._rule_application_count

    def to_dict(self, f):
        lines = [line.split() for line in f.readlines()]
        return {
            ur: {Tabulator.UR: ur, Tabulator.SR: sr, Tabulator.RULES: ''}
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
                applicable_rules = self.ruleset.applicable_rules_for_word(
                    ur.encode()
                )

                applicable_rules_string = "".join(
                    "[%s]" % rule for rule in applicable_rules
                )

                self._rule_application_count[applicable_rules_string][prediction_type] += 1
                self._rule_application_count[applicable_rules_string][Tabulator.RULES] = applicable_rules_string

                prediction_dict[ur][Tabulator.RULES] = applicable_rules_string

    def derivation_for_word(self, word):
        return self.ruleset.applyrules(word.encode(), printall=False)

    def original(self):
        with open(TABULATED) as f:
            for line in f.readlines():
                ur = line.split()[0].encode()
                yield self.ruleset.applyrules(ur, printall=False)

    def write_tabulation_count(self, file, append=False):
        ORDER = "ORDER"
        rule_order = [
            {ORDER: rulename} for rulename in self.ruleset.rc
        ]

        mode = "a" if append else "w"
        with open(file, mode, newline='') as f:

            writer = csv.DictWriter(
                f, fieldnames=[Tabulator.RULES] + Tabulator.PREDICTION_TYPES + [ORDER],
                delimiter='\t'
            )

            # spacer
            if append:
                writer.writerow({Tabulator.RULES: ''})

            writer.writeheader()

            vals = self._rule_application_count.values()

            rows = sorted(
                vals,
                key=lambda row: row[Tabulator.RULES]
            )

            n = 0
            while n < len(rule_order):
                rows[n].update(rule_order[n])
                n += 1

            writer.writerows(rows)
            sum_correct = sum([val[Tabulator.CORRECT] for val in vals])
            sum_incorrect = sum([val[Tabulator.INCORRECT] for val in vals])
            writer.writerow({
                Tabulator.CORRECT: sum_correct,
                Tabulator.INCORRECT: sum_incorrect
            })

    def write_tabulation_examples(self, file, prediction_type=INCORRECT):
        with open(file, 'w', newline='') as f:
            CORRECT_SR = "Correct " + Tabulator.SR
            PREDICTED_SR = "Predicted " + Tabulator.SR

            writer = csv.DictWriter(
                f, fieldnames=[
                    Tabulator.UR,
                    PREDICTED_SR,
                    CORRECT_SR
                ],
                delimiter='\t'
            )

            for ruleset in sorted(
                self._rule_application_count.keys(),
                key=lambda ruleset: (
                    self._rule_application_count[ruleset][prediction_type]
                )
            ):
                correct_column_src = {
                    Tabulator.CORRECT: self.correct_predictions,
                    Tabulator.INCORRECT: self.missed_predictions
                }[prediction_type]

                row_src = self.prediction_dicts_map[prediction_type]

                row_inclusion_predicate = {
                    Tabulator.INCORRECT: lambda ur: ur in self.missed_predictions,
                    Tabulator.CORRECT: lambda _: True  # noop
                }[prediction_type]

                applicable_predictions = [
                    {
                        Tabulator.UR: ur,
                        PREDICTED_SR: prediction[Tabulator.SR],
                        CORRECT_SR: correct_column_src[ur][Tabulator.SR]
                    } for ur, prediction
                    in row_src.items()
                    if ruleset == prediction[Tabulator.RULES] and (
                        row_inclusion_predicate(ur)
                    )
                ]

                writer.writerow({Tabulator.UR: ruleset})
                writer.writeheader()
                writer.writerows(applicable_predictions)
                writer.writerow({Tabulator.UR: ''})


def get_parser():
    parser = argparse.ArgumentParser(
        description="Prediction tabulation utilities.")
    parser.add_argument("--word", type=str)
    parser.add_argument("--grammar", type=str, default=BIG_GRAMMAR)
    parser.add_argument("--original", action="store_true")
    parser.add_argument("--count", action="store_true")
    parser.add_argument("--examples", action="store_true")
    parser.add_argument("--correct", action='store_const', const=Tabulator.CORRECT)
    parser.add_argument("--incorrect", action='store_const', const=Tabulator.INCORRECT)
    parser.add_argument("--exception-dest", type=str, help="output file")
    return parser


def main():
    parser = get_parser()
    args = parser.parse_args()

    tabulator = Tabulator(grammar_file_name=args.grammar)

    if args.correct and args.incorrect:
        raise Exception('Das absurde!')

    if args.word:
        derivation = tabulator.derivation_for_word(args.word)
        print('DERIVATION:', derivation)

    elif args.original:
        for derivation in tabulator.original():
            print(derivation)
            print("\n")
    elif args.count:
        tabulator.tabulate()

        if args.dest:
            tabulator.write_tabulation_count(file=args.exception_dest)
        else:
            prediction_type = args.correct or args.incorrect or None
            pprint.pprint(
                tabulator.rule_application_count(
                    prediction_type
                )
            )
    elif args.examples:
        tabulator.tabulate()

        if args.dest:
            tabulator.write_tabulation_examples(
                file=args.exception_dest)
        else:
            prediction_type = args.correct or args.incorrect or None
            pprint.pprint(
                tabulator.rule_application_examples(
                    prediction_type
                )
            )


if __name__ == "__main__":
    main()
