#!/usr/bin/env python3

# sum2junit.py -- convert a .sum file into Junit-compatible XML
#
# Copyright (C) 2020 Embecosm Limited.
# Contributed by Simon Cook <simon.cook@embecosm.com>
#
# This file is part of DejaGnu.
#
# DejaGnu is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# Unlike the shell variant, this prints out all tests in a sum file and handles
# sum files which contain multiple test variants

from enum import Enum
from xml.sax.saxutils import quoteattr
import sys

class Result(Enum):
    PASS = 1
    FAIL = 2
    XFAIL = 3
    XPASS = 4
    UNRESOLVED = 5
    UNTESTED = 6
    UNSUPPORTED = 7
    KFAIL = 8
    KPASS = 9

def analyze(inpath, outpath, prefix):
    """Analyze the testfile INFILE and output results to OUTPATH."""
    infile = open(inpath, 'r')
    outfile = open(outpath, 'w')
    # Write XML header
    outfile.write('<?xml version="1.0" ?>\n<testsuites>\n')

    tool = None
    variation = None
    tests = []
    log_to_print = False
    # Process each line in the sumfile, and print detailed logs for each
    # variant as its own test class
    # (Unlike sum2unit.sh include the variant in the name for tracking PASSes)
    for line in infile.readlines():
        line = line.strip('\r\n')
        if line.endswith('tests ==='):
            tool = line.split(' ')[1]
            print(f'tool: {tool}')
        elif line.startswith('Running target '):
            # Convert variation name to a suitable namespace
            variation = line.split(' ')[2]
            variation = variation.replace('/-', '_')
            variation = variation.replace('/', '_')
            tests = []
            log_to_print = True
            print(f'variation: {variation}')
        elif line.startswith(f'\t\t=== {tool} Summary'):
            # For multi-variation logs only print summaries once
            if log_to_print:
                print(f'Printing log')
                print_testsuite(outfile, prefix, tool, variation, tests)
            log_to_print = False
        else:
            for res_ty in Result:
                if line.startswith(f'{res_ty.name}: '):
                    testname = line.split(' ', 1)[1]
                    tests.append((res_ty, testname))

    # Write XML footer
    outfile.write('</testsuites>')

def sanitize_name(testname):
    """Returns XML safe testname"""
    invalid_chars = {}
    for char in range(0x0, 0x9):
        invalid_chars[char] = None
    for char in range(0xb, 0xd):
        invalid_chars[char] = None
    for char in range(0xe, 0x20):
        invalid_chars[char] = None
    testname = testname.translate(invalid_chars)
    return quoteattr(testname)

def print_testsuite(outfile, prefix, tool, variation, tests):
    """Prints XML testsuite to OUTFILE"""
    tests_count = len(tests)
    fail_count = len([test for test in tests if test[0] == Result.FAIL or \
                                                test[0] == Result.XPASS or \
                                                test[0] == Result.KPASS])
    skip_count = len([test for test in tests if test[0] == Result.UNSUPPORTED or \
                                                test[0] == Result.UNTESTED])
    error_count = len([test for test in tests if test[0] == Result.UNRESOLVED])
    outfile.write(f'<testsuite name="{prefix}.{tool}.{variation}" tests="{tests_count}"'\
                  f' failures="{fail_count}" skipped="{skip_count}" errors="{error_count}">\n')
    for test in tests:
        if test[0] == Result.PASS:
            outfile.write(f'<testcase name={sanitize_name(test[1])}/>\n')
        elif test[0] == Result.FAIL:
            outfile.write(f'<testcase name={sanitize_name(test[1])}>\n')
            outfile.write('  <failure type="FAIL">Test failed.</failure>\n')
            outfile.write('</testcase>\n')
        # XFAIL/XPASS do not exist in JUnit, so treat as PASS/FAIL
        elif test[0] == Result.XFAIL:
            outfile.write(f'<testcase name={sanitize_name(test[1])}/>\n')
        elif test[0] == Result.XPASS:
            outfile.write(f'<testcase name={sanitize_name(test[1])}>\n')
            outfile.write('  <failure type="XPASS">Test unexpectedly passed.</failure>\n')
            outfile.write('</testcase>\n')
        # Treat KFAIL/KPASS as PASS/FAIL as with XFAIL/XPASS
        elif test[0] == Result.KFAIL:
            outfile.write(f'<testcase name={sanitize_name(test[1])}/>\n')
        elif test[0] == Result.KPASS:
            outfile.write(f'<testcase name={sanitize_name(test[1])}>\n')
            outfile.write('  <failure type="KPASS">Test unexpectedly passed.</failure>\n')
            outfile.write('</testcase>\n')
        elif test[0] == Result.UNSUPPORTED:
            outfile.write(f'<testcase name={sanitize_name(test[1])}>\n')
            outfile.write('  <skipped>Test unsupported.</skipped>\n')
            outfile.write('</testcase>\n')
        elif test[0] == Result.UNTESTED:
            outfile.write(f'<testcase name={sanitize_name(test[1])}>\n')
            outfile.write('  <skipped message="Test untested."/>\n')
            outfile.write('</testcase>\n')
        # This script treats UNRESOLVED as errors
        elif test[0] == Result.UNRESOLVED:
            outfile.write(f'<testcase name={sanitize_name(test[1])}>\n')
            outfile.write('  <error type="UNRESOLVED">Test result unresolved.</error>\n')
            outfile.write('</testcase>\n')
    outfile.write(f'</testsuite>\n')

if __name__ == "__main__":
    if len(sys.argv) == 3:
        analyze(sys.argv[1], sys.argv[2], 'DejaGnu')
    elif len(sys.argv) == 4:
        analyze(sys.argv[1], sys.argv[2], sys.argv[3])
    else:
        print(f'Usage: {sys.argv[0]} infile outfile [testprefix]')
        sys.exit(1)
