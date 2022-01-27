#!/usr/bin/env python3

import argparse
import re
import itertools
import sys

# FN is required: VCard implementation assumes it is present


class VCard:
    BEGIN = 'BEGIN:VCARD'
    END = 'END:VCARD'
    VERSION = re.compile('VERSION:.*')
    FN = re.compile('FN[:;]')
    N = re.compile('N[:;]')

    def __init__(self):
        self._properties = []
        self._fn_idx = -1
        self._n_idx = []

    def add(self, line):
        if line.startswith(VCard.BEGIN) or line.startswith(VCard.END) or line == '\n':
            return
        if VCard.VERSION.match(line):
            self._version = line
        elif VCard.FN.match(line):
            self._properties.append([line])
            self._fn_idx = len(self._properties)-1
        elif line.startswith('\u0020') or line.startswith('\u0009'):
            # line continuation: https://tools.ietf.org/html/rfc6350#section-3.2
            self._properties[-1].append(line)
        else:
            self._properties.append([line])

    def merge(self, vcard):
        # omit other vcard FN
        self._properties.extend(vcard._properties[0:vcard._fn_idx])
        self._properties.extend(vcard._properties[vcard._fn_idx+1:])
        # take higher version
        if vcard._version > self._version:
            self._version = vcard._version

    def write(self, to):
        to.write(VCard.BEGIN+'\n')
        to.write(self._version)

        self._properties.sort(key=VCard._key)
        self._fn_idx = 0  # FN is now first property
        prev = None
        for p in self._properties:
            if (VCard._different(prev, p)):
                for l in p:
                    to.write(l)
                prev = p
        to.write(VCard.END+'\n')

    def _different(p1, p2):
        if p1 is None and p2 is not None:
            return True
        if p1 is not None and p2 is None:
            return True
        if len(p1) != len(p2):
            return True
        for a, b in zip(p1, p2):
            if a != b:
                return True
        return False

    def _key(a):
        l = len(a)
        if l > 1:
            # multilines come last
            return 'ZZ'+str(l)
        if VCard.FN.match(a[0]):
            # FN comes first
            return '0'+str(a)
        if VCard.N.match(a[0]):
            # N comes second
            return '1'+str(a)
        return a[0]

    def fn_str(self):
        return str(self._properties[self._fn_idx])


def main(argv):
    parser = argparse.ArgumentParser(description='Merge and sort vcards.')
    parser.add_argument('infile')
    parser.add_argument('outfile', nargs='?')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args(argv)

    entries = []
    with open(args.infile) as infile:
        for line in infile:
            if line.startswith(VCard.BEGIN):
                entries.append(VCard())

            entries[-1].add(line)

    if args.verbose:
        print('input entries :', len(entries))
    entries.sort(key=VCard.fn_str)

    # merge
    entries_merged = []
    merged = 0
    current = entries[0]
    for e in entries[1:]:
        if e.fn_str() == current.fn_str():
            current.merge(e)
            merged += 1
        else:
            entries_merged.append(current)
            current = e
    if current != entries_merged[-1]:
        entries_merged.append(current)
    entries = entries_merged
    if args.verbose:
        print('merged entries:', merged)

    # VCard uses '\r\n' new lines (CRLF)
    if args.outfile:
        out_name = args.outfile
    else:
        out_name = args.infile+'.sorted'
    with open(out_name, 'w', newline='\r\n') as outfile:
        for e in entries:
            e.write(outfile)

    if args.verbose:
        print('output entries:', len(entries))


if __name__ == "__main__":
    main(sys.argv[1:])
