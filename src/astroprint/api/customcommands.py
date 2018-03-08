# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

from flask import jsonify

from octoprint.server.api import api
from octoprint.server import restricted_access

from astroprint.customcommands import customCommandsManager

@api.route('/custom-commands', methods=['GET'])
@restricted_access
def customCommands():
	ccm = customCommandsManager()

	result = ccm.data.copy()
	return jsonify( result )
