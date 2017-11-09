# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

from . import PluginService
from octoprint.settings import settings

class SystemService(PluginService):
	_validEvents = ['started', 'shutting_down']

	def __init__(self):
		super(SystemService, self).__init__()

	#REQUESTS

	#write a key in config.yaml file
	def setSetting(self, data, sendResponse):
		if 'key' in data and 'value' in data:
			settings().set(data['key'], data['value'])
			settings().save()
			sendResponse({'success':'no error'})
		else:
			sendResponse('error_writing_setting',True)

	#read a key in config.yaml file
	def getSetting(self, data, sendResponse):
		if 'key' in data:
			sendResponse(settings().get(data['key']))
		else:
			sendResponse('key_setting_error',True)
