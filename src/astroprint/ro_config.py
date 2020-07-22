# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2018 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import os
import yaml

from octoprint.settings import settings

from astroprint.util import merge_dict

_instance = None

def roConfig(key):
	global _instance

	if _instance is None:

		defaults = {
			'cloud': {
				'apiHost': "https://api.astroprint.com",
				'apiClientId': None,
				'boxrouter': "wss://boxrouter.astroprint.com"
			},
			'network': {
				'ssl': {
					'certPath': '/boot/.astrobox/ssl/cert.pem'
				}
			}
		}

		roFile = os.path.join(settings().getConfigFolder(),'ro-config.yaml')
		with open(roFile,'r') as f:
			config = yaml.safe_load(f)

		merge_dict(defaults, config)
		_instance = defaults

	v = _instance
	for k in key.split('.'):
		v = v[k]

	return v
