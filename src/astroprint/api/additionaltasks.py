# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

from flask import jsonify

from octoprint.server.api import api
from octoprint.server import restricted_access

from astroprint.additionaltasks import additionalTasksManager

@api.route('/additional-tasks', methods=['GET'])
@restricted_access
def additionalTasks():
	atm = additionalTasksManager()

	result = atm.data.copy()
	return jsonify( result )
