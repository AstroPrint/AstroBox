"""
A machine profile object that holds all values for a specific profile.
"""

import json
import os
import re
import logging


def _getprofiledir(profiledir):
    if None is profiledir:
        profiledir = os.path.join(
            os.path.abspath(os.path.dirname(__file__)), 'profiles')  # Path of the profiles directory
    return profiledir


class Profile(object):
    def __init__(self, name, profiledir=None):
        """Constructor for the profile object.
        @param string name: Name of the profile, NOT the path.
        """
        self._log = logging.getLogger(self.__class__.__name__)
        self.path = _getprofiledir(profiledir)
        self.name = os.path.splitext(name)[0] # name without any extension
        extension = '.json'
        if not name.endswith(extension):
            name += extension
        path = os.path.join(self.path, name)
        self._log.debug('{"event":"open_profile", "path":%s}', path)
        if  os.path.isfile(path):
            with open(path) as fh:
                try:
                    self.values = json.load(fh)
                except Exception, e:
                    self._log.debug('profile load fail for %s on err %s',
                                    os.path.abspath(path), str(e))
                    raise e
        else:
            self._log.debug("no such profile file %s for %s", path, name)
            raise IOError("no such profile file %s for %s", path, name)


def list_profiles(profiledir=None):
    """
    Looks in the ./profiles directory for all files that
    end in .json and returns that list.
    @return A generator of profiles without their .json extensions
    """
    path = _getprofiledir(profiledir)
    profile_extension = '.json'
    for f in os.listdir(path):
        root, ext = os.path.splitext(f)
        if profile_extension == ext :
            yield root


def search_profiles_with_regex(regex, profiledir=None):
    """
    Looks in profiledir for any profiles matching the regex
    """
    if profiledir:
        profiledir = profiledir
    else:
        profiledir = os.path.join(
            os.path.abspath(os.path.dirname(__file__)),
            'profiles',
        )
    path = _getprofiledir(profiledir)
    profile_extension = '.json'
    possible_files = os.listdir(path)
    matches = []
    if regex is not None:
        for f in possible_files:
            match = re.search(regex, f)
            root, ext = os.path.splitext(f)
            if match and ext == profile_extension:
                matches.append(match.group())
    return matches
