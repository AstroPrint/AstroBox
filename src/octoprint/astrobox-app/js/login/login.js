/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var LoginView = Backbone.View.extend({
	el: '#login-view',
	button: null,
	events: {
		'valid form': 'onFormValidated'
	},
	initialize: function(){
		this.$el.find("input[name='email']").focus();
		this.button = this.$el.find('.loading-button');
	},
	onFormValidated: function(e) {
		var errorContainer = this.$el.find('.alert-box');
		errorContainer.hide();
		this.button.addClass('loading');

		var self = this;

        $.ajax({
            url: API_BASEURL + "cloud-slicer/private-key",
            type: "POST",
            data: {
            	email: this.$el.find('input[name=email]').val(),
            	password: this.$el.find('input[name=password]').val()
            },
            success: function() { 
            	location.reload();
            },
            error: function() { 
				errorContainer.text('Invalid Email/Password').show();
                self.button.removeClass('loading');
            }
        });
	}
});

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

var login = new LoginView();