#!/usr/bin/env python
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
  To update build files for all HALs:
     cd test/vts-testcase/hal; ./script/update_makefiles.py
  To update build files for a specific HAL:
     cd test/vts-testcase/hal; ./script/update_makefiles.py --hal nfc@1.0
"""
import argparse
import re
import sys

from build.build_rule_gen import BuildRuleGen
from utils.const import Constant

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Update build files for HAL driver/profiler.')
    parser.add_argument(
        '--hal',
        dest='hal_package_name',
        required=False,
        help='hal package name (e.g. nfc@1.0).')
    args = parser.parse_args()

    print 'Updating build rules.'
    build_rule_gen = BuildRuleGen(Constant.BP_WARNING_HEADER,
                                  Constant.HAL_PACKAGE_PREFIX,
                                  Constant.HAL_INTERFACE_PATH)

    if args.hal_package_name:
        regex = re.compile(Constant.HAL_PACKAGE_NAME_PATTERN)
        result = re.match(regex, args.hal_package_name)
        if not result:
            print 'Invalid hal package name. Exiting..'
            sys.exit(1)
        package_name, version = args.hal_package_name.split('@')
        hal_list = [(package_name, version)]
        _, updated = build_rule_gen.UpdateHalDirBuildRule(
            hal_list, Constant.VTS_HAL_TEST_CASE_PATH)
    else:
        updated = build_rule_gen.UpdateBuildRule(Constant.VTS_HAL_TEST_CASE_PATH)
    if updated:
        sys.exit(-1)

