/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

 // work around a stupid iOS6 bug where ajax requests get cached and only work once, as described at
// http://stackoverflow.com/questions/12506897/is-safari-on-ios-6-caching-ajax-results
$.ajaxSetup({
    type: 'POST',
    headers: { "cache-control": "no-cache" }
});

// send the current UI API key with any request
$.ajaxSetup({
    headers: {"X-Api-Key": UI_API_KEY}
});

/******************/

var StepView = Backbone.View.extend({
	setup_view: null,
	events: {
		"submit form": "_onSubmit",
		"click .submit-action": "_onSubmitClicked"
	},
	initialize: function(params) 
	{
		this.setup_view = params.setup_view;
	},
	onHide: function() {},
	onShow: function() {},
	onSubmit: function(data) {},
	_onSubmit: function(e)
	{
		e.preventDefault();
		var serializedData = $(e.currentTarget).serializeArray();
		var data = {};
		_.each(serializedData, function(item) {
			data[item.name] = item.value;
		});

		this.onSubmit(data);
	},
	_onSubmitClicked: function()
	{
		this.$el.find('form').submit();
		return false;
	},
});

/**************
* Welcome
***************/

var StepWelcome = StepView.extend({
	el: "#step-welcome"
});

/**************
* Name
***************/

var StepName = StepView.extend({
	el: "#step-name",
	default: 'astrobox',
	constructor: function()
	{
		this.events["keyup input"] = "onNameChanged";
		StepView.apply(this, arguments);
	},
	initialize: function()
	{
		this.$el.find('input#astrobox-name').val(this.default);
		this.$el.find('.hotspot-name').text(this.default);
		this.$el.find('.astrobox-url').text(this.default);		
	},
	onShow: function()
	{
		this.$el.find('input').focus();
	},
	onNameChanged: function(e) 
	{
		var name = $(e.target).val();

		if (/^[A-Za-z0-9\-_]+$/.test(name)) {
			this.$el.find('.hotspot-name').text(name);
			this.$el.find('.astrobox-url').text(name);
		} else if (name) {
			$(e.target).val( $(e.target).val().slice(0, -1) );
		} else {
			this.$el.find('.hotspot-name').text('');
			this.$el.find('.astrobox-url').text('');
		}
	},
	onSubmit: function(data)
	{
		if (data.name != this.default) {
			this.$el.find('.loading-button').addClass('loading');
			$.ajax({
				url: API_BASEURL + 'setup/name',
				method: 'post',
				data: data,
				success: _.bind(function() {
					location.href = this.$el.find('.submit-action').attr('href');
				}, this),
				error: function(xhr) {
					if (xhr.status == 400) {
						message = xhr.responseText;
					} else {
						message = "There was an error saving your name";
					}
					noty({text: message, timeout: 3000});
				},
				complete: _.bind(function() {
					this.$el.find('.loading-button').removeClass('loading');
				}, this)
			});
		} else {
			location.href = this.$el.find('.submit-action').attr('href');
		}
	}
});

/**************
* Internet
***************/

var StepInternet = StepView.extend({
	el: "#step-internet",
	onShow: function()
	{
		this.$el.removeClass('success settings');
		this.$el.addClass('checking');
		$.ajax({
			url: API_BASEURL + 'setup/internet',
			method: 'GET',
			success: _.bind(function() {
				this.$el.addClass('success');
			}, this),
			error: _.bind(function() {
				this.$el.addClass('settings');
			}, this),
			complete: _.bind(function() {
				this.$el.removeClass('checking');
			}, this)
		})
	}
});

/**************
* Astroprint
***************/

var StepAstroprint = StepView.extend({
	el: "#step-astroprint",
	initialize: function()
	{
		this.events["click a.logout"] = "onLogoutClicked";
	},
	onShow: function()
	{
		this.$el.removeClass('success settings');
		this.$el.addClass('checking');
		$.ajax({
			url: API_BASEURL + 'setup/astroprint',
			method: 'GET',
			success: _.bind(function(data) {
				if (data.user) {
					this.$el.addClass('success');
					this.$el.find('span.email').text(data.user);
				} else {
					this.$el.addClass('settings');
					this.$el.find('#email').focus();
				}
			}, this),
			error: _.bind(function() {
				this.$el.addClass('settings');
				this.$el.find('#email').focus();
			}, this),
			complete: _.bind(function() {
				this.$el.removeClass('checking');
			}, this)
		});
	},
	onSubmit: function(data) {
		this.$el.find('.loading-button').addClass('loading');
		$.ajax({
			url: API_BASEURL + 'setup/astroprint',
			method: 'post',
			data: data,
			success: _.bind(function() {
				location.href = this.$el.find('.submit-action').attr('href');
			}, this),
			error: _.bind(function(xhr) {
				if (xhr.status == 400 || xhr.status == 401) {
					message = xhr.responseText;
				} else {
					message = "There was an error logging you in";
				}
				noty({text: message, timeout: 3000});
				this.$el.find('#email').focus();
			}, this),
			complete: _.bind(function() {
				this.$el.find('.loading-button').removeClass('loading');
			}, this)
		});
	},
	onLogoutClicked: function(e)
	{
		e.preventDefault();
		$.ajax({
			url: API_BASEURL + 'setup/astroprint',
			method: 'delete',
			success: _.bind(function() {
				this.$el.removeClass('success');
				this.$el.addClass('settings');
			}, this),
			error: _.bind(function(xhr) {
				noty({text: "Error logging you out", timeout: 3000});
			}, this)
		});		
	}
});

