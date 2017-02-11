#!/usr/bin/env python3.4
#
# Copyright (C) 2016 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Update .bp and .mk files under test/vts-testcase/hal.

Among .bp and .mk files affected are:
1. test/vts-testcase/hal/Android.bp
2. files matching: test/vts-testcase/hal/<hal_name>/<hal_version>/Android.bp

Usage:
  cd test/vts-testcase/hal && python update_makefiles.py
"""

from build.build_rule_gen import UpdateBuildRule
import os
import sys

if __name__ == "__main__":
    usage = (
    'Need to run from test/vts-testcase/hal!!!\n\n'
    'Updates .bp and .mk files under test/vts-testcase/hal.\n'
    'Among .bp and .mk files affected are:\n'
    '1. test/vts-testcase/hal/Android.bp\n'
    '2. files matching: test/vts-testcase/hal/<hal_name>/<hal_version>/Android.bp\n\n'
    'Usage:\n'
    '  cd test/vts-testcase/hal && python update_makefiles.py\n')

    PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
    CWD = os.getcwd()
    if CWD != PROJECT_DIR:
        print usage
        sys.exit(1)

    print 'Updating build rules.'
    UpdateBuildRule()
