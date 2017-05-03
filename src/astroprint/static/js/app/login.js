/*
 *  (c) 3DaGoGo, Inc. (product@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var LoginModal = Backbone.View.extend({
  el: '#login-modal',
  button: null,
  events: {
    'valid.fndtn.abide form': 'onFormValidated',
    'opened.fndtn.reveal': 'onModalOpened'
  },
  initialize: function()
  {
    this.button = this.$el.find('.loading-button');
  },
  onFormValidated: function(e)
  {
    e.preventDefault();

    var errorContainer = this.$el.find('.alert-box');
    errorContainer.hide();
    this.button.addClass('loading');

    $.ajax({
      url:  "/api/astroprint/private-key",
      type: "POST",
      data: {
        email: this.$el.find('input[name=email]').val(),
        password: this.$el.find('input[name=password]').val()
      }
    })
    .done(function(){
      //Let some time for the cookie to be set
      setTimeout(function(){
        location.reload();
      }, 1000);
    })
    .fail(_.bind(function(xhr){
      if (xhr.status != 0) {
        if (xhr.status == 503) {
          errorContainer.text('AstroPrint.com can\'t be reached').show();
        } else {
          errorContainer.text('Invalid Email/Password').show();
        }
        this.button.removeClass('loading');
      }
    }, this));

    return false;
  },
  onModalOpened: function()
  {
    this.$el.find("input[name='email']").focus();
  }
});

var loginModal = new LoginModal();
