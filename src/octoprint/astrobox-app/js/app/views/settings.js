/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var WiFiNetworkPasswordDialog = Backbone.View.extend({
	el: '#wifi-network-password-modal',
	events: {
		'click button.connect': 'connectClicked'
	},
	open: function(id, name) {
		this.$el.find('.network-id-field').val(id);
		this.$el.find('.name').text(name);
		this.$el.foundation('reveal', 'open');
		this.$el.one('opened', _.bind(function() {
			this.$el.find('.network-password-field').focus();
		}, this));
	},
	connectClicked: function(e) {
		e.preventDefault();

		var form = this.$el.find('form');

		this.connect($(e.target), form.find('.network-id-field').val(), form.find('.network-password-field').val());
	},
	connect: function(btn, id, password) {
		var loadingBtn = btn.closest('.loading-button');
		var self = this;
		loadingBtn.addClass('loading');

		$.ajax({
			url: API_BASEURL + 'settings/wifi/active', 
			type: 'POST',
			contentType: 'application/json',
			dataType: 'json',
			data: JSON.stringify({id: id, password: password})
		})
		.done(function(data) {
			if (data.ssid) {
				noty({text: "AstroBox is now connected to "+data.ssid+".", type: "success", timeout: 3000});
				self.$el.foundation('reveal', 'close');
			} else if (data.message) {
				noty({text: data.message});
			}
		})
		.fail(function(){
			noty({text: "There was an error saving setting.", timeout: 3000});
			self.$el.foundation('reveal', 'close');
		})
		.complete(function() {
			loadingBtn.removeClass('loading');
		});
	}
});

var WiFiNetworksDialog = Backbone.View.extend({
	el: '#wifi-network-list-modal',
	networksTemplate: _.template( $("#wifi-network-modal-row").html() ),
	passwordDlg: null,
	open: function(networks) {
		var content = this.$el.find('.modal-content');
		content.empty();

		content.html(this.networksTemplate({ 
			networks: networks
		}));

		content.find('button').bind('click', _.bind(this.networkSelected, this));

		this.$el.foundation('reveal', 'open');
	},
	networkSelected: function(e) {
		e.preventDefault();

		var button = $(e.target);
	
		if (!this.passwordDlg) {
			this.passwordDlg = new WiFiNetworkPasswordDialog();
		}

		if (button.data('secured') == '1') {
			this.passwordDlg.open(button.data('id'), button.data('name'));
		} else {
			this.passwordDlg.connect(button, button.data('id'), null);
		}
	}
});

var SettingsPage = Backbone.View.extend({
	parent: null,
	initialize: function(params) {
		this.parent = params.parent;
	},
	show: function() {
		this.parent.$el.find('.settings-page').addClass('hide');
		this.$el.removeClass('hide');
	}
});

var PrinterConnectionView = SettingsPage.extend({
	el: '#printer-connection',
	settings: null,
	events: {
		'change #settings-baudrate': 'baudrateChanged',
		'change #settings-serial-port': 'portChanged'
	},
	show: function() {
		//Call Super
		SettingsPage.prototype.show.apply(this);

		if (!this.settings) {
			$.getJSON(API_BASEURL + 'settings', null, _.bind(function(data) {
				this.settings = data;
				if (data.serial) {
					if (data.serial.baudrateOptions) {
						var baudList = this.$el.find('#settings-baudrate');
						_.each(data.serial.baudrateOptions, function(element){
							baudList.append('<option val="'+element+'">'+element+'</option>');
						});
						baudList.val(data.serial.baudrate);
					}

					if (data.serial.portOptions) {
						var portList = this.$el.find('#settings-serial-port');
						_.each(data.serial.portOptions, function(element){
							var option = $('<option val="'+element+'">'+element+'</option>');
							if (data.serial.port == element) {
								option.attr('selected', 1);
							}
							portList.append(option);
						});
					}
				} 
			}, this))
			.fail(function() {
				noty({text: "There was an error getting serial settings.", timeout: 3000});
			});
		}
	},
	baudrateChanged: function(e) {
		$.ajax({
			url: API_BASEURL + 'settings', 
			type: 'POST',
			contentType: 'application/json',
			dataType: 'json',
			data: JSON.stringify({serial: { baudrate: $(e.target).val() }})
		})
		.fail(function(){
			noty({text: "There was an error saving setting.", timeout: 3000});
		});
	},
	portChanged: function(e) {
		$.ajax({
			url: API_BASEURL + 'settings', 
			type: 'POST',
			contentType: 'application/json',
			dataType: 'json',
			data: JSON.stringify({serial: { port: $(e.target).val() }})
		})
		.fail(function(){
			noty({text: "There was an error saving setting.", timeout: 3000});
		});
	}
});

