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
	el: "#step-share"
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