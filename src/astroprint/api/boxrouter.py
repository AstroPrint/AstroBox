# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

from flask import jsonify

from octoprint.server.api import api
from astroprint.boxrouter import boxrouterManager

@api.route("/boxrouter", methods=["POST"])
def connect_boxrouter():
	br = boxrouterManager()

	br.boxrouter_connect()

	return jsonify()