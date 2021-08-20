import subprocess
import os
import copy
from collections import OrderedDict
from tabulate import (
    GRAMMAR,
    CORRECT_MADE,
    CORRECT_MISSED,
    INCORRECT_MADE,
    TABULATED,
    Tabulator,
    get_parser
)


def fix_predictions():
    def to_dict(f):
        lines = [line.split() for line in f.readlines()]
        return {ur: sr for ur, sr in lines}

    def write_to_file(d, f):
        for k, v in d.items():
            f.write('%s\t%s\n' % (
                k, '\t'.join(v) if isinstance(v, tuple) else v
            ))

    with open(CORRECT_MADE) as correct_made_f, \
          open(CORRECT_MISSED) as correct_missed_f, \
          open(INCORRECT_MADE) as incorrect_made_f:

        correct_made = to_dict(correct_made_f)
        correct_missed = to_dict(correct_missed_f)
        incorrect_made = to_dict(incorrect_made_f)

        new_correct_made = copy.copy(correct_made)
        new_correct_missed = copy.copy(correct_missed)
        new_incorrect_made = copy.copy(incorrect_made)

        for ur, sr in incorrect_made.items():
            if ur in correct_missed and correct_missed[ur] == sr:
                new_correct_made[ur] = sr
                del new_correct_missed[ur]
                del new_incorrect_made[ur]

        for predictions, file in [
            (new_correct_made, open(CORRECT_MADE, 'w+')),
            (new_correct_missed, open(CORRECT_MISSED, 'w+')),
            (new_incorrect_made, open(INCORRECT_MADE, 'w+')),
        ]:
            write_to_file(predictions, file)

        table = OrderedDict(
            (ur, (incorrect_made[ur], correct_missed[ur]))
            for ur in sorted(new_incorrect_made.keys())
            if ur in correct_missed
        )

        write_to_file(table, open(TABULATED, 'w+'))


def main():
    parser = get_parser()
    parser.add_argument("--exception-dir", type=str, help="output dir")
    parser.add_argument("-a", action="store_true", help="append to count file")
    args = parser.parse_args()

    COMMAND = ['foma', '-f', 'test.grammar.foma']
    subprocess.call(COMMAND, cwd=GRAMMAR)

    fix_predictions()

    tabulator = Tabulator(grammar_file_name=args.grammar)
    tabulator.tabulate()

    if not os.path.exists(args.exception_dir) or not os.path.isdir(args.exception_dir):
        os.mkdir(args.exception_dir)

    incorrect_examples_tables_file = os.path.join(args.exception_dir, 'incorrect-table.csv')
    correct_examples_tables_file = os.path.join(args.exception_dir, 'correct-table.csv')
    exception_counts_file = os.path.join(args.exception_dir, 'count.csv')
    tabulator.write_tabulation_examples(
        file=incorrect_examples_tables_file,
        prediction_type=Tabulator.INCORRECT)
    tabulator.write_tabulation_examples(
        file=correct_examples_tables_file,
        prediction_type=Tabulator.CORRECT)
    tabulator.write_tabulation_count(
        file=exception_counts_file,
        append=args.a)


if __name__ == "__main__":
    main()
