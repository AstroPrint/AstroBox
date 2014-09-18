/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

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

/***********************
* Printer - Connection
************************/

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
			$.getJSON(API_BASEURL + 'settings/printer', null, _.bind(function(data) {
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
			url: API_BASEURL + 'settings/printer', 
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
			url: API_BASEURL + 'settings/printer', 
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

/*************************
* Internet - Connection
**************************/

var InternetConnectionView = SettingsPage.extend({
	el: '#internet-connection',
	template: _.template( $("#internet-connection-settings-page-template").html() ),
	networksDlg: null,
	settings: null,
	events: {
		'click .loading-button.start-hotspot button': 'startHotspotClicked',
		'click .loading-button.stop-hotspot button': 'stopHotspotClicked',
		'click .loading-button.list-networks button': 'listNetworksClicked'
	},
	initialize: function(params) {
		SettingsPage.prototype.initialize.apply(this, arguments);

		this.networksDlg = new WiFiNetworksDialog({parent: this});
	},
	show: function() {
		//Call Super
		SettingsPage.prototype.show.apply(this);

		if (!this.settings) {
			$.getJSON(API_BASEURL + 'settings/internet', null, _.bind(function(data) {
				this.settings = data;
				this.render();
			}, this))
			.fail(function() {
				noty({text: "There was an error getting WiFi settings.", timeout: 3000});
			});
		}
	},
	render: function() {
		this.$el.html(this.template({ 
			settings: this.settings
		}));
	},
	startHotspotClicked: function(e) {
		var el = $(e.target).closest('.loading-button');

		el.addClass('loading');

		$.ajax({
			url: API_BASEURL + "settings/internet/hotspot",
			type: "POST",
			success: _.bind(function(data, code, xhr) {
				noty({text: 'Your AstroBox has created a hotspot. Connect to <b>'+this.settings.hotspot.name+'</b>.', type: 'success', timeout:3000});
				this.settings.hotspot.active = true;
				this.render();
			}, this),
			error: function(xhr) {
				noty({text: xhr.responseText, timeout:3000});
			},
			complete: function() {
				el.removeClass('loading');
			}
		});
	},
	stopHotspotClicked: function(e) {
		var el = $(e.target).closest('.loading-button');

		el.addClass('loading');

		$.ajax({
			url: API_BASEURL + "settings/internet/hotspot",
			type: "DELETE",
			success: _.bind(function(data, code, xhr) {
				noty({text: 'The hotspot has been stopped', type: 'success', timeout:3000});
				this.settings.hotspot.active = false;
				this.render();
			}, this),
			error: function(xhr) {
				noty({text: xhr.responseText, timeout:3000});
			},
			complete: function() {
				el.removeClass('loading');
			}
		});
	},
	listNetworksClicked: function(e) {
		var el = $(e.target).closest('.loading-button');

		el.addClass('loading');

		$.getJSON(
			API_BASEURL + "settings/internet/wifi-networks",
			_.bind(function(data) {
				if (data.message) {
					noty({text: data.message});
				} else if (data.networks) {
					var self = this;
					this.networksDlg.open(_.sortBy(_.uniq(_.sortBy(data.networks, function(el){return el.name}), true, function(el){return el.name}), function(el){
						el.active = self.settings.networks.wireless && self.settings.networks.wireless.id == el.id;
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

var WiFiNetworkPasswordDialog = Backbone.View.extend({
	el: '#wifi-network-password-modal',
	events: {
		'click button.connect': 'connectClicked',
		'submit form': 'connectClicked'
	},
	parent: null,
	initialize: function(params) {
		this.parent = params.parent;
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
			url: API_BASEURL + 'settings/internet/active', 
			type: 'POST',
			contentType: 'application/json',
			dataType: 'json',
			data: JSON.stringify({id: id, password: password})
		})
		.done(function(data) {
			if (data.ssid) {
				noty({text: "AstroBox is now connected to "+data.ssid+".", type: "success", timeout: 3000});
				self.$el.foundation('reveal', 'close');
				self.parent.settings.network = {name: data.ssid}
				self.parent.render();
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
	parent: null,
	initialize: function(params) {
		this.parent = params.parent;
	},
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
			this.passwordDlg = new WiFiNetworkPasswordDialog({parent: this.parent});
		}

		if (button.data('secured') == '1') {
			this.passwordDlg.open(button.data('id'), button.data('name'));
		} else {
			this.passwordDlg.connect(button, button.data('id'), null);
		}
	}
});

/********************
* Software - Update
*********************/

var SoftwareUpdateView = SettingsPage.extend({
	el: '#software-update',
	events: {
		'click .loading-button.check button': 'onCheckClicked'
	},
	updateDialog: null,
	onCheckClicked: function(e)
	{
		var loadingBtn = this.$el.find('.loading-button.check');
		loadingBtn.addClass('loading');
		$.ajax({
			url: API_BASEURL + 'settings/software/check', 
			type: 'GET',
			dataType: 'json',
			success: _.bind(function(data) {
				if (!this.updateDialog) {
					this.updateDialog = new SoftwareUpdateDialog();
				}

				this.updateDialog.open(data);
			}, this),
			error: function(xhr) {
				if (xhr.status == 400) {
					noty({text: xhr.responseText, timeout: 3000});
				} else {
					noty({text: "There was a problem checking for new software.", timeout: 3000});
				}
			},
			complete: function() {
				loadingBtn.removeClass('loading');
			}
		});
	}
});

var SoftwareUpdateDialog = Backbone.View.extend({
	el: '#software-update-modal',
	data: null,
	contentTemplate: null,
	open: function(data)
	{
		if (!this.contentTemplate) {
			this.contentTemplate = _.template( $("#software-update-modal-content").html() )
		}

		this.data = data;

		var content = this.$el.find('.content');
		content.empty();
		content.html(this.contentTemplate({data: data, date_format:app.utils.dateFormat}));

		content.find('button.cancel').bind('click', _.bind(this.close, this));
		content.find('button.go').bind('click', _.bind(this.doUpdate, this));

		this.$el.foundation('reveal', 'open');
	},
	close: function()
	{
		this.$el.foundation('reveal', 'close');
	},
	doUpdate: function()
	{
		var loadingBtn = this.$el.find('.loading-button');
		loadingBtn.addClass('loading');
		$.ajax({
			url: API_BASEURL + 'settings/software/update', 
			type: 'POST',
			dataType: 'json',
			contentType: 'application/json',
			data: JSON.stringify({
				release_id: this.data.release.id
			}),
			success: function() {
				//reset the page to show updating progress
				location.href = '/';
			},
			error: function(xhr) {
				if (xhr.status == 400) {
					noty({text: xhr.responseText, timeout: 3000});
				} else {
					noty({text: "There was a problem updating to the new version.", timeout: 3000});
				}
				loadingBtn.removeClass('loading');
			}
		});
	}
});

/************************
* Software - Advanced
*************************/

var SoftwareAdvancedView = SettingsPage.extend({
	el: '#software-advanced',
	ResetConfirmDialog: null,
	initialize: function(params)
	{
		SettingsPage.prototype.initialize.apply(this, arguments);
		this.ResetConfirmDialog = new ResetConfirmDialog();		
	}
});

var ResetConfirmDialog = Backbone.View.extend({
	el: '#restore-confirm-modal',
	events: {
		'click button.secondary': 'doClose',
		'click button.alert': 'doReset',
		'open.fndtn.reveal': 'onOpen'
	},
	onOpen: function()
	{
		this.$el.find('input').val('');
	},
	doClose: function()
	{
		this.$el.foundation('reveal', 'close');
	},
	doReset: function()
	{
		if (this.$el.find('input').val() == 'RESET') {
			this.$el.find('.loading-button').addClass('loading');
			$.ajax({
				url: API_BASEURL + 'settings/software/settings', 
				type: 'DELETE',
				contentType: 'application/json',
				dataType: 'json',
				data: JSON.stringify({}),
				success: function() {
					location.href = "";
				},
				complete: _.bind(function() {
					this.$el.find('.loading-button').removeClass('loading');
				}, this)
			})
		} 
	}
});


/******************************************/

var SettingsMenu = Backbone.View.extend({
	el: '#settings-side-bar',
	subviews: null,
	initialize: function(params) {
		if (params.subviews) {
			this.subviews = params.subviews;
		}
	},
	changeActive: function(page) {
		var target = this.$el.find('li.'+page);
		this.$el.find('li.active').removeClass('active');
		target.closest('li').addClass('active');
		this.subviews[page].show();
	}
});

var SettingsView = Backbone.View.extend({
	el: '#settings-view',
	menu: null,
	events: {
		'show': 'onShow'
	},
	subviews: null,
	initialize: function() {
		this.subviews = {
			'printer-connection': new PrinterConnectionView({parent: this}),
			'internet-connection': new InternetConnectionView({parent: this}),
			'software-update': new SoftwareUpdateView({parent: this}),
			'software-advanced': new SoftwareAdvancedView({parent: this})
		};
		this.menu = new SettingsMenu({subviews: this.subviews});
	},
	onShow: function() {
		this.subviews['printer-connection'].show();
	}
});
