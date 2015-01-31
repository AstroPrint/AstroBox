/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var ConnectionView = Backbone.View.extend({
	el: '#connection-view',
	events: {
		'click i.printer': 'printerTapped',
		'click i.server': 'serverTapped',
		'click i.astroprint': 'astroprintTapped'
	},
	socketData: null,
	connect: function(clicked) {
		var self = this;

        $.ajax({
            url: API_BASEURL + "connection",
            method: "GET",
            dataType: "json",
            success: function(response) {
		        if (response.current.state.substr(0,5) == 'Error' || response.current.state == 'Closed') {
		        	if (clicked && response.current.port == null) {
        				app.router.navigate('settings/printer-connection', {trigger: true, replace: true});
        				noty({text: 'Enter Connection settings.', type:"information", timeout: 3000});
		        		return;
		        	}

		        	if (response.current.state.substr(0,5) == 'Error') {
		        		console.error("Printer connection had error: "+response.current.state);
		        	}

			        var data = {
			            "command": "connect",
			            "port": response.options.portPreference,
			            "baudrate": response.options.baudratePreference,
			            "autoconnect": true
			        };

			        $.ajax({
			            url: API_BASEURL + "connection",
			            type: "POST",
			            dataType: "json",
			            contentType: "application/json; charset=UTF-8",
			            data: JSON.stringify(data),
			            error: function() {
			            	self.setPrinterConnection('failed');
			       		    if (clicked) {
	            				noty({text: 'No Printer connected.', type:"alert", timeout: 3000});
	            			}
			            }
			        });
			    } else if (response.current.state != 'Connecting') {
			    	if (response.current.state == 'Printing' || response.current.state == 'Paused') {
		        		app.showPrinting();
		        	}

		        	self.setPrinterConnection('connected');
		        } else {
					self.setPrinterConnection('blink-animation');
		        }
            }
        });
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
		var element = this.$el.find('i.server');
		var titleText = '';

		element.removeClass('blink-animation connected failed').addClass(className);

		switch(className) {
			case 'blink-animation':
				titleText = 'Connecting to '+ASTROBOX_NAME+'...';
				break;

			case 'connected':
				titleText = 'Connected to '+ASTROBOX_NAME;
				break;

			case 'failed':
				titleText = ASTROBOX_NAME+' is unreachable';
				break;
		}

		element.attr('title', titleText);
	},
	setPrinterConnection: function(className) {
		var element = this.$el.find('i.printer');
		var titleText = '';

		element.removeClass('blink-animation connected failed').addClass(className);

		switch(className) {
			case 'blink-animation':
				titleText = 'Connecting to printer...';
				break;

			case 'connected':
				titleText = 'Connected to printer';
				break;

			case 'failed':
				titleText = 'The Printer is not connected';
				break;
		}

		element.attr('title', titleText);
	},
	setAstroprintConnection: function(className) {
		var element = this.$el.find('i.astroprint')
		var titleText = '';

		element.removeClass('blink-animation connected failed').addClass(className);

		switch(className) {
			case 'blink-animation':
				titleText = 'Connecting to the astroprint.com...';
				break;

			case 'connected':
				titleText = 'Connected to astroprint.com';
				break;

			case 'failed':
				titleText = 'Not connected to astroprint.com';
				break;
		}

		element.attr('title', titleText);
	},
	printerTapped: function(e) {
		if ($(e.target).hasClass('failed')) {
			this.connect(true);
		}
	},
	serverTapped: function(e) {
		if ($(e.target).hasClass('failed')) {
			this.socketData.reconnect();
			this.connect();
		}
	},
	astroprintTapped: function(e) {
		var icon = $(e.target);
		if (icon.hasClass('failed')) {
			if (LOGGED_IN) {
				icon.addClass('blink-animation');
		        $.ajax({
		            url: API_BASEURL + "boxrouter",
		            method: "POST",
		            dataType: "json",
		            complete: function(response) {
		            	icon.removeClass('blink-animation');
		            }
		        });
		    } else {
		    	$('#login-modal').foundation('reveal', 'open');
		    }
		}
	}
});