# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import os.path
import yaml

from octoprint.settings import settings

class SoftwareManager(object):
	def __init__(self):
		self.data = {
			"version": {
				"major": 0,
				"minor": 0,
				"build": 0,
				"date": None
			},
			"variant": {
				"id": None,
				"name": None
			}
		}

		s = settings()
		infoFile = s.get(['software', 'infoFile']) or "%s/software.yaml" % os.path.dirname(s._configfile)
		if not os.path.isfile(infoFile):
			infoFile = None

		if infoFile:
			config = None
			with open(infoFile, "r") as f:
				config = yaml.safe_load(f)

			def merge_dict(a,b):
				for key in b:
					if isinstance(b[key], dict):
						merge_dict(a[key], b[key])
					else:
						a[key] = b[key]

			if config:
				merge_dict(self.data, config)

	def version(self):
		return '%d.%d (%s) %s' % (
			self.data['version']['major'], 
			self.data['version']['minor'], 
			self.data['version']['build'], 
			self.data['variant']['name'] or 'AstroBox')
