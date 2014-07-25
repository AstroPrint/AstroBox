/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var LoginModal = Backbone.View.extend({
	el: '#login-modal',
	button: null,
	events: {
		'valid form': 'onFormValidated',
        'opened.fndtn.reveal': 'onModalOpened'
	},
	initialize: function()
    {
		this.button = this.$el.find('.loading-button');
	},
	onFormValidated: function(e) 
    {
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
	},
    onModalOpened: function()
    {
        this.$el.find("input[name='email']").focus();
    }
});

var loginModal = new LoginModal();