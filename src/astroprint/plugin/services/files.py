# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

from . import PluginService

class FilesService(PluginService):
	_validEvents = ['file_added', 'file_deleted']

	def __init__(self):
		super(FilesService, self).__init__()
