#
# Copyright 2018 - The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

class Constant(object):
    """Constant values used in scripts. """

    # Default path that stores the Google defined HAL interface.
    HAL_INTERFACE_PATH = 'hardware/interfaces'
    # Default package root for Google defined HAL interface.
    HAL_PACKAGE_PREFIX = 'android.hardware'
    # Default path that stores HAL traces, used for replay tests.
    HAL_TRACE_PATH = 'test/vts-testcase/hal-trace'
    # Default path for VTS test configure files.
    VTS_HAL_TEST_CASE_PATH = 'test/vts-testcase/hal'
