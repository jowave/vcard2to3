#!/usr/bin/env python3

import sys
import argparse
import re
import quopri


class VCard:
    BEGIN = 'BEGIN:VCARD'
    END = 'END:VCARD'
    N = re.compile('^N[:;]')
    FN = re.compile('^FN[:;]')
    NICKNAME = re.compile('NICKNAME[:;]')

    def __init__(self):
        self.reset()

    def reset(self):
        self.lines = []
        self._omit = False
        self._n = None
        self._fn = None

    def add(self, line, idx=None):
        if idx is not None:
            self.lines.insert(idx, line)
        else:
            self.lines.append(line)
        if VCard.N.match(line):
            self._n = line
        if VCard.FN.match(line):
            self._fn = line

    def omit(self):
        self._omit = True

    def valid(self):
        return self._n != None and self._fn != None

    def repair(self):
        if self.valid():
            return
        nick_idx = -1
        n_idx = -1
        fn_idx = -1
        for i, l in enumerate(self.lines[1:-1]):
            if VCard.N.match(l):
                n_idx = i+1
            if VCard.FN.match(l):
                fn_idx = i+1
            if VCard.NICKNAME.match(l):
                nick_idx = i+1
        if not self.valid():
            # insert the "equivalent" field after the existing one
            # Arbitrary "convertion": whitespace in FN <-> ';' in N
            # N and FN have precedence over NICKNAME
            if n_idx >= 0 and self._fn is None:
                new_fn = self.lines[n_idx].replace('N', 'FN', 1)
                # split and join the field to handle ';' -> ' '
                new_fn = new_fn.split(':')
                new_fn[1] = ' '.join(new_fn[1].split(';')).strip() + '\n'
                new_fn = ':'.join(new_fn)
                self.add(new_fn, n_idx+1)
            elif fn_idx >= 0 and self._n is None:
                new_n = self.lines[fn_idx].replace('FN', 'N', 1)
                new_n = new_n.split(':')
                # note: if there are more (>=) than 5 items, the supplementary
                #  ones are actually ignored by the vcard2.1/3 standard.
                new_n[1] = ';'.join(new_n[1].split()).strip() + '\n'
                new_n = ':'.join(new_n)
                self.add(new_n, fn_idx+1)
            elif nick_idx >= 0:
                # no N or FN but NICKNAME found, use it
                # note that this loosens the vCard2.1 spec. (NICKNAME unsupported)
                if self._n is None:
                    self.add(self.lines[nick_idx].replace(
                        'NICKNAME', 'N', 1), nick_idx)
                if self._fn is None:
                    self.add(self.lines[nick_idx].replace(
                        'NICKNAME', 'FN', 1), nick_idx)

    def write(self, to):
        if self._omit:
            return
        # If either N, FN or NICKNAME is found, use it for the missing N or FN
        self.repair()
        if not self.valid():
            return
        for line in self.lines:
            to.write(line)


class QuotedPrintableDecoder:
    # Match 'QUOTED-PRINTABLE' with optional preceding or following 'CHARSET'.
    # Note: the value of CHARSET is ignored, decoding is always done using the 'encoding' constructor parameter.
    quoted = re.compile(
        '.*((;CHARSET=.+)?;ENCODING=QUOTED-PRINTABLE(;CHARSET=.+?)?):')

    def __init__(self, encoding='UTF-8'):
        self.encoding = encoding
        self._consumed_lines = ''
        pass

    def __call__(self, line):
        return self.decode(line)

    def decode(self, line):
        line = self._consumed_lines + line  # add potentially stored previous lines
        self._consumed_lines = ''
        m = QuotedPrintableDecoder.quoted.match(line)
        if m:
            # remove the matched group 1 from line (the ';ENCODING=QUOTED-PRINTABLE')
            string_to_decode = line[:m.start(1)] + line[m.end(1):]
            try:
                decoded_line = quopri.decodestring(string_to_decode).decode(self.encoding)
            except Exception as e:
                raise Exception("Failed to decode quoted printable in: '" + line + "'") from e
            # Escape newlines, but preserve the last one (which must be '\n', since we read the file in universal newlines mode)
            decoded_line = decoded_line[:-1].replace('\r\n', '\\n')
            decoded_line = decoded_line.replace('\n', '\\n')
            return decoded_line + '\n'
        return line

    def consume_incomplete(self, line):
        # consume all lines ending with '=', where the first line started the quoted-printable
        if line.endswith('=\n'):
            m = QuotedPrintableDecoder.quoted.match(line)
            if m or len(self._consumed_lines) > 0:
                self._consumed_lines += line
                return True
        return False


