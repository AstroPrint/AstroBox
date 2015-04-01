$.ajaxSetup({
    type: 'POST',
    cache: false,
    headers: { 
    	"X-Api-Key": UI_API_KEY
    }
});

LoginForm = Backbone.View.extend({
	el: '#login-form',
	events: {
		'submit': 'onSubmit'
	},
	onSubmit: function(e)
	{
		e.preventDefault();

		var loadingBtn = this.$('.loading-button');

		loadingBtn.addClass('loading');

		$.ajax({
			url: '/api/login',
			data: this.$el.serializeArray()
		})
		.done(function(){
			location.reload();
		})
		.fail(function(){
			noty({text: "Invalid Password", timeout: 3000});
			loadingBtn.removeClass('loading');
		});

		return false;
	}
});

var form = new LoginForm();