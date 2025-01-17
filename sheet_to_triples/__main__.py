# Copyright 2020 Visual Meaning Ltd
# This is free software licensed as GPL-3.0-or-later - see COPYING for terms.

"""Convert tabular data into triples."""

import argparse
import itertools
import os
import stat
import sys

from . import (
    debug,
    rdf,
    run,
    trans,
)

PURGE_MAP = {
    'none': lambda _: True,
    'geo': rdf.relates_geo_name,
    'issues': rdf.relates_issue,
}


def _is_book_path(path):
    return path.endswith(('.xls', '.xlsx'))


def _parse_book_path(path):
    st = os.stat(path)
    if stat.S_ISDIR(st.st_mode):
        for root, dirs, files in os.walk(path):
            for filepath in filter(_is_book_path, files):
                yield os.path.join(root, filepath)
            return
    elif stat.S_ISREG(st.st_mode):
        yield path


def _transform_list(path):
    if path is None:
        return
    dir_path = os.path.dirname(path)
    with open(path, 'r') as f:
        transform_names = f.read().splitlines()
    for name in transform_names:
        yield from trans.Transform.iter_from_name(name, base_path=dir_path)


def list_from_parser_iter(parser, iterator, argument):
    """Make parser errors from delayed execution during argument iteration.

    Note, this stops on the first error in the iterator still, rather than
    collecting all errors and exhausing the iterator.
    """
    try:
        return list(iterator)
    except (EnvironmentError, ValueError) as err:
        parser.error('{a} argument: {e}'.format(a=argument, e=err))


def parse_args(argv):
    parser = argparse.ArgumentParser(argv[0], description=__doc__)
    parser.add_argument(
        '--book', action='extend', type=_parse_book_path,
        help='paths to any spreadsheet files to load')
    parser.add_argument(
        '--add-graph', action='append',
        help='path to existing graph to add to model')
    parser.add_argument(
        '--model',
        help='path to json file with existing map model')
    parser.add_argument(
        '--model-out', metavar='PATH',
        help='path to write new json file with output map model')
    arg_purge = parser.add_argument(
        '--purge-except', metavar='|'.join(PURGE_MAP.keys()),
        type=PURGE_MAP.get, default='none',
        help='Use named rule to remove some triples from existing model')
    parser.add_argument(
        '--no-resolve-same', action='store_false', dest='resolve_same',
        help='keep triples that mark same identity in output model')
    parser.add_argument(
        '--debug', action='store_true', help='debug interactively any error')
    parser.add_argument(
        '-v', '--verbose', action='store_true', help='show details as turtle')
    parser.add_argument(
        '--from-list', dest='_from_list',
        help='add multiple transforms from a text file of transform names')
    parser.add_argument(
        '--non-unique-from', dest='_non_unique_from',
        help='load non unique triple properties from list of past transforms')
    parser.add_argument(
        'transform', nargs='*',
        help='names of any transforms to run')
    args = parser.parse_args(argv[1:])

    # Load transform lists and report errors from filesystem or content
    args.transform = list(itertools.chain.from_iterable(
        list_from_parser_iter(
            parser, trans.Transform.iter_from_name(name), name
        ) for name in args.transform
    ))
    args.transform[:0] = list_from_parser_iter(
        parser, _transform_list(args._from_list), '--from-list')
    args.non_unique_from = list_from_parser_iter(
        parser, _transform_list(args._non_unique_from), '--non-unique-from')

    if not args.book:
        need_book = set(tf.name for tf in args.transform if tf.uses_sheet())
        if need_book:
            parser.error(f'transforms {need_book} require --book')
    if not args.purge_except:
        parser.error('--purge-except must be one of ' + arg_purge.metavar)
    if args.model_out and not args.model:
        args.model = run.default_model
    return args


def run_runner(runner, args):
    if args.add_graph:
        for graph_to_add in args.add_graph:
            runner.graph.parse(graph_to_add, format='ttl')
        runner.set_terms(iter(runner.graph))

    if args.non_unique_from:
        runner.use_non_uniques(args.non_unique_from)
    if args.add_graph or args.transform:
        runner.run(args.transform)
        if args.model_out:
            runner.save_model(args.model_out)
    elif runner.verbose:
        run.show_graph(runner.graph)


def main(argv):
    args = parse_args(argv)
    with debug.context(args.debug):
        runner = run.Runner.from_args(args)
        run_runner(runner, args)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
