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

import os

from vts_spec_parser import VtsSpecParser
import build_rule_gen_utils as utils


class BuildRuleGen(object):
    """Build rule generator for test/vts-testcase/hal."""
    _ANDROID_BUILD_TOP = os.environ.get('ANDROID_BUILD_TOP')
    if not _ANDROID_BUILD_TOP:
        print 'Run "lunch" command first.'
        sys.exit(1)
    _PROJECT_PATH = os.path.join(_ANDROID_BUILD_TOP, 'test', 'vts-testcase',
                                 'hal')
    _VTS_BUILD_TEMPLATE = os.path.join(_PROJECT_PATH, 'script', 'build',
                                       'template', 'vts_build_template.bp')

    def __init__(self):
        """BuildRuleGen constructor."""
        self._vts_spec_parser = VtsSpecParser()

    def UpdateBuildRule(self):
        """Updates build rules under test/vts-testcase/hal."""
        hal_list = self._vts_spec_parser.HalNamesAndVersions()
        self.UpdateTopLevelBuildRule()
        self.UpdateHalDirBuildRule(hal_list)

    def UpdateTopLevelBuildRule(self):
        """Updates test/vts-testcase/hal/Android.bp"""
        utils.WriteBuildRule(
            os.path.join(self._PROJECT_PATH, 'Android.bp'),
            self._TopLevelBuildRule())

    def UpdateSecondLevelBuildRule(self, hal_list):
        """Updates test/vts-testcase/hal/<hal_name>/Android.bp"""
        top_level_dirs = dict()
        for target in hal_list:
            hal_dir = os.path.join(
                utils.HalNameDir(target[0]), utils.HalVerDir(target[1]))
            top_dir = hal_dir.split('/', 1)[0]
            top_level_dirs.setdefault(
                top_dir, []).append(os.path.relpath(hal_dir, top_dir))

        for k, v in top_level_dirs.items():
            file_path = os.path.join(self._PROJECT_PATH, k, 'Android.bp')
            utils.WriteBuildRule(file_path, self._SecondLevelBuildRule(v))

    def UpdateHalDirBuildRule(self, hal_list):
        """Updates build rules for vts drivers/profilers.

        Updates vts drivers/profilers for each pair of (hal_name, hal_version)
        in hal_list.

        Args:
            hal_list: list of tuple of strings. For example,
                [('vibrator', '1.3'), ('sensors', '1.7')]
        """
        for target in hal_list:
            hal_name = target[0]
            hal_version = target[1]

            file_path = os.path.join(self._PROJECT_PATH,
                                     utils.HalNameDir(hal_name),
                                     utils.HalVerDir(hal_version), 'Android.bp')

            utils.WriteBuildRule(file_path, self._VtsBuildRuleFromTemplate(
                self._VTS_BUILD_TEMPLATE, hal_name, hal_version))

    def _TopLevelBuildRule(self):
        """Returns build rules for test/vts-testcase/hal/Android.bp.

        Args:
          hal_list: list of tuple of strings. For example,
              [('vibrator', '1.3'), ('sensors', '1.7')]
        """
        result = '// This file was auto-generated. Do not edit manually.\n'
        result += 'subdirs = [\n'
        result += '    "*",\n'
        result += ']\n'
        return result

    def _SecondLevelBuildRule(self, hal_subdirs):
        """Returns build rules for test/vts-testcase/hal/*/Android.bp.

        Args:
          hal_subname: list of strings, sub-dirs of the hal,
              e.g. for 'audio/effect/1.0' it would be 'effect/V1_0'.
        """
        result = 'subdirs = [\n'
        for subdir in hal_subdirs:
            result += '    "%s",\n' % subdir
        result += ']\n'
        return result

    def _VtsBuildRuleFromTemplate(self, template_path, hal_name, hal_version):
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
        return self._FillOutBuildRuleTemplate(hal_name, hal_version,
                                              build_template)

    def _FillOutBuildRuleTemplate(self, hal_name, hal_version, template):
        """Returns build rules in string form by filling out given template.

        Args:
          hal_name: string, name of the hal, e.g. 'vibrator'.
          hal_version: string, version of the hal, e.g '7.4'
          template: string, build rule template to fill out.

        Returns:
          string, complete build rule in string form.
        """

        def GeneratedOutput(hal_name, hal_version, extension):
            """Formats list of vts spec names into a string.

            Formats list of vts spec name for given hal_name, hal_version
            into a string that can be inserted into build template.

            Args:
              hal_name: string, name of the hal, e.g. 'vibrator'.
              hal_version: string, version of the hal, e.g '7.4'
              extension: string, extension of files e.g. '.cpp'.

            Returns:
              string, to be inserted into build template.
            """
            result = []
            vts_spec_names = self._vts_spec_parser.VtsSpecNames(hal_name,
                                                                hal_version)
            for vts_spec in vts_spec_names:
                result.append('"android/hardware/%s/%s/%s%s",' %
                              (utils.HalNameDir(hal_name), hal_version,
                               vts_spec, extension))
            return '\n        '.join(result)

        def ImportedDriverPackages(imported_packages):
            """Formats list of imported packages into a string.

            Formats list of imported packages for given hal_name, hal_version
            into a string that can be inserted into build template.

            Args:
              imported_packages: list of imported packages

            Returns:
              string, to be inserted into build template.
            """
            result = []
            for package in imported_packages:
                prefix = 'android.hardware.'
                if package.startswith(prefix):
                    vts_driver_name = package.replace('@', '.vts.driver@')
                    result.append('"%s",' % vts_driver_name)
                else:
                    result.append('"%s",' % package)
            return '\n        '.join(result)

        def ImportedProfilerPackages(imported_packages):
            """Formats list of imported packages into a string.

            Formats list of imported packages for given hal_name, hal_version
            into a string that can be inserted into build template.

            Args:
              imported_packages: list of imported packages

            Returns:
              string, to be inserted into build template.
            """
            result = []
            for package in imported_packages:
                prefix = 'android.hardware.'
                if package.startswith(prefix):
                    vts_driver_name = package + "-vts.profiler"
                    result.append('"%s",' % vts_driver_name)
                else:
                    result.append('"%s",' % package)
            return '\n        '.join(result)

        build_rule = template
        build_rule = build_rule.replace('{HAL_NAME}', hal_name)
        build_rule = build_rule.replace('{HAL_NAME_DIR}',
                                        utils.HalNameDir(hal_name))
        build_rule = build_rule.replace('{HAL_VERSION}', hal_version)
        build_rule = build_rule.replace(
            '{GENERATED_VTS_SPECS}',
            GeneratedOutput(hal_name, hal_version, ''))
        build_rule = build_rule.replace(
            '{GENERATED_SOURCES}',
            GeneratedOutput(hal_name, hal_version, '.cpp'))
        build_rule = build_rule.replace(
            '{GENERATED_HEADERS}', GeneratedOutput(hal_name, hal_version, '.h'))

        imported_packages = self._vts_spec_parser.ImportedPackagesList(
            hal_name, hal_version)
        build_rule = build_rule.replace(
            '{IMPORTED_DRIVER_PACKAGES}',
            ImportedDriverPackages(imported_packages))
        build_rule = build_rule.replace(
            '{IMPORTED_PROFILER_PACKAGES}',
            ImportedProfilerPackages(imported_packages))

        return build_rule
