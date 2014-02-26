#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""
Convenience wrapper for testing development version of timegaps CLI without
installing. With the root directory of this repository as CWD, timegaps can be
invoked via

$ python timegaps-runner.py 


The canonical way would be (http://stackoverflow.com/a/3617928/145400):

$ python -m timegaps.main


Note: after installation with setuptools, a `timegaps` command is available:

$ python setup.py install; timegaps

"""


from timegaps.main import main


if __name__ == '__main__':
    main()

