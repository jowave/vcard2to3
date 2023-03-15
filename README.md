# vcard2to3

Convert vcards from version 2.1 to version 3.0.

I wrote these scripts to convert contacts exported from an Android 4.x phone and import them into Nextcloud. It worked for me, your mileage may vary.

The scripts are rather simple, they don't cover all differences between 2.1 and 3.0.


## vcard2to3.py

`vcard2to3.py` is the conversion script.
Quickstart:

    git clone https://github.com/jowave/vcard2to3.git
    cd vcard2to3
    ./vcard2to3.py your_file.vcf

The output will be a file `your_file.vcf.converted`.

To show available command-line arguments run:

    ./vcard2to3.py --help

    usage: vcard2to3.py [-h] [--in_encoding IN_ENCODING]
                        [--out_encoding OUT_ENCODING] [-r REMOVE]
                        [--remove_card REMOVE_CARD] [--remove_dollar]
                        infile [outfile]

    Convert VCard 2.1 to VCard 3.0.

    positional arguments:
      infile                the input filename
      outfile               the output filename, defaults to the input filename
                            with ".converted" appended, this file will be
                            overwritten if it exists

    options:
      -h, --help            show this help message and exit
      --in_encoding IN_ENCODING
                            the encoding of the input file (default: platform
                            dependent)
      --out_encoding OUT_ENCODING
                            the encoding for the output file (default: platform
                            dependent)
      -r REMOVE, --remove REMOVE
                            remove lines matching regex REMOVE, can be given
                            multiple times
      --remove_card REMOVE_CARD
                            remove vcards for which any line matches regex
                            REMOVE_CARD, can be given multiple times
      --remove_dollar       remove "$" in N and FN values

## vcard\_merge.py

Merge and sort vcards. With `vcard_merge.py` you can remove duplicate contacts. The contacts are sorted and merged by `FN` and duplicate lines within one contact are omitted.
You may have to manually edit the result.

## References

* [VCard 3.0](https://tools.ietf.org/html/rfc2426)
* [VCard 4.0](https://tools.ietf.org/html/rfc6350)
