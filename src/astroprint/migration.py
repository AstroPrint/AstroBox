# coding=utf-8
__author__ = "Daniel Arroyo. 3DaGogo, Inc <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging

def migrateSettings():
	from octoprint.settings import settings

	logger = logging.getLogger(__name__)
	logger.info('Checking for settings migrations...')
	migrationsDone = 0;

	s = settings()

	#Migration to add the reboot action
	actions = s.get(['system', 'actions'])

	if 'reboot' not in [a["action"] for a in actions]:
		actions.append({
			'action': 'reboot',
			'command': 'reboot'
		})
		s.set(['system', 'actions'], actions, True)
		migrationsDone += 1

	if migrationsDone > 0:
		s.save()

	logger.info('Performed %d settings migrations.' % migrationsDone)
