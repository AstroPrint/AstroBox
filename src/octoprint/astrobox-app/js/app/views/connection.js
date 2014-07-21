/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var ConnectionView = Backbone.View.extend({
	el: '#connection-view',
	events: {
		'click i.printer': 'printerTapped',
		'click i.server': 'serverTapped'
	},
	socketData: null,
	connect: function() {
		var self = this;

		this.setPrinterConnection('blink-animation');

        $.ajax({
            url: API_BASEURL + "connection",
            method: "GET",
            dataType: "json",
            success: function(response) {
		        var data = {
		            "command": "connect",
		            "port": response.options.portPreference,
		            "baudrate": response.options.baudratePreference,
		            "autoconnect": true
		        };

		        if (response.current.state.substr(0,5) == 'Error' || response.current.state == 'Closed') {
			        $.ajax({
			            url: API_BASEURL + "connection",
			            type: "POST",
			            dataType: "json",
			            contentType: "application/json; charset=UTF-8",
			            data: JSON.stringify(data),
			            error: function() {
			            	self.setPrinterConnection('failed');
			            }
			        });
			    } else if (response.current.state != 'Connecting') {
			    	if (response.current.state == 'Printing' || response.current.state == 'Paused') {
		        		app.showPrinting();
		        	}
		        }
            }
        })
	},
	disconnect: function() {
	    $.ajax({
	        url: API_BASEURL + "connection",
	        type: "POST",
	        dataType: "json",
	        contentType: "application/json; charset=UTF-8",
	        data: JSON.stringify({"command": "disconnect"}),
	        success: function(response) {
	        	self.$el.removeClass('connected');
	        }
	    });	
	},
	setServerConnection: function(className) {
		this.$el.find('i.server').removeClass('blink-animation connected failed').addClass(className);
	},
	setPrinterConnection: function(className) {
		this.$el.find('i.printer').removeClass('blink-animation connected failed').addClass(className);
	},
	printerTapped: function(e) {
		if ($(e.target).hasClass('failed')) {
			this.connect();
		}
	},
	serverTapped: function(e) {
		if ($(e.target).hasClass('failed')) {
			this.socketData.reconnect();
			this.connect();
		}
	}
});