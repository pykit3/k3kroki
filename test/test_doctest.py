import doctest

import k3kroki


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(k3kroki))
    return tests
