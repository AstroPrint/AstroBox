/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var SettingsView = Backbone.View.extend({
	el: '#settings-view',
	events: {
		'click button.upgrade': 'upgradeClicked',
		'click .loading-button.hotspot button': 'hotspotClicked',
		'click .loading-button.connect button': 'connectClicked'
	},
	upgradeClicked: function() {
		alert('upgrading');
	},
	hotspotClicked: function(e) {
		var el = $(e.target).closest('.loading-button');

		el.addClass('loading');

		var data = {
            "action": "hotspot"
        }

        $.ajax({
            url: API_BASEURL + "system",
            type: "POST",
            data: data,
            success: function(data, code, xhr) {
            	if (xhr.status == 204) {
            		alert('hotspot is not configured on this box');
            	} else {
            		alert('The system is now creating a hotspot. Search and connect to it');
            		window.close();
            	}
            },
            error: function() {
				console.error('failed to open hotspot');
            },
            complete: function() {
            	el.removeClass('loading');
            }
        });
	},
	connectClicked: function(e) {
		var el = $(e.target).closest('.loading-button');

		el.addClass('loading');

		var data = {
            "action": "connect-internet"
        }

        $.ajax({
            url: API_BASEURL + "system",
            type: "POST",
            data: data,
            success: function(data, code, xhr) {
            	if (xhr.status == 204) {
            		alert('connect-internet is not configured on this box');
            	} else {
            		alert('The system has closed the hotspot. Connect to the same network as AstroBox.');
            		window.close();
            	}
            },
            error: function() {
				console.error('failed to connect to the internet');
            },
            complete: function() {
            	el.removeClass('loading');
            }
        });
	}
});