/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var StepView = Backbone.View.extend({
	setup_view: null,
	events: {
		"click .next-step": "doNext"
	},
	initialize: function(params) 
	{
		this.setup_view = params.setup_view;
	},
	doNext: function(e)
	{
		e.preventDefault();
		this.setup_view.nextStep();
	}
});

var StepWelcome = StepView.extend({
	el: "#step-welcome"
});

var StepShare = StepView.extend({
	el: "#step-share",
	constructor: function() {
	    this.events["click .share-button.facebook"] = "onFacebookClicked";
	    this.events["click .share-button.twitter"] = "onTwitterClicked";
	    StepView.apply(this, arguments);
  	},
	onFacebookClicked: function(e)
	{
		e.preventDefault();
		window.open('https://www.facebook.com/sharer/sharer.php?u=http%3A%2F%2Fwww.astroprint.com','facebook','width=740,height=280,left=300,top=300');
		this.$el.find('button.next-step').removeClass('hide');
		this.$el.find('a.next-step').addClass('hide');
	},
	onTwitterClicked: function(e)
	{
		e.preventDefault();
		window.open('https://twitter.com/share?url=http%3A%2F%2Fwww.astroprint.com&text=I+just+setup+my+AstroBox+and+%40AstroPrint3D+for+easy+%233DPrinting.+Get+yours+at','twitter','width=740,height=280,left=300,top=300');
		this.$el.find('button.next-step').removeClass('hide');
		this.$el.find('a.next-step').addClass('hide');
	}
});

var SetupView = Backbone.View.extend({
	steps: null,
	current_step: 0,
	initialize: function()
	{
		this.steps = [
			new StepWelcome({'setup_view': this}),
			new StepShare({'setup_view': this})
		];

		this.setStep(this.current_step);
	},
	setStep: function(step)
	{
		if (step >= 0 && step < this.steps.length) {
			this.steps[this.current_step].$el.addClass('hide');
			this.steps[step].$el.removeClass('hide');
		}
	},
	nextStep: function()
	{
		if (this.steps.length > (this.current_step + 1)) {
			this.setStep(this.current_step + 1);
			this.current_step++;
		} else {
			//last step refresh the screen;
			location.reload();
		}
	},
	previousStep: function()
	{
		if (this.current_step > 0) {
			this.setStep(this.current_step - 1);
			this.current_step--;
		}
	}
});

var setup_view = new SetupView();