var InternetWifiView = SettingsPage.extend({
	el: '#internet-wifi',
	networksDlg: null,
	settings: null,
	events: {
		'click .loading-button.start-hotspot button': 'startHotspotClicked',
		'click .loading-button.stop-hotspot button': 'stopHotspotClicked',
		'click .loading-button.connect button': 'connectClicked'
	},
	initialize: function(params) {
		SettingsPage.prototype.initialize.apply(this, arguments);

		this.networksDlg = new WiFiNetworksDialog();
	},
	show: function() {
		//Call Super
		SettingsPage.prototype.show.apply(this);

		if (!this.settings) {
			$.getJSON(API_BASEURL + 'settings/wifi', null, _.bind(function(data) {
				this.settings = data;
				this.render();
			}, this))
			.fail(function() {
				noty({text: "There was an error getting WiFi settings.", timeout: 3000});
			});
		}
	},
	render: function() {
		if (this.settings.network) {
			this.$el.find('.network-name').text(this.settings.network.name);
		}

		if (this.settings.isHotspotActive) {
			this.$el.find('.loading-button.start-hotspot').hide();
			this.$el.find('.loading-button.stop-hotspot').show();
		} else {
			this.$el.find('.loading-button.start-hotspot').show();
			this.$el.find('.loading-button.stop-hotspot').hide();
		}
	},
	startHotspotClicked: function(e) {
		var el = $(e.target).closest('.loading-button');

		el.addClass('loading');

		var data = {
			"action": "start-hotspot"
		}

		$.ajax({
			url: API_BASEURL + "system",
			type: "POST",
			data: data,
			success: function(data, code, xhr) {
				if (xhr.status == 204) {
					noty({text: 'hotspot is not configured on this box', timeout:3000});
				} else {
					alert('The system is now creating a hotspot. Search and connect to it');
					window.close();
				}
			},
			error: function() {
				noty({text: 'failed to open hotspot', timeout:3000});
			},
			complete: function() {
				el.removeClass('loading');
			}
		});
	},
	stopHotspotClicked: function(e) {
		var el = $(e.target).closest('.loading-button');

		el.addClass('loading');

		var data = {
			"action": "stop-hotspot"
		}

		$.ajax({
			url: API_BASEURL + "system",
			type: "POST",
			data: data,
			success: function(data, code, xhr) {
				if (xhr.status == 204) {
					noty({text: 'hotspot is not configured on this box', timeout:3000});
				} else {
					noty({text: 'The hotspot has been stopped', type: 'success', timeout:3000});
				} 
			},
			error: function() {
				noty({text: 'failed to stop hotspot', timeout:3000});
			},
			complete: function() {
				el.removeClass('loading');
			}
		});
	},
	connectClicked: function(e) {
		var el = $(e.target).closest('.loading-button');

		el.addClass('loading');

		$.getJSON(
			API_BASEURL + "settings/wifi/networks",
			_.bind(function(data) {
				if (data.message) {
					noty({text: data.message});
				} else if (data.networks) {
					var self = this;
					this.networksDlg.open(_.sortBy(_.uniq(_.sortBy(data.networks, function(el){return el.name}), true, function(el){return el.name}), function(el){
						el.active = self.settings && self.settings.network.id == el.id;
						return -el.signal
					}));
				}
			}, this)
		).
		fail(function(){
			noty({text: "There was an error retrieving networks.", timeout:3000});
		}).
		complete(function(){
			el.removeClass('loading');
		});
	}
});

var SettingsMenu = Backbone.View.extend({
	el: '#settings-side-bar',
	subviews: null,
	events: {
		'click a.printer-connection': 'showPrinterConnection',
		'click a.internet-wifi': 'showInternetWifi'
	},
	initialize: function(params) {
		if (params.subviews) {
			this.subviews = params.subviews;
		}
	},
	_changeActive: function(e) {
		e.preventDefault();
		this.$el.find('li.active').removeClass('active');
		$(e.target).closest('li').addClass('active');
	},
	showPrinterConnection: function(e) {
		this._changeActive(e);
		this.subviews.printerConnection.show();
	},
	showInternetWifi: function(e) {
		this._changeActive(e);
		this.subviews.internetWifi.show();
	}
});

var SettingsView = Backbone.View.extend({
	el: '#settings-view',
	menu: null,
	events: {
		'show': 'onShow'
	},
	subviews: {
		printerConnection: null,
		internetWifi: null
	},
	initialize: function() {
		this.subviews.printerConnection = new PrinterConnectionView({parent: this});
		this.subviews.internetWifi = new InternetWifiView({parent: this});
		this.menu = new SettingsMenu({subviews: this.subviews});
	},
	onShow: function() {
		this.subviews.printerConnection.show();
	}
});
