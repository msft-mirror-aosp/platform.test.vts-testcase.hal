#!/usr/bin/env python3.4
#
# Copyright (C) 2017 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import fnmatch
import os

HW_IFACE_DIR = '../../../hardware/interfaces/'
VTS_DRIVER_BUILD_TEMPLATE = 'build/template/vts_driver_build_template.bp'
VTS_PROFILER_BUILD_TEMPLATE = 'build/template/vts_profiler_build_template.bp'


def UpdateBuildRule():
    """Updates build rules under test/vts-testcase/hal."""

    def HalList():
        """Returns a list of hals and version present under hardware/interfaces.

    Returns:
      List of tuples of strings containing hal names and hal versions. For example,
      [('vibrator', '1.3'), ('sensors', '1.7')]
    """
        result = []
        for base, dirs, files in os.walk(HW_IFACE_DIR):
            pattern = HW_IFACE_DIR + '*/[0-9].[0-9]'
            if fnmatch.fnmatch(base, pattern) and 'tests' not in base:
                hal_dir = base[len(HW_IFACE_DIR):]
                hal_dir = hal_dir.rsplit('/', 1)
                hal_name = hal_dir[0].replace('/', '.')
                hal_version = hal_dir[1]
                result.append((hal_name, hal_version))
        return result

    hal_list = HalList()
    UpdateTopLevelBuildRule(hal_list)
    UpdateHalDirBuildRule(hal_list)


def UpdateTopLevelBuildRule(hal_list):
    """Updates test/vts-testcase/hal/Android.bp"""
    WriteBuildRule('./Android.bp', TopLevelBuildRule(hal_list))


def UpdateHalDirBuildRule(hal_list):
    """Updates build rules for vts drivers/profilers.

  Updates vts drivers/profilers for each pair of (hal_name, hal_version) in hal_list.

  Args:
    hal_list: list of tuple of strings. For example,
        [('vibrator', '1.3'), ('sensors', '1.7')]
  """
    for target in hal_list:
        hal_name = target[0]
        hal_version = target[1]
        hal_name_dir = hal_name.replace('.', '/')
        hal_version_dir = 'V' + hal_version.replace('.', '_')

        file_path = './%s/%s/Android.bp' % (hal_name_dir, hal_version_dir)
        WriteBuildRule(file_path, HalDirBuildRule())

        file_path = './%s/%s/driver/Android.bp' % (hal_name_dir,
                                                   hal_version_dir)
        WriteBuildRule(file_path, VtsBuildRuleFromTemplate(
            VTS_DRIVER_BUILD_TEMPLATE, hal_name, hal_version))

        file_path = './%s/%s/profiler/Android.bp' % (hal_name_dir,
                                                     hal_version_dir)
        WriteBuildRule(file_path, VtsBuildRuleFromTemplate(
            VTS_PROFILER_BUILD_TEMPLATE, hal_name, hal_version))


def WriteBuildRule(file_path, build_rule):
    """Writes the build rule into specified file.

  Opens file_path and writes build_rule into it. Creates intermediate directories if necessary.

  Args:
    file_path: string, path to file to which to write.
    build_rule: string, build rule to be written into file.
  """
    dir_path = os.path.dirname(file_path)

    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

    with open(file_path, 'w') as bp_file:
        bp_file.write(build_rule)


def TopLevelBuildRule(hal_list):
    """Returns build rules for test/vts-testcase/hal/Android.bp.

  Args:
    hal_list: list of tuple of strings. For example,
        [('vibrator', '1.3'), ('sensors', '1.7')]
  """
    result = 'subdirs = [\n'
    for target in hal_list:
        hal_name = target[0]
        hal_version = target[1]
        hal_name_dir = hal_name.replace('.', '/')
        hal_version_dir = 'V' + hal_version.replace('.', '_')
        hal_dir = '%s/%s/' % (hal_name_dir, hal_version_dir)
        result += '    "%s",\n' % hal_dir
    result += ']\n'
    return result


def HalDirBuildRule():
    return 'subdirs = ["*"]\n'


def VtsBuildRuleFromTemplate(template_path, hal_name, hal_version):
    """Returns build rules in string form by filling out a template.

  Reads template from given path and fills it out.

  Args:
    template_path: string, path to build rule template file.
    hal_name: string, name of the hal, e.g. 'vibrator'.
    hal_version: string, version of the hal, e.g '7.4'

  Returns:
    string, complete build rules in string form
  """
    with open(template_path) as template_file:
        build_template = str(template_file.read())
    return FillOutBuildRuleTemplate(build_template, hal_name, hal_version)


def FillOutBuildRuleTemplate(template, hal_name, hal_version):
    """Returns build rules in string form by filling out given template.

  Args:
    template: string, build rule template to fill out.
    hal_name: string, name of the hal, e.g. 'vibrator'.
    hal_version: string, version of the hal, e.g '7.4'

  Returns:
    string, complete build rule in string form.
  """

    def HalSpecToVtsSpecName(hal_spec_name):
        """Transforms hal spec name to its corresponding vts spec name.

    Args:
      hal_spec_name: string, name of hal file, e.g. 'IVibrator.hal'.
    Returns:
      string, name of hal file, e.g. 'Vibrator.vts'.
    """
        vts_spec_name = hal_spec_name.replace('.hal', '.vts')
        if vts_spec_name != 'types.vts':
            vts_spec_name = vts_spec_name[1:]
        return vts_spec_name

    def VtsSpecList(hal_name, hal_version):
        """Returns list of .vts files for given hal name and version.

    hal_name: string, name of the hal, e.g. 'vibrator'.
    hal_version: string, version of the hal, e.g '7.4'

    Returns:
      list of string, .vts files for given hal name and version,
          e.g. ['Vibrator.vts', 'types.vts']
    """
        hal_files_dir = '%s/%s/%s/' % (HW_IFACE_DIR, hal_name.replace(
            '.', '/'), hal_version)
        hal_spec_list = filter(lambda x: x.endswith('.hal'),
                               os.listdir(hal_files_dir))
        vts_spec_list = map(HalSpecToVtsSpecName, hal_spec_list)
        return vts_spec_list

    def GeneratedOutput(hal_name, hal_version, extension):
        result = []
        for vts_spec in VtsSpecList(hal_name, hal_version):
            result.append('"android/hardware/%s/%s/%s%s",' % (
                hal_name.replace('.', '/'), hal_version, vts_spec, extension))
        return '\n        '.join(result)

    build_rule = template
    build_rule = build_rule.replace('{HAL_NAME}', hal_name)
    build_rule = build_rule.replace('{HAL_NAME_DIR}', hal_name.replace('.',
                                                                       '/'))
    build_rule = build_rule.replace('{HAL_VERSION}', hal_version)
    build_rule = build_rule.replace(
        '{GENERATED_SOURCES}', GeneratedOutput(hal_name, hal_version, '.cpp'))
    build_rule = build_rule.replace(
        '{GENERATED_HEADERS}', GeneratedOutput(hal_name, hal_version, '.h'))

    return build_rule
