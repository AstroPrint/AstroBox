# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import time

from gi.repository import Gst

#
# Util functions
#

def waitToReachState(element, state, timeout= 3.0, attempts= 1):
	while attempts:
		stateReturn, currentState, pending = element.get_state( (timeout * Gst.SECOND) if timeout != Gst.CLOCK_TIME_NONE else Gst.CLOCK_TIME_NONE)
		if currentState == state and ( stateReturn == Gst.StateChangeReturn.SUCCESS or stateReturn == Gst.StateChangeReturn.NO_PREROLL ):
			return True

		attempts -= 1
		if attempts:
			time.sleep(0.1)

	return False
