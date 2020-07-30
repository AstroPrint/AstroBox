# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2020 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import os
import yaml

from octoprint.settings import settings

from astroprint.util import merge_dict

_instance = None

def dataStore():
	global _instance

	if _instance is None:
		_instance = DataStore()

	return _instance

class DataStore(object):
	def __init__(self):
		self._data = {
			'printer_state': {
				'bed_clear': True
			}
		}

		self._storeFile =	os.path.join(settings().getConfigFolder(),'data-store.yaml')
		if os.path.isfile(self._storeFile):
			with open(self._storeFile,'r') as f:
				config = yaml.safe_load(f)

			merge_dict(self._data, config)

	def get(self, key):
		v = self._data

		for k in key.split('.'):
			v = v[k]

		return v

	def set(self, key, value):
		path = key.split('.')
		d = self._data

		if len(path) > 1:
			for k in path[:-1]:
				if k not in d:
					d[k] = {}
				d = d[k]

			k = path[-1]
		else:
			k = path[0]

		d[k] = value
		self.save()

	def save(self):
		with open(self._storeFile,'w') as f:
			yaml.safe_dump(self._data, f, default_flow_style=False, indent="  ", allow_unicode=True)
