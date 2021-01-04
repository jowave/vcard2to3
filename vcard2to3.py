#!/usr/bin/env python3

import sys
import argparse
import re
import quopri

class VCard:
    BEGIN = 'BEGIN:VCARD'
    END = 'END:VCARD'
    FN = re.compile('FN[:;]')
    NICKNAME = re.compile('NICKNAME[:;]')
    def __init__(self, prune_empty=False):
        self.reset()
        self._prune_empty = prune_empty
    def reset(self):
        self.lines = []
        self._omit = False
        self._fn = None
    def add(self, line):
        self.lines.append(line)
        if VCard.FN.match(line):
            self._fn = line
    def omit(self):
        self._omit = True
    def valid(self):
        return self._fn != None
    def write(self, to):
        if self._omit:
            return
        nick_idx = -1
        for i,l in enumerate(self.lines[1:-1]):
            if VCard.NICKNAME.match(l):
                if self._fn and (self._fn[3:] == l[9:]):
                    del(self.lines[i+1]) # NICKNAME == FN => remove nickname
                else:
                    nick_idx = i+1
        if not self.valid() and nick_idx >= 0 and (not self._prune_empty or len(self.lines) > 4):
            # no FN but NICKNAME found, use it
            self.lines[nick_idx] = self.lines[nick_idx].replace('NICKNAME', 'FN', 1)
            self._fn = self.lines[nick_idx]
            nick_idx = -1
        if not self.valid():
            return
        for line in self.lines:
            to.write(line)

class QuotedPrintableDecoder:
    # Match 'QUOTED-PRINTABLE' with optional preceding or following 'CHARSET'.
    # Note: the value of CHARSET is ignored, decoding is always to UTF-8.
    quoted = re.compile('.*((;CHARSET=.+)?;ENCODING=QUOTED-PRINTABLE(;CHARSET=.+?)?):')
    def __init__(self):
        self._consumed_lines = ''
        pass

    def __call__(self, line):
        return self.decode(line)

    def decode(self, line):
        line = self._consumed_lines + line # add potentially stored previous lines
        self._consumed_lines = ''
        m = QuotedPrintableDecoder.quoted.match(line)
        if m:
            line = line[:m.start(1)] + line[m.end(1):] # remove the matched group 1 from line
            decoded_line = quopri.decodestring(line).decode('UTF-8')
            # Escape newlines, but preserve the last one (which must be '\n', since we read the file in universal newliens mode)
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
    def __init__(self):
        self.replace_filters = [] # array of 2-tuples. Each tuple consists of regular expression object and replacement. Replacement may be a string or a function, see https://docs.python.org/3/library/re.html#re.sub
        self.replace_filters.append( (re.compile('^VERSION:.*'), 'VERSION:3.0') )
        #self.replace_filters.append( (re.compile('^PHOTO;ENCODING=BASE64;JPEG:'), 'PHOTO:data:image/jpeg;base64,') ) # Version 4.0
        self.replace_filters.append( (re.compile('^PHOTO;ENCODING=BASE64;JPEG:'), 'PHOTO;ENCODING=b;TYPE=JPEG:')) # Version 3.0
        self.replace_filters.append( (re.compile(';X-INTERNET([;:])'), '\\1') )
        self.replace_filters.append( (re.compile('^X-ANDROID-CUSTOM:vnd.android.cursor.item/nickname;([^;]+);.*'), 'NICKNAME:\\1') )
        self.replace_filters.append( (re.compile(';PREF([;:])'), ';TYPE=PREF\\1') ) # Version 3.0
        #self.replace_filters.append( (re.compile(';PREF([;:])'), ';PREF=1\\1') ) # Version 4.0
        self.replace_filters.append( (re.compile('^X-JABBER(;?.*):(.+)'), 'IMPP\\1:xmpp:\\2') ) # Version 4.0
        self.replace_filters.append( (re.compile('^X-ICQ(;?.*):(.+)'), 'IMPP\\1:icq:\\2') ) # Version 4.0
        self.replace_filters.append( (re.compile('^(TEL|EMAIL|ADR|URL|LABEL|IMPP);([^;:=]+[;:])'), Replacer.type_lc) )
        self.replace_filters.append( (re.compile('^EMAIL:([^@]+@jabber.*)'), 'IMPP;xmpp:\\1') )
        self.replace_filters.append( (re.compile('^TEL;TYPE=x-mobil:(.*)'), 'TEL;TYPE=cell:\\1') ) # see #9

    def type_lc(matchobj):
        # Example:
        # TEL;CELL;VOICE:+49123456789
        # will become:
        # TEL;TYPE=cell;VOICE:+49123456789
        return matchobj.group(1)+';TYPE='+matchobj.group(2).lower()


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
    parser = argparse.ArgumentParser(description='Convert VCard 2.1 to VCard 3.0.')
    parser.add_argument('infile')
    parser.add_argument('outfile', nargs='?')
    parser.add_argument('--in_encoding', help='the encoding of the input file (default: platform dependent)')
    parser.add_argument('--out_encoding', help='the encoding for the output file (default: platform dependent)')
    parser.add_argument('-r', '--remove', action='append', help='remove lines matching regex REMOVE, can be given multiple times')
    parser.add_argument('--remove_card', action='append', help='remove vcards for which any line matches regex REMOVE, can be given multiple times')
    parser.add_argument('--remove_dollar', action='store_true', help='remove "$" in N and FN values')
    parser.add_argument('-p', '--prune_empty', action='store_true', help='remove vcards which have only FN but no additional fields')
    args = parser.parse_args(argv)

    if args.outfile:
        out_name = args.outfile
    else:
        out_name = args.infile+'.converted'

    vcard = VCard(True if args.prune_empty else False)
    decoder = QuotedPrintableDecoder()
    replace = Replacer()
    if args.remove_dollar:
        replace.replace_filters.append( (re.compile('^(N|FN):([^$]+)\$'), '\\1:\\2') )
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