/**************
* Printer
***************/

var StepPrinter = StepView.extend({
	el: "#step-printer",
	onShow: function()
	{
		this.$el.removeClass('success settings');
		this.$el.addClass('checking');
		$.ajax({
			url: API_BASEURL + 'setup/printer',
			method: 'GET',
			success: _.bind(function(data) {
				this.$el.addClass('settings');
				if (data.portOptions && data.baudrateOptions) {
					var portSelect = this.$el.find('select#port');
					portSelect.empty();
					_.each(data.portOptions, function(p) {
						portSelect.append('<option value="'+p+'">'+p+'</option>');
					});
					portSelect.val(data.port);

					var baudSelect = this.$el.find('select#baud-rate');
					baudSelect.empty();
					_.each(data.baudrateOptions, function(b) {
						baudSelect.append('<option value="'+b+'">'+b+'</option>');
					});
					baudSelect.val(data.baudrate);
				} else {
					noty({text: "Error reading printer connection settings", timeout: 3000});
				}
			}, this),
			error: _.bind(function(xhr) {
				this.$el.addClass('settings');
				if (xhr.status == 400) {
					message = xhr.responseText;
				} else {
					message = "Error reading printer connection settings";
				}
				noty({text: message, timeout: 3000});

			}, this),
			complete: _.bind(function() {
				this.$el.removeClass('checking');
			}, this)
		});
	},
	onSubmit: function(data) {
		this._setConnecting(true);
		$.ajax({
			url: API_BASEURL + 'setup/printer',
			method: 'post',
			data: data,
			success: _.bind(function() {
				//We monitor the connection here for status updates
		        var socket = new SockJS(SOCKJS_URI);
		        socket.onmessage = _.bind(function(e){ 
		        	if (e.type == "message" && e.data.current) {
		        		var flags = e.data.current.state.flags;
		        		if (flags.operational) {
		        			socket.close();
		        			this._setConnecting(false);
		        			location.href = this.$el.find('.submit-action').attr('href');
		        		} else if (flags.error) {
							noty({text: 'There was an error connecting to the printer.', timeout: 3000});
							socket.close();
							this._setConnecting(false);
		        		}
		        	}
		        }, this);
			}, this),
			error: _.bind(function(xhr) {
				if (xhr.status == 400 || xhr.status == 401) {
					message = xhr.responseText;
				} else {
					message = "There was an error connecting to your printer";
				}
				noty({text: message, timeout: 3000});
				this._setConnecting(false);
			}, this)
		});
	},
	_setConnecting: function(connecting)
	{
		if (connecting) {
			this.$el.find('.loading-button').addClass('loading');
			this.$el.find('.skip-step').hide();
		} else {
			this.$el.find('.loading-button').removeClass('loading');
			this.$el.find('.skip-step').show();			
		}
	}
});

/**************
* Share
***************/

var StepShare = StepView.extend({
	el: "#step-share",
	constructor: function() 
	{
	    this.events["click .share-button.facebook"] = "onFacebookClicked";
	    this.events["click .share-button.twitter"] = "onTwitterClicked";
	    this.events["click .setup-done"] = "onSetupDone";
	    StepView.apply(this, arguments);
  	},
	onFacebookClicked: function(e)
	{
		e.preventDefault();
		window.open('https://www.facebook.com/sharer/sharer.php?u=http%3A%2F%2Fwww.astroprint.com','facebook','width=740,height=280,left=300,top=300');
		this.$el.find('a.button.setup-done').show();
		this.$el.find('a.setup-done').addClass('hide');
	},
	onTwitterClicked: function(e)
	{
		e.preventDefault();
		window.open('https://twitter.com/share?url=http%3A%2F%2Fwww.astroprint.com&text=I+just+setup+my+AstroBox+and+%40AstroPrint3D+for+easy+%233DPrinting.+Get+yours+at','twitter','width=740,height=280,left=300,top=300');
		this.$el.find('a.button.setup-done').show();
		this.$el.find('a.setup-done').addClass('hide');
	},
	onSetupDone: function(e)
	{
		e.preventDefault();
		$.ajax({
			url: API_BASEURL + 'setup/done',
			method: 'post',
			success: function() {
				location.href = "/";
			},
			error: function() {
				noty({text: "There was an error saving your settings.", timeout: 3000});
			}
		});
	}
});

var SetupView = Backbone.View.extend({
	steps: null,
	current_step: 'welcome',
	router: null,
	initialize: function()
	{
		this.steps = {
			'welcome': new StepWelcome({'setup_view': this}),
			'name': new StepName({'setup_view': this}),
			'internet': new StepInternet({'setup_view': this}),
			'astroprint': new StepAstroprint({'setup_view': this}),
			'printer': new StepPrinter({'setup_view': this}),
			'share': new StepShare({'setup_view': this})
		};

		this.router = new SetupRouter({'setup_view': this});
	},
	setStep: function(step)
	{
		if (this.steps[step] != undefined) {
			this.steps[this.current_step].$el.addClass('hide');
			this.steps[this.current_step].onHide();
			this.steps[step].$el.removeClass('hide');
			this.steps[step].onShow();
			this.current_step = step;
		}
	}
});

var SetupRouter = Backbone.Router.extend({
	setup_view: null,
	routes: {
		"": "setStep",
		":step": "setStep"
	},
	initialize: function(params)
	{
		this.setup_view = params.setup_view;
	},
	setStep: function(step) 
	{
		this.setup_view.setStep(step || 'welcome');
	}
});

var setup_view = new SetupView();

Backbone.history.start();