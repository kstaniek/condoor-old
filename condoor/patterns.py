# =============================================================================
#
# Copyright (c) 2016, Cisco Systems
# All rights reserved.
#
# # Author: Klaudiusz Staniek
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
# Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
# THE POSSIBILITY OF SUCH DAMAGE.
# =============================================================================


import os
import re
import json
import yaml


class PatternManager(object):
    def __init__(self, pattern_dict):
        self._dict = pattern_dict
        #self._dict_compiled = self._compile_patterns()

    def _compile_patterns(self):

        dict_compiled = {}
        for platform, patterns in self._dict.items():
            dict_compiled[platform] = {}
            for key, pattern in patterns.items():
                try:
                    compiled = None
                    if isinstance(pattern, str):
                        compiled = re.compile(pattern)
                    elif isinstance(pattern, dict):
                        compiled = re.compile(pattern['pattern'])
                    if compiled:
                        dict_compiled[platform][key] = compiled

                except re.error as e:
                    raise RuntimeError("Pattern compile error: {} ({}:{})".format(e.message, platform, key))


        return dict_compiled

    def _get_platform_patterns(self, platform):

        patterns = self._dict.get(platform, None)

        if patterns is None:
            raise KeyError("Unknown platform".format(platform))

        generic_patterns = self._dict.get('generic', None)

        if generic_patterns is None:
            raise RuntimeError("Patterns database corrupted. Platform: {}".format(platform))

        return patterns, generic_patterns

    def _get_all_patterns(self, key, compiled=True):
        # get of unique list of platforms
        patterns = set()
        platforms = list(set([platform for platform in self._dict.keys() if platform is not None]))
        for platform in platforms:
            try:
                patterns |= set(self.get_pattern(platform, key, compiled=False).split('|'))
            except KeyError:
                continue

        if not patterns:
            raise KeyError("Pattern not found: {}".format(key))

        patterns_re = "|".join(list(patterns))

        if compiled:
            return re.compile(patterns_re)
        else:
            return patterns_re

    def get_pattern(self, platform, key, compiled=True):
        """
        Returns the pattern defined by the key string specific to the platform.
        :param platform:
        :param key:
        :param compiled:
        :return: Pattern string or RE object.
        """

        patterns, generic_patterns = self._get_platform_patterns(platform)
        pattern = patterns.get(key, generic_patterns.get(key, None))

        if isinstance(pattern, dict):
            pattern = pattern.get('pattern', None)

        # list of references to other platforms
        if isinstance(pattern, list):
            pattern_set = set()
            for platform in pattern:
                try:
                    pattern_set |= set(self.get_pattern(platform, key, compiled=False).split('|'))
                except KeyError:
                    continue
            pattern = "|".join(pattern_set)

        if pattern is None:
            raise KeyError("Patterns database corrupted. Platform: {}, Key: {}".format(platform, key))

        if compiled:
            return re.compile(pattern)
        else:
            return pattern

    def get_pattern_description(self, platform, key, compiled=True):
        patterns, generic_patterns = self._get_platform_patterns(platform, compiled=compiled)
        pattern = patterns.get(key, generic_patterns.get(key, None))
        if isinstance(pattern, dict):
            description = pattern.get('description', None)
        else:
            description = key

        return description


class YPatternManager(PatternManager):
    def __init__(self, config_file_path=None):
        if config_file_path is None:
            scriptname = os.path.splitext(os.path.abspath(__file__))[0]
            config_file_path = os.getenv(scriptname.upper() + 'CFG', scriptname + '.yaml')

        pattern_dict = self._read_config(config_file_path)
        super(YPatternManager, self).__init__(pattern_dict=pattern_dict)

    def _read_config(self, config_file_path):
        config = {}
        with open(config_file_path, 'r') as ymlfile:
            config = yaml.load(ymlfile)

        return config



#ypm = YPatternManager()
#print(ypm.get_pattern("generic", "syntax_error", compiled=False))
#print(ypm.get_pattern("generic", "syntax_error").pattern)


#print(ypm._get_all_patterns('rommon').pattern)

#print(ypm._get_all_patterns('rommon', compiled=False))

#print(ypm._get_all_patterns('dupa'))

#print(ypm.get_pattern("XR", "connection_closed", compiled=False))
#print(ypm.get_pattern("XR", "standby_console", compiled=False))