class Replacer:
    # Regex to create 'TYPE=' paramter, see also Replacer.type_lc.
    # In the second group match everything up to ':', but don't match if '=' or another ':' is found.
    type_param_re = re.compile('^(TEL|EMAIL|ADR|URL|LABEL|IMPP);([^:=]+:)')

    def __init__(self):
        # array of 2-tuples.
        # Each tuple consists of regular expression object and replacement.
        # Replacement may be a string or a function, see https://docs.python.org/3/library/re.html#re.sub
        self.replace_filters = []
        self.replace_filters.append((re.compile('^VERSION:.*'), 'VERSION:3.0'))
        # self.replace_filters.append( (re.compile('^PHOTO;ENCODING=BASE64;JPEG:'), 'PHOTO:data:image/jpeg;base64,') ) # Version 4.0
        self.replace_filters.append((re.compile(
            '^PHOTO;ENCODING=BASE64;JPEG:'), 'PHOTO;ENCODING=b;TYPE=JPEG:'))  # Version 3.0
        # remove non standard X-INTERNET (not needed for EMAIL anyway)
        self.replace_filters.append((re.compile(';X-INTERNET([;:])'), '\\1'))
        self.replace_filters.append((re.compile(
            '^X-ANDROID-CUSTOM:vnd.android.cursor.item/nickname;([^;]+);.*'), 'NICKNAME:\\1'))
        self.replace_filters.append(
            (re.compile('^X-JABBER(;?.*):(.+)'), 'IMPP\\1:xmpp:\\2'))  # Version 4.0
        self.replace_filters.append(
            (re.compile('^X-ICQ(;?.*):(.+)'), 'IMPP\\1:icq:\\2'))  # Version 4.0
        self.replace_filters.append((Replacer.type_param_re, Replacer.type_lc))
        self.replace_filters.append(
            (re.compile(';PREF([;:])'), ';TYPE=PREF\\1'))  # Version 3.0
        # self.replace_filters.append( (re.compile(';PREF([;:])'), ';PREF=1\\1') ) # Version 4.0
        self.replace_filters.append(
            (re.compile('^EMAIL:([^@]+@jabber.*)'), 'IMPP;xmpp:\\1'))
        self.replace_filters.append(
            (re.compile('^TEL;TYPE=x-mobil:(.*)'), 'TEL;TYPE=cell:\\1'))  # see #9

    def type_lc(matchobj):
        # Example:
        # TEL;CELL;VOICE:+49123456789
        # will become:
        # TEL;TYPE=cell,voice:+49123456789
        return matchobj.group(1)+';TYPE='+matchobj.group(2).lower().replace(";", ",")

    def __call__(self, line):
        return self.replace(line)

    def replace(self, line):
        for r in self.replace_filters:
            line = r[0].sub(r[1], line)
        return line


class Remover:
    def __init__(self, patterns):
        self.filters = []
        if patterns is not None:
            for p in patterns:
                self.filters.append(re.compile(p))

    def __call__(self, line):
        return self.remove(line)

    def remove(self, line):
        for f in self.filters:
            if f.match(line):
                return True
        return False


def main(argv):
    parser = argparse.ArgumentParser(
        description='Convert VCard 2.1 to VCard 3.0.')
    parser.add_argument('infile')
    parser.add_argument('outfile', nargs='?')
    parser.add_argument('--in_encoding', default=sys.getdefaultencoding(),
                        help='the encoding of the input file (default: platform dependent)')
    parser.add_argument('--out_encoding', default=sys.getdefaultencoding(),
                        help='the encoding for the output file (default: platform dependent)')
    parser.add_argument('-r', '--remove', action='append',
                        help='remove lines matching regex REMOVE, can be given multiple times')
    parser.add_argument('--remove_card', action='append',
                        help='remove vcards for which any line matches regex REMOVE, can be given multiple times')
    parser.add_argument('--remove_dollar', action='store_true',
                        help='remove "$" in N and FN values')
    args = parser.parse_args(argv)

    if args.outfile:
        out_name = args.outfile
    else:
        out_name = args.infile+'.converted'

    vcard = VCard()
    decoder = QuotedPrintableDecoder(args.in_encoding)
    replace = Replacer()
    if args.remove_dollar:
        replace.replace_filters.append(
            (re.compile('^(N|FN):([^$]+)\\$'), '\\1:\\2'))
    remove_line = Remover(args.remove if args.remove else None)
    remove_card = Remover(args.remove_card if args.remove_card else None)

    last_line = ''
    # VCard uses '\r\n' new lines (CRLF)
    with open(args.infile, mode='r', encoding=args.in_encoding) as infile, open(out_name, 'w', newline='\r\n', encoding=args.out_encoding) as outfile:
        for line in infile:
            if decoder.consume_incomplete(line):
                continue

            if line.startswith(VCard.BEGIN):
                vcard.reset()

            line = decoder.decode(line)
            line = replace(line)
            if not remove_line(line):
                vcard.add(line)

            if remove_card(line):
                vcard.omit()

            if line.startswith(VCard.END):
                vcard.write(outfile)


if __name__ == "__main__":
    main(sys.argv[1:])
