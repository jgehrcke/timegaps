#!/bin/bash
echo ">>> Running timegaps unit tests."
cd test && py.test test_api.py test_cmdline.py
cd ..
echo -e "\n>>> Running setup.py check..."
python setup.py check
echo -e "\n>>> Running python setup.py --long-description | rst2html.py > /dev/null..."
python setup.py --long-description | rst2html.py > /dev/null
echo -e "\n>>> Running rst2html.py CHANGELOG.rst > /dev/null..."
rst2html.py CHANGELOG.rst > /dev/null
echo -e "\n>>> Running PEP8 check..."
pep8 timegaps/*.py
echo -e "\n>>> Running pylint..."
pylint --reports=n --disable=C0103,W0212,W0511,W0142,R0903 \
    timegaps/main.py \
    timegaps/timegaps.py \
    timegaps/timefilter.py
