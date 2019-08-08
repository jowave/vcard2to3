# vcard2to3

Convert vcards from version 2.1 to version 3.0.

I wrote these scripts to convert contacts exported from an Android 4.x phone and import them into Nextcloud. It worked for me, your mileage may vary.

## vcard2to3.py

`vcard2to3.py` is the conversion script.
Quickstart:

    git clone https://github.com/jowave/vcard2to3.git
    cd vcard2to3
    ./vcard2to3.py your_file.vcf
    
The output will be a file `your_file.vcf.converted`.

To show available command-line arguments run:

    ./vcard2to3.py --help

## vcard_merge.py

Merge and sort vcards. With `vcard_merge.py` you can remove duplicate contacts. The contacts are sorted and merged by `FN` and duplicate lines within one contact are omitted.
You may have to manually edit the result.

## References

* [VCard 3.0](https://tools.ietf.org/html/rfc2426)
* [VCard 4.0](https://tools.ietf.org/html/rfc6350)
