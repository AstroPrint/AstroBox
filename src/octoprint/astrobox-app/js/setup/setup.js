/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var StepView = Backbone.View.extend({
	setup_view: null,
	events: {},
	initialize: function(params) 
	{
		this.setup_view = params.setup_view;
	},
	onHide: function() {},
	onShow: function() {}
});

var StepWelcome = StepView.extend({
	el: "#step-welcome"
});

var StepName = StepView.extend({
	el: "#step-name",
	constructor: function()
	{
		this.events["keyup input"] = "onNameChanged";
		StepView.apply(this, arguments);
	},
	onShow: function()
	{
		this.$el.find('input').focus();
	},
	onNameChanged: function(e) 
	{
		this.$el.find('.hotspot-name').text($(e.target).val());
		this.$el.find('.astrobox-url').text($(e.target).val());
	}
});

var StepInternet = StepView.extend({
	el: "#step-internet"
});

var StepAstroprint = StepView.extend({
	el: "#step-astroprint",
	onShow: function()
	{
		this.$el.find('#email').focus();
	},
});

var StepPrinter = StepView.extend({
	el: "#step-printer"
});

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
		location.href = "/";
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

		this.setStep(this.current_step);
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