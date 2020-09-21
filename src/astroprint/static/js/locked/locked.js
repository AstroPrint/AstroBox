/*
 *  (c) AstroPrint Product Team. 3DaGoGo, Inc. (product@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

/* exported lockedView */

$.ajaxSetup({
  cache: false
});

var LoginForm = Backbone.View.extend({
  el: '#login-form',
  view: null,
  unblockModal: null,
  events: {
    'submit': 'onSubmit',
    'click a.pin': 'onPinClicked',
    'click a.unblock': 'onUnblockClicked'
  },
  initialize: function(options)
  {
    this.view = options.view
    this.unblockModal = new UnblockModal();
  },
  onPinClicked: function(e)
  {
    e.preventDefault()
    this.view.$el.addClass('pin')
  },
  onUnblockClicked: function(e)
  {
    e.preventDefault()
    this.unblockModal.open()
  },
  onSubmit: function(e)
  {
    e.preventDefault();

    var loadingBtn = this.$('.loading-button');

    loadingBtn.addClass('loading');
    this.view.loggingIn = true

    $.ajax({
      type: 'POST',
      url: '/api/login',
      data: this.$el.serializeArray(),
      headers: {
        "X-Api-Key": UI_API_KEY
      }
    })
    .done(function(){
      location.reload();
    })
    .fail(function(xhr){
      var message = "Unkonwn error (" + xhr.status + "). Please refresh the page";

      if (xhr.status == 401) {
        if (xhr.responseText.toLowerCase() == 'invalid api key') {
          message = "The access key has changed. Please refresh the page.";
        } else {
          message = "Invalid Password";
        }
      }

      noty({text: message , timeout: 3000});
      loadingBtn.removeClass('loading');
    })
    .always(_.bind(function(){
      this.view.loggingIn = false
    }, this))

    return false;
  }
});

var PinForm = Backbone.View.extend({
  el: '#pin-form',
  view: null,
  attempts: 3,
  events: {
    'submit': 'onSubmit',
    'mousedown a.show-pin': "onShow",
    'mouseup a.show-pin': "onHide",
    'mouseleave a.show-pin': "onHide",
    'click a.forgot': 'onForgotClicked',
    'click button.confirm': 'onConfirmClicked'
  },
  initialize: function (options)
  {
    this.view = options.view
  },
  onShow: function(e)
  {
    e.preventDefault()
    this.$('input').attr('type', 'text')
    this.attempts = 3
  },
  onHide: function()
  {
    this.$('input').attr('type', 'password')
  },
  onSubmit: function (e)
  {
    e.preventDefault();
  },
  onForgotClicked: function(e)
  {
    e.preventDefault()

    this.view.$el.removeClass('pin')
  },
  onConfirmClicked: function(e)
  {
    e.preventDefault()
    var loadingBtn = this.$('.loading-button');

    loadingBtn.addClass('loading');
    this.view.loggingIn = true

    $.ajax({
      type: 'POST',
      url: '/api/validate-pin',
      data: this.$el.serializeArray(),
      headers: {
        "X-Api-Key": UI_API_KEY
      }
    })
      .done(function () {
        location.reload();
      })
      .fail(_.bind(function (xhr) {
        var message = "Unkonwn error ("+xhr.status+"). Please refresh the page";

        if (xhr.status == 401) {
          message = "Invalid PIN. Remaining attempts: " + this.attempts;

          if (this.attempts <= 0) {
            this.view.$el.removeClass('pin').addClass('no-pin')
          } else {
            this.attempts--
          }
        }

        noty({ text: message, timeout: 3000 });
        loadingBtn.removeClass('loading');
      }, this))
      .always(_.bind(function () {
        this.view.loggingIn = false
      }, this))
  }
})

var UnblockModal = Backbone.View.extend({
  el: "#unblock-modal",
  events: {
    'click button.close': 'onCloseClicked'
  },
  open: function ()
  {
    this.$('input#code').val('')
    this.$el.foundation('reveal', 'open');
  },
  onCloseClicked: function (e) {
    e.preventDefault()
    this.$el.foundation('reveal', 'close');
  },
})

var LockedView = Backbone.View.extend({
  el: '#locked-view',
  loginForm: null,
  pinForm: null,
  loggingIn: false,
  initialize: function()
  {
    this.loginForm = new LoginForm({view: this});
    this.pinForm = new PinForm({view: this});
    this.startPolling();
  },
  startPolling: function()
  {
    setInterval(_.bind(function(){
      if (!this.loggingIn) {
        $.ajax({type:'POST', url: '/accessKeys'})
          .done(function(data){
            if (_.isObject(data)) {
              location.reload();
            }
          })
        }
    }, this), 3000);
  }
});

var lockedView = new LockedView();
