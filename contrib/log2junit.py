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

def get_log_snippet(logdata, start, line):
    """Given a log LOGDATA and a start point START, return string indexes
    in slice notation indicating the log snippet up until line, and a new search
    point for the next log extraction."""
    if not logdata:
        return (0, 0), 0
    cutoff = logdata.find(line, start)
    if cutoff == -1:
        print(f'Error finding "{line}"')
        print(f'  Search buffer started: "{logdata[start:start+100]}"')
        raise ValueError
    return (start, cutoff), cutoff + len(line)

def get_log_for_sum(sumpath):
    """For sum file INPATH, get the log file contents for this test run,
    returning an empty string if the log is not available."""
    try:
        if sumpath[-8:] == '.sum.sep':
            logpath = sumpath[:-8] + '.log.sep'
            return open(logpath, 'r').read()
        elif sumpath[-4:] == ".sum":
            logpath = sumpath[:-4] + '.log'
            return open(logpath, 'r').read()
        else:
            raise ValueError
    except ValueError:
        print(f'Unsupported sum filename {sumpath}')
        return ''
    except IOError:
        print(f'Unable to load log for {sumpath}')
        return ''

def analyze(inpath, outpath, prefix):
    """Analyze the testfile INFILE and output results to OUTPATH."""
    infile = open(inpath, 'r')
    outfile = open(outpath, 'w')
    logdata = get_log_for_sum(inpath)
    logindex = 0

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
            _, logindex = get_log_snippet(logdata, logindex, line)
            tool = line.split(' ')[1]
            print(f'tool: {tool}')
        elif line.startswith('Running target '):
            _, logindex = get_log_snippet(logdata, logindex, line)
            # Convert variation name to a suitable namespace
            variation = line.split(' ')[2]
            variation = variation.replace('/-', '_')
            variation = variation.replace('/', '_')
            tests = []
            log_to_print = True
            print(f'variation: {variation}')
        elif line.startswith(f'\t\t=== {tool} Summary'):
            _, logindex = get_log_snippet(logdata, logindex, line)
            # For multi-variation logs only print summaries once
            if log_to_print:
                print(f'Printing log')
                print_testsuite(outfile, prefix, tool, variation, tests)
            log_to_print = False
        else:
            for res_ty in Result:
                if line.startswith(f'{res_ty.name}: '):
                    lineindex, logindex = get_log_snippet(logdata, logindex, line)
                    testname = line.split(' ', 1)[1]
                    testlog = logdata[lineindex[0]:lineindex[1]]
                    tests.append((res_ty, testname, testlog))

    # Write XML footer
    outfile.write('</testsuites>')

def sanitize_data(data):
    """Returns XML safe logdata"""
    invalid_chars = {}
    for char in range(0x0, 0x9):
        invalid_chars[char] = None
    for char in range(0xb, 0xd):
        invalid_chars[char] = None
    for char in range(0xe, 0x20):
        invalid_chars[char] = None
    data = data.translate(invalid_chars)
    return data

def sanitize_name(testname):
    """Returns XML safe testname"""
    testname = sanitize_data(testname)
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
        outfile.write(f'<testcase name={sanitize_name(test[1])}>\n')
        if test[2]:
            outfile.write(f'  <system-out><![CDATA[{sanitize_data(test[2])}]]></system-out>\n')
        if test[0] == Result.FAIL:
            outfile.write('  <failure type="FAIL">Test failed.</failure>\n')
        # XFAIL/XPASS do not exist in JUnit, so treat as PASS/FAIL
        elif test[0] == Result.XPASS:
            outfile.write('  <failure type="XPASS">Test unexpectedly passed.</failure>\n')
        # Treat KFAIL/KPASS as PASS/FAIL as with XFAIL/XPASS
        elif test[0] == Result.KPASS:
            outfile.write('  <failure type="KPASS">Test unexpectedly passed.</failure>\n')
        elif test[0] == Result.UNSUPPORTED:
            outfile.write('  <skipped>Test unsupported.</skipped>\n')
        elif test[0] == Result.UNTESTED:
            outfile.write('  <skipped message="Test untested."/>\n')
        # This script treats UNRESOLVED as errors
        elif test[0] == Result.UNRESOLVED:
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
